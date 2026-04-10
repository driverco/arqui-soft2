import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from typing import Annotated


from fastapi import FastAPI, HTTPException, Request, Header, Depends, Response
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor
import psycopg2
from datetime import datetime
from typing import Optional
import httpx
import os
import time
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)

class TokenData(BaseModel):
    username: str
    role: str

def get_request_info(request: Request):
    """Extract client IP and pod hostname from request"""
    return (request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host, os.getenv("HOSTNAME"))

async def get_current_writepod():
    async with httpx.AsyncClient() as client:
        logger.info(f"Sending request to {os.getenv('ADMINKUBES_SERVICE_URL')}/write-pod")
        response = await client.get(f"{os.getenv('ADMINKUBES_SERVICE_URL')}/write-pod")
        logger.info(f"Response from {os.getenv('ADMINKUBES_SERVICE_URL')}/write-pod: {response.json().get('writepod', 'none')}")
        return response.json().get('writepod', 'none')

async def writepod():
    writepod = await get_current_writepod()
    podname =  os.getenv("HOSTNAME")
    logger.info(f"Writepod: {writepod}, Current pod: {podname}")
    return podname==writepod


async def log_audit(username, method, endpoint, user_agent, ip, pod, security_status="NORMAL", security_message=None, is_write: Optional[bool] = None):
    should_write = is_write if is_write is not None else await writepod()

    if should_write:
        try:
            logger.info(f"Writing audit log: user={username}, method={method}, endpoint={endpoint}, user_agent={user_agent}, ip={ip}, pod={pod}")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO audit_logs (user_id, method, endpoint, timestamp, user_agent, ip, pod, security_status, security_message) "
                "VALUES ((select user_id from users where username = %s), %s, %s, now(), %s, %s, %s, %s, %s)",
                (username, method, endpoint, user_agent, ip, pod, security_status, security_message),
            )
            conn.commit()
            cursor.close()
            conn.close()
            logger.info(f"Audit log: user={username}, method={method}, endpoint={endpoint}, user_agent={user_agent}, ip={ip}, pod={pod}")
        except psycopg2.Error as e:
            logger.error(f"Database error in audit log: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in audit log: {str(e)}")
    else:
        logger.warning(f"Is Not the  writepod, skipping audit log: user={username}, method={method}, endpoint={endpoint}, user_agent={user_agent}, ip={ip}, pod={pod}")           


async def get_current_user_from_token(token: str):
    print (f"get_current_user_from_token - token: {token}")
    async with httpx.AsyncClient() as client:
        #logger.info(f"Sending request to {os.getenv('AUTH_SERVICE_URL')}/users/me with token: {token}")
        start_time = time.perf_counter()
        response = await client.get(f"{os.getenv('AUTH_SERVICE_URL')}/users/me", headers={"Authorization": f"Bearer {token}"})
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        logger.info(f"Bloque Auth - Execution time: {duration_ms:.2f} milliseconds")
        if response.status_code != 200:
            logger.error(f"Auth service response: {response.status_code} - {response.text}")
            return TokenData(username="", role="")
        user_data = response.json()
        return TokenData(username=user_data["username"], role=user_data["role"])


async def require_role(current_user, *allowed_roles):
    async def role_checker():
        if not current_user:
            return False
        if current_user.role not in allowed_roles:
            return False
        return True
    return await role_checker()


async def log_and_validate(request: Request, token: str, allowed_roles: list, is_write: Optional[bool] = None):
    #logger.info(f"tokenlogandvalidate: {token}")
    start_time = time.perf_counter()
    current_user = await get_current_user_from_token(token=token)
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000
    logger.info(f"Bloque A - Execution time: {duration_ms:.2f} milliseconds")
    #logger.info(f"Current user: {current_user.username}, role: {current_user.role}")

    start_time = time.perf_counter()
    await log_audit(current_user.username, *get_request_info(request), is_write=is_write)
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000
    logger.info(f"Bloque B - Execution time: {duration_ms:.2f} milliseconds")

    start_time = time.perf_counter()
    if not current_user.username:
        raise HTTPException(status_code=401, detail="Token inválido o acceso denegado")
    if not await require_role(current_user, *allowed_roles):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000
    logger.info(f"Bloque C - Execution time: {duration_ms:.2f} milliseconds")

class OrderCreateItem(BaseModel):
    item_id: int
    quantity: int
    unit_value: float

class OrderCreate(BaseModel):
    user_id: Optional[int] = None
    client_id: int
    items: list[OrderCreateItem]

class Order(BaseModel):
    order_id: int
    user_id: int
    timestamp: datetime
    client_id: int

async def analyze_request(request: Request, user_id: int):
    original_user_agent = request.headers.get("X-Original-User-Agent", request.headers.get("user-agent", "none"))
    print("Original User-Agent: ", original_user_agent)
    headers = {}
    if original_user_agent:
        headers["X-Original-User-Agent"] = original_user_agent

    client_ip = request.client.host
    x_forwarded_for = request.headers.get("x-forwarded-for")

    if x_forwarded_for:
        forwarded_for = f"{x_forwarded_for}, {client_ip}"
    else:
        forwarded_for = client_ip

    headers['X-Forwarded-For'] = forwarded_for

    async with httpx.AsyncClient() as client:
        print(user_id)
        response = await client.get(f"{os.getenv('ANALYTICS_SERVICE_URL')}/analyze/{user_id}", headers=headers)
        return response.json()

