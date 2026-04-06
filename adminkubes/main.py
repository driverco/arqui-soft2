from fastapi import FastAPI
from kubernetes import client, config

app = FastAPI()

writepod = ""


@app.get("/pods")
async def get_pods_status():
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace="default", label_selector="app=orders-service")
    pod_statuses = []
    for pod in pods.items:
        pod_statuses.append({
            "name": pod.metadata.name,
            "status": pod.status.phase,
            "pod_ip": pod.status.pod_ip,
            "ready": all(container.ready for container in pod.status.container_statuses or [])
        })
    return {"pods": pod_statuses}


@app.get("/write-pod")

async def get_write_pod():
    global writepod

    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()
    v1 = client.CoreV1Api()
    #get pods
    pods = v1.list_namespaced_pod(namespace="default", label_selector="app=orders-service")

    #get pods
    for pod in pods.items:
        if pod.metadata.name == writepod and pod.status.phase == "Running":
            return {"writepod": writepod}

    for pod in pods.items:
        if pod.status.phase == "Running":
                writepod = pod.metadata.name
                break

    return {"writepod": writepod}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
