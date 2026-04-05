import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from typing import Annotated


from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor
import psycopg2
from datetime import datetime
from typing import Optional
import httpx
import os

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


async def log_audit(username, method, endpoint, user_agent, ip, pod):
    if (await writepod()):
        try:
            logger.info(f"Writing audit log: user={username}, method={method}, endpoint={endpoint}, user_agent={user_agent}, ip={ip}, pod={pod}")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO audit_logs (user_id, method, endpoint, timestamp, user_agent, ip, pod) "
                "VALUES ((select user_id from users where username = %s), %s, %s, now(), %s, %s, %s)",
                (username, method, endpoint, user_agent, ip, pod),
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
    async with httpx.AsyncClient() as client:
        #logger.info(f"Sending request to {os.getenv('AUTH_SERVICE_URL')}/users/me with token: {token}")
        response = await client.get(f"{os.getenv('AUTH_SERVICE_URL')}/users/me", headers={"Authorization": f"Bearer {token}"})
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


async def log_and_validate(request: Request, token: str, allowed_roles: list):
    #logger.info(f"tokenlogandvalidate: {token}")
    current_user = await get_current_user_from_token(token=token)
    #logger.info(f"Current user: {current_user.username}, role: {current_user.role}")
    await log_audit(current_user.username, *get_request_info(request))
    if not current_user.username:
        raise HTTPException(status_code=401, detail="Token inválido o acceso denegado")
    if not await require_role(current_user, *allowed_roles):
        raise HTTPException(status_code=403, detail="Acceso denegado")


class OrderCreate(BaseModel):
    user_id: Optional[int] = None
    client_id: int

class Order(BaseModel):
    order_id: int
    user_id: int
    timestamp: datetime
    client_id: int


@app.post("/orders", response_model=Order)
async def create_order(request: Request, order: OrderCreate):
    current_user = await get_current_user_from_token(oauth2_scheme)
    log_audit(current_user.username, *get_request_info(request))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE username = %s", (current_user.username,))
    user_row = cursor.fetchone()
    if not user_row:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Usuario autenticado no encontrado")

    authenticated_user_id = user_row["user_id"]
    target_user_id = order.user_id if order.user_id else authenticated_user_id

    if current_user.role == "U" and target_user_id != authenticated_user_id:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=403, detail="Los usuarios no pueden crear órdenes para otro usuario")

    cursor.execute(
        "INSERT INTO orders (user_id, timestamp, client_id) VALUES (%s, NOW(), %s) RETURNING order_id, user_id, timestamp, client_id",
        (target_user_id, order.client_id)
    )
    new_order = cursor.fetchone()
    conn.commit()
    cursor.close()
    conn.close()
    return new_order








@app.get("/orders")
async def get_orders(request: Request, token: Annotated[str, Depends(oauth2_scheme)]):
    #logger.info(f"Token: {token}")
    await log_and_validate( request, token, allowed_roles=["A", "S"])
    logger.info("Retrieving all orders")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT order_id, user_id, timestamp, client_id FROM orders")
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return orders










# @app.get("/orders/{user_id}")
# async def get_ordersbyuser(request: Request, user_id: int):
#     await log_and_validate( request, allowed_roles=["A", "S", "U"])
#     current_user = await get_current_user_from_token(oauth2_scheme)
#     if current_user.role == "U" :
#         conn = get_db_connection()
#         cursor = conn.cursor()
#         cursor.execute("SELECT user_id FROM users WHERE username = %s", (current_user.username,))
#         user_row = cursor.fetchone()
#         cursor.close()
#         if int(user_id) != int(user_row["user_id"]):
#             raise HTTPException(status_code=403, detail="Los usuarios no pueden ver órdenes de otro usuario")

#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("SELECT order_id, user_id, timestamp, client_id FROM orders WHERE user_id = %s", (user_id,))
#     orders = cursor.fetchall()
#     cursor.close()
#     conn.close()
#     return orders










    

@app.get("/my-orders")
async def get_my_orders(request: Request):
    current_user = await get_current_user_from_token(oauth2_scheme)
    log_audit(current_user.username, *get_request_info(request))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE username = %s", (current_user.username,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user_id = user["user_id"]
    cursor.execute("SELECT order_id, user_id, timestamp, client_id FROM orders WHERE user_id = %s", (user_id,))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return orders

@app.get("/")
async def root():
    return {"message": "Orders Service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)

