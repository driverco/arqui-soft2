import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor
import psycopg2
from datetime import datetime
from typing import Optional
import httpx

app = FastAPI()

# Database connection
DATABASE_URL = "postgresql://admin:DevTeam+1379@postgres:30432/orders"  # Update as needed

# Auth service URL
AUTH_SERVICE_URL = "http://auth-service:8010"  # Kubernetes service name

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

class TokenData(BaseModel):
    username: str
    role: str

def log_audit(username, method, endpoint, user_agent, ip):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO audit_logs (user_id, method, endpoint, timestamp, user_agent, ip) "
            "VALUES ((select user_id from users where username = %s), %s, %s, now(), %s, %s)",
            (username, method, endpoint, user_agent, ip),
        )
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Audit log: user={username}, method={method}, endpoint={endpoint}, user_agent={user_agent}, ip={ip}")
    except psycopg2.Error as e:
        logger.error(f"Database error in audit log: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in audit log: {str(e)}")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{AUTH_SERVICE_URL}/validate", headers={"Authorization": f"Bearer {token}"})
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Token inválido o acceso denegado")
        user_data = response.json()
        return TokenData(username=user_data["username"], role=user_data["role"])

def require_role(*allowed_roles):
    async def role_checker(current_user: TokenData = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Acceso denegado")
        return current_user
    return role_checker

class OrderCreate(BaseModel):
    user_id: Optional[int] = None
    client_id: int

class Order(BaseModel):
    order_id: int
    user_id: int
    timestamp: datetime
    client_id: int

@app.post("/orders", response_model=Order)
async def create_order(request: Request, order: OrderCreate, current_user: TokenData = Depends(get_current_user)):
    log_audit(current_user.username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)

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
async def get_orders(request: Request, current_user: TokenData = Depends(require_role("A", "S"))):
    log_audit(current_user.username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT order_id, user_id, timestamp, client_id FROM orders")
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return orders

@app.get("/my-orders")
async def get_my_orders(request: Request,current_user: TokenData = Depends(get_current_user)):
    log_audit(current_user.username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
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
    uvicorn.run(app, host="0.0.0.0", port=8000)