@app.post("/orders", response_model=Order)
async def create_order(request: Request, order: OrderCreate, token: str = Depends(oauth2_scheme)):
    current_user = await get_current_user_from_token(token)
    log_audit(current_user.username, *get_request_info(request))

    conn = get_db_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (current_user.username,))
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=400, detail="Usuario autenticado no encontrado")

        authenticated_user_id = user_row["user_id"]
        target_user_id = order.user_id if order.user_id else authenticated_user_id

        if current_user.role == "U" and target_user_id != authenticated_user_id:
            raise HTTPException(status_code=403, detail="Los usuarios no pueden crear órdenes para otro usuario")

        cursor.execute(
            "INSERT INTO orders (user_id, timestamp, client_id) VALUES (%s, NOW(), %s) RETURNING order_id, user_id, timestamp, client_id",
            (target_user_id, order.client_id)
        )
        new_order = cursor.fetchone()
        order_id = new_order["order_id"]

        if order.items:
            item_ids = [item.item_id for item in order.items]
            cursor.execute(
                "SELECT item_id FROM items WHERE item_id = ANY(%s)",
                (item_ids,)
            )
            existing_items = {row["item_id"] for row in cursor.fetchall()}
            missing_items = [item_id for item_id in item_ids if item_id not in existing_items]
            if missing_items:
                raise HTTPException(
                    status_code=400,
                    detail=f"Los siguientes item_id no existen: {missing_items}"
                )

            for item in order.items:
                cursor.execute(
                    "INSERT INTO orders_items (order_id, item_id, quantity, unit_value) VALUES (%s, %s, %s, %s)",
                    (order_id, item.item_id, item.quantity, item.unit_value)
                )

        conn.commit()
        return new_order
    except HTTPException:
        conn.rollback()
        cursor.close()
        conn.close()
        raise
    except psycopg2.Error as e:
        conn.rollback()
        cursor.close()
        conn.close()
        logger.error(f"Database error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al crear la orden")
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        logger.error(f"Unexpected error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail="Error inesperado al crear la orden")
    finally:
        if not cursor.closed:
            cursor.close()
        if conn and not conn.closed:
            conn.close()


@app.post("/orders-optimized", response_model=Order)
async def create_order_optimized(
    request: Request,
    order: OrderCreate,
    isWrite: bool,
    token: str = Depends(oauth2_scheme),
):
    current_user = await get_current_user_from_token(token)
    await log_audit(current_user.username, *get_request_info(request), is_write=isWrite)

    conn = get_db_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (current_user.username,))
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=400, detail="Usuario autenticado no encontrado")

        authenticated_user_id = user_row["user_id"]
        target_user_id = order.user_id if order.user_id else authenticated_user_id

        if current_user.role == "U" and target_user_id != authenticated_user_id:
            raise HTTPException(status_code=403, detail="Los usuarios no pueden crear órdenes para otro usuario")

        cursor.execute(
            "INSERT INTO orders (user_id, timestamp, client_id) VALUES (%s, NOW(), %s) RETURNING order_id, user_id, timestamp, client_id",
            (target_user_id, order.client_id)
        )
        new_order = cursor.fetchone()
        order_id = new_order["order_id"]

        if order.items:
            item_ids = [item.item_id for item in order.items]
            cursor.execute(
                "SELECT item_id FROM items WHERE item_id = ANY(%s)",
                (item_ids,)
            )
            existing_items = {row["item_id"] for row in cursor.fetchall()}
            missing_items = [item_id for item_id in item_ids if item_id not in existing_items]
            if missing_items:
                raise HTTPException(
                    status_code=400,
                    detail=f"Los siguientes item_id no existen: {missing_items}"
                )

            for item in order.items:
                cursor.execute(
                    "INSERT INTO orders_items (order_id, item_id, quantity, unit_value) VALUES (%s, %s, %s, %s)",
                    (order_id, item.item_id, item.quantity, item.unit_value)
                )

        conn.commit()
        return new_order
    except HTTPException:
        conn.rollback()
        cursor.close()
        conn.close()
        raise
    except psycopg2.Error as e:
        conn.rollback()
        cursor.close()
        conn.close()
        logger.error(f"Database error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al crear la orden")
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        logger.error(f"Unexpected error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail="Error inesperado al crear la orden")
    finally:
        if not cursor.closed:
            cursor.close()
        if conn and not conn.closed:
            conn.close()


def get_filtered_orders(user_id: Optional[int] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id is not None:
        cursor.execute("SELECT order_id, user_id, timestamp, client_id FROM orders WHERE user_id = %s", (user_id,))
    else:
        cursor.execute("SELECT order_id, user_id, timestamp, client_id FROM orders")
    
    orders = cursor.fetchall()
    order_ids = [order["order_id"] for order in orders]

    if order_ids:
        cursor.execute(
            "SELECT order_id, item_id, quantity, unit_value FROM orders_items WHERE order_id = ANY(%s)",
            (order_ids,)
        )
        items_rows = cursor.fetchall()
    else:
        items_rows = []

    cursor.close()
    conn.close()

    orders_by_id = {order["order_id"]: dict(order, items=[]) for order in orders}
    for item_row in items_rows:
        orders_by_id[item_row["order_id"]]["items"].append({
            "item_id": item_row["item_id"],
            "quantity": item_row["quantity"],
            "unit_value": item_row["unit_value"]
        })

    return list(orders_by_id.values())


@app.get("/orders")
async def get_orders(request: Request, token: Annotated[str, Depends(oauth2_scheme)]):
    start_time = time.perf_counter()
    logger.info(f"Token: {token}")
    await log_and_validate( request, token, allowed_roles=["A", "S"])
    logger.info("Retrieving all orders")
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000
    logger.info(f"Block 1 - Execution time: {duration_ms:.2f} milliseconds")

    start_time = time.perf_counter()
    current_user = await get_current_user_from_token(token)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE username = %s", (current_user.username,))
    user_row = cursor.fetchone()
    user_id = user_row["user_id"] if user_row else None ### Falta acción si no se puede determinar el user_id
    cursor.close()
    conn.close()
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000
    logger.info(f"Block 2 - Execution time: {duration_ms:.2f} milliseconds")

    start_time = time.perf_counter()
    loop = asyncio.get_running_loop()

    orders_task = loop.run_in_executor(None, get_filtered_orders)
    analytics_task = analyze_request(request, user_id)

    orders, analysis = await asyncio.gather(orders_task, analytics_task)

    if analysis.get("suspicious_activity"):
        logger.warning(f"Suspicious activity detected for user {current_user.username}: {analysis}")
        print(f"Suspicious activity detected for user {current_user.username}: {analysis}")
        await log_audit(current_user.username, *get_request_info(request), security_status="BLOCKED", security_message=str(analysis))
        return Response(content='{"detail": "Suspicious activity detected, access denied"}', status_code=403, media_type="application/json")
    orders = get_filtered_orders()
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000
    logger.info(f"Block 3 - Execution time: {duration_ms:.2f} milliseconds")

    return orders


@app.get("/orders-optimized")
async def get_orders_optimized(
    request: Request,
    isWrite: bool,
    token: Annotated[str, Depends(oauth2_scheme)],
):
    start_time = time.perf_counter()
    logger.info(f"Token: {token}")
    await log_and_validate(request, token, allowed_roles=["A", "S"], is_write=isWrite)
    logger.info("Retrieving all orders")
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000
    logger.info(f"Block 1 - Execution time: {duration_ms:.2f} milliseconds")

    start_time = time.perf_counter()
    current_user = await get_current_user_from_token(token)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE username = %s", (current_user.username,))
    user_row = cursor.fetchone()
    user_id = user_row["user_id"] if user_row else None
    cursor.close()
    conn.close()
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000
    logger.info(f"Block 2 - Execution time: {duration_ms:.2f} milliseconds")

    start_time = time.perf_counter()
    loop = asyncio.get_running_loop()

    orders_task = loop.run_in_executor(None, get_filtered_orders)
    analytics_task = analyze_request(request, user_id)

    orders, analysis = await asyncio.gather(orders_task, analytics_task)

    if analysis.get("suspicious_activity"):
        logger.warning(f"Suspicious activity detected for user {current_user.username}: {analysis}")
        print(f"Suspicious activity detected for user {current_user.username}: {analysis}")
        await log_audit(
            current_user.username,
            *get_request_info(request),
            security_status="BLOCKED",
            security_message=str(analysis),
            is_write=isWrite,
        )
        return Response(content='{"detail": "Suspicious activity detected, access denied"}', status_code=403, media_type="application/json")
    orders = get_filtered_orders()
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000
    logger.info(f"Block 3 - Execution time: {duration_ms:.2f} milliseconds")

    return orders


@app.get("/orders/{user_id}")
async def get_ordersbyuser(request: Request, user_id: int, token: str = Depends(oauth2_scheme)):
    await log_and_validate( request, token, allowed_roles=["A", "S", "U"])
    current_user = await get_current_user_from_token(token)
    if current_user.role == "U" :
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (current_user.username,))
        user_row = cursor.fetchone()
        cursor.close()
        if int(user_id) != int(user_row["user_id"]):
            raise HTTPException(status_code=403, detail="Los usuarios no pueden ver órdenes de otro usuario")
        conn.close()
    orders = get_filtered_orders(user_id=user_id)
    return orders


@app.get("/my-orders")
async def get_my_orders(request: Request, token: str = Depends(oauth2_scheme)):
    current_user = await get_current_user_from_token(token)
    await log_audit(current_user.username, *get_request_info(request))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE username = %s", (current_user.username,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user_id = user["user_id"]
    cursor.close()
    conn.close()
    orders = get_filtered_orders(user_id=user_id)
    return orders

@app.get("/")
async def root():
    return {"message": "Orders Service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
