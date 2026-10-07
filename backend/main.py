from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from database import init_db, get_db_connection
from auth import hash_password, verify_password, create_session, get_current_user
from extraction import process_document
from contextlib import asynccontextmanager
from datetime import date

app = FastAPI(title="ExpiryWatch API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="ExpiryWatch API", version="1.0.0", lifespan=lifespan)

class AuthPayload(BaseModel):
    email: EmailStr
    password: str

@app.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: AuthPayload):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s;", (payload.email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid registration details.")

    hashed = hash_password(payload.password)
    cursor.execute(
        "INSERT INTO users (email, hashed_password) VALUES (%s, %s) RETURNING id;",
        (payload.email, hashed)
    )
    user_id = cursor.fetchone()["id"]
    conn.commit()
    cursor.close()
    conn.close()

    token = create_session(user_id)
    return {"message": "Account created", "token": token, "email": payload.email}

@app.post("/login")
def login(payload: AuthPayload):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, hashed_password FROM users WHERE email = %s;", (payload.email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_session(user["id"])
    return {"message": "Login successful", "token": token, "email": payload.email}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ExpiryWatch", "database": "PostgreSQL"}

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

@app.post("/extract")
async def extract_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    ext = file.filename.split(".")[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: PDF, PNG, JPG, JPEG")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit.")

    result = process_document(file_bytes, file.filename)
    return result

class ConfirmPayload(BaseModel):
    document_type: str
    expiry_date: date

@app.post("/confirm", status_code=status.HTTP_201_CREATED)
def confirm_document(
    payload: ConfirmPayload,
    current_user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO documents (user_id, document_type, expiry_date, status)
        VALUES (%s, %s, %s, 'ACTIVE')
        RETURNING id;
    """, (current_user["id"], payload.document_type, payload.expiry_date))
    doc_id = cursor.fetchone()["id"]
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Document tracked successfully", "document_id": doc_id}

@app.get("/documents")
def get_user_documents(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, document_type, expiry_date, status, created_at
        FROM documents
        WHERE user_id = %s
        ORDER BY expiry_date ASC;
    """, (current_user["id"],))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"documents": rows}
