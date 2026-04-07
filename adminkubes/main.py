import asyncio
import logging
import os

from contextlib import asynccontextmanager

from fastapi import FastAPI
from kubernetes import client, config


logger = logging.getLogger(__name__)

v1 = None
snapshot = {
    "pods": [],
    "writepod": "",
}
refresh_task = None


def get_kube_client():
    global v1

    if v1 is not None:
        return v1

    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()

    v1 = client.CoreV1Api()
    return v1


def fetch_snapshot():
    global snapshot

    kube_client = get_kube_client()
    pods = kube_client.list_namespaced_pod(
        namespace="default",
        label_selector="app=orders-service",
    )

    pod_statuses = []
    running_pod_names = set()

    for pod in pods.items:
        pod_status = {
            "name": pod.metadata.name,
            "status": pod.status.phase,
            "pod_ip": pod.status.pod_ip,
            "ready": all(container.ready for container in pod.status.container_statuses or []),
        }
        pod_statuses.append(pod_status)

        if pod.status.phase == "Running":
            running_pod_names.add(pod.metadata.name)

    current_writepod = snapshot["writepod"]

    if current_writepod not in running_pod_names:
        current_writepod = ""
        for pod in pods.items:
            if pod.status.phase == "Running":
                current_writepod = pod.metadata.name
                break

    snapshot = {
        "pods": pod_statuses,
        "writepod": current_writepod,
    }


async def refresh_snapshot_loop():
    while True:
        try:
            await asyncio.to_thread(fetch_snapshot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to refresh Kubernetes snapshot")

        await asyncio.sleep(float(os.getenv("REFRESH_INTERVAL_SECONDS") or 10))   


@asynccontextmanager
async def lifespan(_: FastAPI):
    global refresh_task

    refresh_task = asyncio.create_task(refresh_snapshot_loop())

    try:
        yield
    finally:
        if refresh_task is not None:
            refresh_task.cancel()
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass


app = FastAPI(lifespan=lifespan)


@app.get("/pods")
async def get_pods_status():
    return {"pods": snapshot["pods"]}


@app.get("/write-pod")
async def get_write_pod():
    return {"writepod": snapshot["writepod"]}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
