import logging

import re
from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.security import OAuth2PasswordBearer
from psycopg2.extras import RealDictCursor
import psycopg2
from typing import Optional
import os

from dotenv import load_dotenv
load_dotenv()  # Carga las variables de entorno desde el archivo .env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)

def parse_user_agent(user_agent: str) -> dict[str, str]:
    ua = user_agent or ""
    parsed: dict[str, str] = {
        "raw": ua,
        "os": "unknown",
        "browser": "unknown",
        "browser_version": "unknown",
        "device": "unknown"
    }

    if "Windows NT" in ua:
        parsed["os"] = "Windows"
    elif "Macintosh" in ua or "Mac OS X" in ua:
        parsed["os"] = "macOS"
    elif "Android" in ua:
        parsed["os"] = "Android"
    elif "iPhone" in ua or "iPad" in ua or "iPod" in ua:
        parsed["os"] = "iOS"
    elif "Linux" in ua:
        parsed["os"] = "Linux"

    if "Mobile" in ua:
        parsed["device"] = "mobile"
    elif "Tablet" in ua or "iPad" in ua:
        parsed["device"] = "tablet"
    else:
        parsed["device"] = "desktop"

    browser_match = None
    if "Edg/" in ua or "Edge/" in ua:
        parsed["browser"] = "Edge"
        browser_match = re.search(r"(?:Edg|Edge)/([\d\.]+)", ua)
    elif "OPR/" in ua or "Opera" in ua:
        parsed["browser"] = "Opera"
        browser_match = re.search(r"(?:OPR|Opera)/([\d\.]+)", ua)
    elif "Chrome/" in ua and "Safari/" in ua and "Edg/" not in ua and "OPR/" not in ua:
        parsed["browser"] = "Chrome"
        browser_match = re.search(r"Chrome/([\d\.]+)", ua)
    elif "Firefox/" in ua:
        parsed["browser"] = "Firefox"
        browser_match = re.search(r"Firefox/([\d\.]+)", ua)
    elif "Safari/" in ua and "Chrome/" not in ua:
        parsed["browser"] = "Safari"
        browser_match = re.search(r"Version/([\d\.]+)", ua)
    elif "MSIE" in ua or "Trident/" in ua:
        parsed["browser"] = "Internet Explorer"
        browser_match = re.search(r"(?:MSIE |rv:)([\d\.]+)", ua)

    if browser_match:
        parsed["browser_version"] = browser_match.group(1)

    return parsed

def check_suspicious_activity(agent: dict[str, str], ip: str, agent2: dict[str, str], ip2: str) -> bool:
    if ip != ip2:
        return True
    if agent["browser"] != agent2["browser"] or agent["os"] != agent2["os"] or agent["device"] != agent2["device"] or agent["browser_version"] != agent2["browser_version"]:
        return True
    return False

@app.get("/analyze/{user_id}")
async def analyze_user_behavior(request: Request, user_id : int):
    # Obtener el user-agent original del header
    agent_header = request.headers.get("X-Original-User-Agent", "")
    agent = parse_user_agent(agent_header)

    # Obtener la IP original del header
    ip = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    
    # Obtener el user-agent e IP almacenados en la base de datos para este usuario
    conn = get_db_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    cursor.execute("SELECT type, value FROM users_user_agent WHERE user_id = %s", (user_id,))
    rows = cursor.fetchall()

    stored_agent: Optional[dict[str, str]] = None
    stored_ip: Optional[str] = None

    for row in rows:
        row_type = str(row["type"]).upper()
        if row_type == "A":
            stored_agent = parse_user_agent(row["value"])
        elif row_type == "I":
            stored_ip = row["value"]
    cursor.close()
    conn.close()

    if check_suspicious_activity(agent, ip, stored_agent or {}, stored_ip or ""):
        return {"suspicious_activity": True, "agent": agent, "ip": ip, "stored_agent": stored_agent, "stored_ip": stored_ip}

    return {"agent": agent, "ip": stored_ip}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)