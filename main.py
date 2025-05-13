import os
from dotenv import load_dotenv

# .env yükleme
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

from fastapi import FastAPI, HTTPException, Depends, Header
from contextlib import asynccontextmanager
from auth import hash_password, verify_password, create_jwt_token, decode_jwt_token
from database import engine, Base, get_db
from pydantic import BaseModel
from models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from cryptography.fernet import Fernet, InvalidToken


KEY = os.getenv("FERNET_KEY").encode()
cipher = Fernet(KEY)

def encrypt_val(val: str) -> str:
    return cipher.encrypt(val.encode()).decode()

def decrypt_val(token: str) -> str:
    return cipher.decrypt(token.encode()).decode()


# Uygulama ayağa kalkarken tabloları yarat
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)

# --- Auth modelleri ---
class UserRegister(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class ApiKeyIn(BaseModel):
    api_key: str
    api_secret: str

# --- Kayıt ---
@app.post("/auth/register")
async def register(user: UserRegister, db: AsyncSession = Depends(get_db)):
    if not user.email.strip():
        raise HTTPException(400, "E-posta adresi boş olamaz!")
    res = await db.execute(select(User).where(User.email == user.email))
    if res.scalar_one_or_none():
        raise HTTPException(400, "Bu e-posta zaten kayıtlı.")
    new_user = User(
        email=user.email,
        hashed_password=hash_password(user.password)
    )
    db.add(new_user)
    await db.commit()
    return {"message": "Kullanıcı başarıyla kaydedildi!"}

# --- Giriş ---
@app.post("/auth/login")
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == user.email))
    db_user = res.scalar_one_or_none()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(401, "Geçersiz kimlik bilgisi")
    token = create_jwt_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}

# --- Mevcut kullanıcı bilgileri ---
@app.get("/user/me")
async def get_user_info(Authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    if not Authorization:
        raise HTTPException(401, "Token eksik!")
    scheme, _, token = Authorization.partition(" ")
    if not token:
        raise HTTPException(401, "Invalid token")
    data = decode_jwt_token(token)
    res = await db.execute(select(User).where(User.email == data["sub"]))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Kullanıcı bulunamadı!")
    return {
        "email": user.email,
        "created_at": str(user.created_at)
    }

# --- API Key/Get & Set ---
@app.post("/user/api-keys")
async def set_api_keys(
    payload: ApiKeyIn,
    Authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    if not Authorization:
        raise HTTPException(401, "Token eksik!")
    _, _, token = Authorization.partition(" ")
    data = decode_jwt_token(token)
    res = await db.execute(select(User).where(User.email == data["sub"]))
    user = res.scalar_one_or_none()
    """
    user.api_key = payload.api_key
    user.api_secret = payload.api_secret
    """
    # Ham değerleri şifrele
    user.api_key = encrypt_val(payload.api_key)
    user.api_secret = encrypt_val(payload.api_secret)
    db.add(user)
    await db.commit()
    return {"message": "API anahtarları güncellendi."}


@app.get("/user/api-keys")
async def get_api_keys(Authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    if not Authorization:
        raise HTTPException(401, "Token eksik!")
    _, _, token = Authorization.partition(" ")
    data = decode_jwt_token(token)
    res = await db.execute(select(User).where(User.email == data["sub"]))
    user = res.scalar_one_or_none()
    """
    return {
        "api_key":    user.api_key or "",
        "api_secret": user.api_secret or ""
    }
    """

    def try_decrypt(val: str) -> str:
        if not val:
            return ""
        try:
            return decrypt_val(val)
        except InvalidToken:
            # zaten şifrelenmemiş
            return val
    return {
        "api_key": try_decrypt(user.api_key or ""),
        "api_secret": try_decrypt(user.api_secret or "")
    }
from fastapi.responses import JSONResponse
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig

class PasswordResetRequest(BaseModel):
    email: str

class PasswordReset(BaseModel):
    token: str
    new_password: str

# --- SMTP Ayarı ---
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT")),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_STARTTLS=True,      
    MAIL_SSL_TLS=False,      
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)


@app.post("/auth/request-password-reset")
async def request_password_reset(req: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == req.email))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Kullanıcı bulunamadı")

    from datetime import timedelta
    reset_token = create_jwt_token({"sub": user.email}, expires_delta=timedelta(minutes=5))
    reset_link = f"http://localhost:8501/?reset_token={reset_token}"

    # E-posta içeriği
    message = MessageSchema(
        subject="Şifre Sıfırlama Talebi",
        recipients=[user.email],
        body=f"Şifrenizi sıfırlamak için aşağıdaki bağlantıya tıklayın:\n\n{reset_link}",
        subtype="plain"
    )
    fm = FastMail(conf)
    await fm.send_message(message)
    

    return {"message": "Şifre sıfırlama bağlantısı e-posta adresinize gönderildi."}

@app.post("/auth/reset-password")
async def reset_password(data: PasswordReset, db: AsyncSession = Depends(get_db)):
    print("🔐 TOKEN GELDİ:", data.token)
    try:
        payload = decode_jwt_token(data.token)
        print("✅ DECODE BAŞARILI:", payload)
    except Exception as e:
        print("❌ JWT HATASI:", str(e))
        raise HTTPException(400, "Geçersiz veya süresi dolmuş token")

    email = payload.get("sub")
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Kullanıcı bulunamadı")

    user.hashed_password = hash_password(data.new_password)
    db.add(user)
    await db.commit()

    return {"message": "Şifreniz başarıyla güncellendi."}

