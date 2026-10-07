import secrets
import bcrypt
from fastapi import Header, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_db_connection

# Declare HTTPBearer security scheme for Swagger UI
security = HTTPBearer()

def hash_password(password: str) -> str:
  # Truncate to 72 bytes to respect bcrypt's hard specification limit
  pwd_bytes = password.encode("utf-8")[:72]
  salt = bcrypt.gensalt()
  return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
  pwd_bytes = plain_password.encode("utf-8")[:72]
  return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))

def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sessions (token, user_id) VALUES (%s, %s);", (token, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    return token

def delete_session(token: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = %s;", (token,))
    conn.commit()
    cursor.close()
    conn.close()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token"
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    # If your sessions table matches tokens to users:
    cursor.execute("""
        SELECT u.id, u.email 
        FROM users u
        JOIN sessions s ON u.id = s.user_id
        WHERE s.token = %s;
    """, (token,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token"
        )

    return user