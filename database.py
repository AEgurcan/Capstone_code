# database.py

import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# .env içindeki değişkenleri yüklüyoruz
load_dotenv()

# Çevre değişkenlerinden parçaları al
DB_USER     = os.getenv("DB_USER", "postgres_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST     = os.getenv("DB_HOST", "crypto-indicator-db.culmicy0av1x.us-east-1.rds.amazonaws.com")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "Crypto_Indicator_DB")

# Şifredeki özel karakterleri urlencode et
DB_PASSWORD_ENC = quote_plus(DB_PASSWORD)

# Tam connection string
DATABASE_URL = (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD_ENC}@"
    f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_size=5,
    max_overflow=10,
)

# Oturum üreticisi
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base model
Base = declarative_base()

# FastAPI dependency olarak kullanmak için:
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
from sqlalchemy.ext.asyncio import async_sessionmaker

# Otomatik async session üretici
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_async_session() -> AsyncSession:
    return async_session()
