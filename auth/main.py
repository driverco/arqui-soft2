import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta
import jwt
import psycopg2
from psycopg2.extras import RealDictCursor
from passlib.context import CryptContext
import hashlib
import os
from dotenv import load_dotenv
load_dotenv()

# Contexto para hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str
    role: str

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)

def get_request_info(request: Request):
    """Extract client IP and pod hostname from request"""
    return (request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host, os.getenv("HOSTNAME"))

def log_audit(username, method, endpoint, user_agent, ip, pod):
    try:
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

def verify_password(plain_password, hashed_password):
#    return pwd_context.verify(plain_password, hashed_password)
    return plain_password == hashed_password

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, os.getenv("SECRET_KEY"), algorithm=os.getenv("ALGORITHM"))

def is_token_blacklisted(token: str) -> bool:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM token_blacklist WHERE token_hash = %s AND expires_at > NOW()", (token_hash,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result is not None

def blacklist_token(token: str):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO token_blacklist (token_hash, expires_at) VALUES (%s, %s) ON CONFLICT (token_hash) DO NOTHING", (token_hash, expires_at))
    conn.commit()
    cursor.close()
    conn.close()

def get_current_user(token: str = Depends(oauth2_scheme)):
    if is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=[os.getenv("ALGORITHM")])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        return TokenData(username=username, role=role)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

def require_role(*allowed_roles):
    async def role_checker(current_user: TokenData = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Permiso denegado")
        return current_user
    return role_checker

@app.post("/token", response_model=Token)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (form_data.username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not user or not verify_password(form_data.password, user["password"]):
        log_audit(form_data.username, *get_request_info(request))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user["username"], "role": user["role"]})
    log_audit(user["username"], *get_request_info(request))
    return {"access_token": access_token, "token_type": "bearer"}





async def log_and_validate(request: Request, token: str, allowed_roles: list):

    current_user = get_current_user()
    print(f"Current user: {current_user.username}, role: {current_user.role}")
    log_audit(current_user.username, *get_request_info(request))
    if not current_user.username:
        raise HTTPException(status_code=401, detail="Token inválido o acceso denegado")
    if not await require_role(*allowed_roles):
        raise HTTPException(status_code=403, detail="Acceso denegado")


@app.get("/users/me")
async def read_users_me(request: Request, token: str = Depends(oauth2_scheme)):
    if is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token blacklisted")
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=[os.getenv("ALGORITHM")])
        username: str = payload.get("sub")
        if username is None:
            log_audit(None, *get_request_info(request))
            raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.PyJWTError:
        log_audit(None, *get_request_info(request))
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if not user:
        log_audit(username, *get_request_info(request))
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    log_audit(username, *get_request_info(request))
    return {"username": user["username"], "role": payload.get("role")}


@app.post("/logout")
async def logout(request: Request, token: str = Depends(oauth2_scheme), current_user: TokenData = Depends(get_current_user)):
    blacklist_token(token)
    log_audit(current_user.username, *get_request_info(request))
    return {"message": f"Usuario {current_user.username} ha cerrado sesión exitosamente"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

