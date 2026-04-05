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

# Configuración del JWT
SECRET_KEY = "mi_llave_secreta_muy_segura"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Configuración de la base de datos PostgreSQL
DATABASE_URL = "postgresql://admin:DevTeam+1379@localhost:5432/orders"  # Replace with your credentials

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
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

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

def verify_password(plain_password, hashed_password):
#    return pwd_context.verify(plain_password, hashed_password)
    return plain_password == hashed_password

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

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
    expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
        log_audit(form_data.username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user["username"], "role": user["role"]})
    log_audit(user["username"], request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/admin-only")
async def admin_only(request: Request, current_user: TokenData = Depends(require_role("admin"))):
    try:
        log_audit(current_user.username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
        return {"message": f"Accceso concedido a {current_user.username} con rol {current_user.role}"}
    except HTTPException as e:
        if e.status_code == 403:
            log_audit(current_user.username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
            raise HTTPException(status_code=403, detail="Acceso denegado: Solo administradores permitidos")
        raise

@app.get("/users-and-admins")
async def users_and_admins(request: Request, current_user: TokenData = Depends(require_role("user", "admin"))):
    try:
        return {"message": f"Accceso concedido a {current_user.username} con rol {current_user.role}"}
    except HTTPException as e:
        if e.status_code == 403:
            log_audit(current_user.username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
            raise HTTPException(status_code=403, detail="Acceso denegado: Solo usuarios y administradores permitidos")
        raise

@app.get("/users-and-supervisors")
async def users_and_supervisors(request: Request, current_user: TokenData = Depends(require_role("user", "supervisor"))):
    try:
        return {"message": f"Accceso concedido a {current_user.username} con rol {current_user.role}"}
    except HTTPException as e:
        if e.status_code == 403:
            log_audit(current_user.username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
            raise HTTPException(status_code=403, detail="Acceso denegado: Solo usuarios y supervisores permitidos")
        raise

@app.get("/admins-and-supervisors")
async def admins_and_supervisors(request: Request, current_user: TokenData = Depends(require_role("admin", "supervisor"))):
    try:
        return {"message": f"Accceso concedido a {current_user.username} con rol {current_user.role}"}
    except HTTPException as e:
        if e.status_code == 403:
            log_audit(current_user.username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
            raise HTTPException(status_code=403, detail="Acceso denegado: Solo administradores y supervisores permitidos")
        raise


@app.get("/users/me")
async def read_users_me(request: Request, token: str = Depends(oauth2_scheme)):
    if is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            log_audit(None, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
            raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.PyJWTError:
        log_audit(None, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, full_name FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not user:
        log_audit(username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    log_audit(username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
    return {"username": user["username"], "full_name": user["full_name"]}

@app.post("/logout")
async def logout(request: Request, token: str = Depends(oauth2_scheme), current_user: TokenData = Depends(get_current_user)):
    blacklist_token(token)
    log_audit(current_user.username, request.method, request.url.path, request.headers.get("user-agent", "none"), request.client.host)
    return {"message": f"Usuario {current_user.username} ha cerrado sesión exitosamente"}

def get_current_user(token: str = Depends(oauth2_scheme)):
    if is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
