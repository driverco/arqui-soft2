import asyncio
from importlib.resources import path
import os

from fastapi import FastAPI, Request, Response
import httpx


import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


app = FastAPI()



async def get_current_writepod():
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Sending request to {os.getenv('ADMINKUBES_SERVICE_URL')}/write-pod")
            response = await client.get(f"{os.getenv('ADMINKUBES_SERVICE_URL')}/write-pod", timeout=5.0)
            response.raise_for_status()
            logger.info(f"Response from {os.getenv('ADMINKUBES_SERVICE_URL')}/write-pod: {response.json().get('writepod', 'none')}")
            return response.json().get('writepod', 'none')
    except httpx.HTTPError as e:
        logger.error(f"HTTP error connecting to adminkubes write-pod: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_current_writepod: {str(e)}")
        return None

async def writepod():
    writepod = await get_current_writepod()
    podname =  os.getenv("HOSTNAME")
    logger.info(f"Writepod: {writepod}, Current pod: {podname}")
    return podname==writepod


async def get_order_pods():
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Sending request to {os.getenv('ADMINKUBES_SERVICE_URL')}/pods")
            response = await client.get(f"{os.getenv('ADMINKUBES_SERVICE_URL')}/pods", timeout=5.0)
            response.raise_for_status()
            logger.info(f"Response from {os.getenv('ADMINKUBES_SERVICE_URL')}/pods: {response.json().get('pods', [])}")
            return response.json().get('pods', [])
    except httpx.HTTPError as e:
        logger.error(f"HTTP error connecting to adminkubes pods: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_order_pods: {str(e)}")
        return []



@app.get("/")
async def root():
    return {"message": "APIGateway Service"}

@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_auth(request: Request, path: str):
    try:
        async with httpx.AsyncClient() as client:
            url = f"{os.getenv('AUTH_SERVICE_URL')}/{path}"
            logger.info(f"Proxying request to {url} with method {request.method}")
            
            response = await client.request(
                method=request.method,
                url=url,
                headers={k: v for k, v in request.headers.items() if k.lower() != 'host'},
                content=await request.body(),
                params=request.query_params,
                timeout=10.0
            )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
    except httpx.HTTPError as e:
        logger.error(f"HTTP error proxying to auth service: {str(e)}")
        return Response(content='{"detail": "Auth service error"}', status_code=502, media_type="application/json")
    except Exception as e:
        logger.error(f"Unexpected error in proxy_auth: {str(e)}")
        return Response(content='{"detail": "Internal server error"}', status_code=500, media_type="application/json")


@app.api_route("/api/adminkubes/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_adminkubes(request: Request, path: str):
    try:
        async with httpx.AsyncClient() as client:
            url = f"{os.getenv('ADMINKUBES_SERVICE_URL')}/{path}"
            logger.info(f"Proxying request to {url} with method {request.method}")
            
            response = await client.request(
                method=request.method,
                url=url,
                headers={k: v for k, v in request.headers.items() if k.lower() != 'host'},
                content=await request.body(),
                params=request.query_params,
                timeout=10.0
            )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
    except httpx.HTTPError as e:
        logger.error(f"HTTP error proxying to adminkubes service: {str(e)}")
        return Response(content='{"detail": "Adminkubes service error"}', status_code=502, media_type="application/json")
    except Exception as e:
        logger.error(f"Unexpected error in proxy_adminkubes: {str(e)}")
        return Response(content='{"detail": "Internal server error"}', status_code=500, media_type="application/json")

@app.api_route("/api/orders/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_orders(request: Request, path: str):
    try:
        order_pods = await get_order_pods()
        writepod = await get_current_writepod()
        
        if not order_pods:
            logger.warning("No order pods available")
            return Response(content='{"detail": "No order pods available"}', status_code=503, media_type="application/json")
        
        logger.info(f"Order service pods: {order_pods}")
        
        body_content = await request.body()
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        original_user_agent = request.headers.get('user-agent')
        if original_user_agent:
            headers['X-Original-User-Agent'] = original_user_agent
        
        client_ip = request.client.host

        x_forwarded_for = request.headers.get("x-forwarded-for")

        if x_forwarded_for:
            forwarded_for = f"{x_forwarded_for}, {client_ip}"
        else:
            forwarded_for = client_ip

        headers['X-Forwarded-For'] = forwarded_for

        async def send_request(client: httpx.AsyncClient, pod_name: str, url: str, started: asyncio.Event):
            try:
                started.set()
                response = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    content=body_content,
                    params=request.query_params,
                    timeout=10.0
                )
                logger.info(f"Response from pod {pod_name}: {response.status_code}")
                return response
            except httpx.HTTPError as e:
                logger.warning(f"Error sending request to pod {pod_name}: {str(e)}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error sending request to pod {pod_name}: {str(e)}")
                return None

        dispatch_events = []
        write_task = None

        async with httpx.AsyncClient() as client:
            for pod in order_pods:
                try:
                    pod_ip = pod.get('pod_ip')
                    pod_name = pod.get('name')

                    if not pod_ip:
                        logger.warning(f"Pod {pod_name} has no IP address, skipping")
                        continue

                    url = f"http://{pod_ip}:{os.getenv('ORDERS_PORT')}/{path}"
                    logger.info(f"Proxying request to pod: {pod_name}  url: {url} with method {request.method}")

                    started = asyncio.Event()
                    task = asyncio.create_task(send_request(client, pod_name, url, started))
                    dispatch_events.append(started.wait())

                    if writepod == pod_name:
                        write_task = task
                except Exception as e:
                    logger.error(f"Error preparing pod {pod.get('name')}: {str(e)}")
                    continue

            if write_task is None:
                logger.error("Write pod not found in available pods")
                return Response(content='{"detail": "Write pod error"}', status_code=502, media_type="application/json")

            if dispatch_events:
                await asyncio.gather(*dispatch_events)
            
            response = await write_task

        if(response.status_code == 418): 

            logger.info(f"Sending request to {os.getenv('ADMINKUBES_SERVICE_URL')}/pod-failing")
            responsePodFailing = await client.get(f"{os.getenv('ADMINKUBES_SERVICE_URL')}/pod-failing", timeout=5.0)
            responsePodFailing.raise_for_status()
            #do the call again
            proxy_orders(request, path)

        if response is None:
            logger.error("No response from write pod")
            return Response(content='{"detail": "Write pod error"}', status_code=502, media_type="application/json")
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in proxy_orders: {str(e)}")
        return Response(content='{"detail": "Internal server error"}', status_code=500, media_type="application/json")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
