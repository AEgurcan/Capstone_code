from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db
from models import User
from auth import hash_password, verify_password, create_jwt_token
from pydantic import BaseModel

app = FastAPI()

# === Pydantic modelleri ===
class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

# === Kayıt ===
@app.post("/auth/register")
async def register_user(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="E-posta zaten kayıtlı.")

    new_user = User(
        email=data.email,
        hashed_password=hash_password(data.password)
    )
    db.add(new_user)
    await db.commit()
    return {"message": "Kayıt başarılı."}

# === Giriş ===
@app.post("/auth/login")
async def login_user(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalars().first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Geçersiz e-posta veya şifre.")
    
    token = create_jwt_token({"sub": user.email})
    return {"access_token": token}

# === Test: kullanıcı verisi ===
@app.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"email": user.email, "api_key": user.api_key}
