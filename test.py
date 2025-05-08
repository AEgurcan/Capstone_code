# cd .venv\backend
# uvicorn main:app --reload

# cd .venv\frontend
# streamlit run streamlit_app.py

# lokal db için
# DATABASE_URL=sqlite+aiosqlite:///./capstone.db

# güncel db'yi özel karakterlere uyumlu hale getiren kod
# from urllib.parse import quote_plus
# print(quote_plus("(,2(hpK.6Ywz"))  # => %28%2C2%28hpK.6Ywz

"""
import bcrypt

# Veritabanından çektiğin hash
hashed_password = b"$2b$12$E6aPK5.efEwRVk572LIw0.kiN4mOOx9447kAbluDxePbruBVqZUMy"

# Giriş yaparken denediğin şifre (kayıt olurken ne girdiysen aynısını buraya yaz)
plain_password = b"berkay"

# Şifreyi doğrula
if bcrypt.checkpw(plain_password, hashed_password):
    print("Şifre DOĞRU!")
else:
    print("Şifre YANLIŞ!")
"""


"""
import sqlite3

conn = sqlite3.connect("capstone.db")
cursor = conn.cursor()

cursor.execute("SELECT email, hashed_password FROM users")  # Kullanıcıları getir
rows = cursor.fetchall()

for row in rows:
    print("E-posta:", row[0])
    print("Hashlenmiş Şifre:", row[1])

conn.close()


import sqlite3

conn = sqlite3.connect("capstone.db")
cursor = conn.cursor()

# Aynı e-posta ile birden fazla kayıt olup olmadığını kontrol et
cursor.execute("SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1")
duplicate_users = cursor.fetchall()

if duplicate_users:
    for email, count in duplicate_users:
        print(f"Fazladan kayıt bulunan e-posta: {email}, {count} adet")
        cursor.execute("DELETE FROM users WHERE email = ?", (email,))

    conn.commit()
    print("Fazla kayıtlar temizlendi.")

else:
    print("Fazla kayıt bulunamadı.")

conn.close()


import sqlite3

conn = sqlite3.connect("capstone.db")
cursor = conn.cursor()

# Boş e-posta kaydını sil
cursor.execute("DELETE FROM users WHERE email IS NULL OR email = ''")

conn.commit()
conn.close()

print("Boş e-posta içeren kayıtlar temizlendi.")
"""

"""
# migrate.py
import sqlite3

conn = sqlite3.connect("capstone.db")
cursor = conn.cursor()
cursor.execute("ALTER TABLE users ADD COLUMN api_key TEXT")
cursor.execute("ALTER TABLE users ADD COLUMN api_secret TEXT")
conn.commit()
conn.close()
print("users tablosuna api_key ve api_secret sütunları eklendi.")
"""


"""
import asyncio
from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def test_connection():
    # 1) percent-encode just your password
    pwd = quote_plus("(,2(hpK.6Ywz")  
    #    => "%28%2C2%28hpK.6Ywz"
    
    # 2) build the URL using a literal @ to separate password from host
    url = (
        f"postgresql+asyncpg://postgres_admin:{"7zzQ8o5g956jxvDz"}"
        "@crypto-indicator-db.culmicy0av1x.us-east-1.rds.amazonaws.com:5432/"
        "Crypto_Indicator_DB"
    )
    
    engine = create_async_engine(url, echo=True)
    async with engine.connect() as conn:
        now_val = await conn.scalar(text("SELECT now()"))
        print("Postgres time:", now_val)

    await engine.dispose()

asyncio.run(test_connection())
"""


"""
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key)
"""


# migrate_encrypt.py
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from dotenv import load_dotenv

# crypto.py içinde encrypt_val fonksiyonunuz var:
#import encrypt_val
# models.py içindeki User sınıfınız:
from models import User
from urllib.parse import quote_plus

# .env'i yükleyin ve FERNET_KEY ile DATABASE_URL olduğundan emin olun
# .env dosyanıza ekleyin:
#   FERNET_KEY=qPAGhQ-9Ub7v_zalso3ccSxMDBrx-MicQC758ZhB5EM=
#   DATABASE_URL=postgresql+asyncpg://...
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
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL tanımlı değil!")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def migrate():
    async with AsyncSessionLocal() as session:
        # ORM-select ile tüm User nesnelerini alın:
        result = await session.execute(select(User))
        users = result.scalars().all()  # artık u bir User objesi

        for u in users:
            updated = False

            # Daha önce encrypt edilmemiş api_key’ler:
            #if u.api_key and not u.api_key.startswith("gAAAA"):
               # u.api_key = encrypt_val(u.api_key)
                #updated = True

            # Aynı şekilde api_secret:
            #if u.api_secret and not u.api_secret.startswith("gAAAA"):
                #u.api_secret = encrypt_val(u.api_secret)
                #updated = True

            if updated:
                session.add(u)  # değişikliği işaretleyin

        await session.commit()
    await engine.dispose()
    print("✨ Tüm anahtarlar encrypt edilip güncellendi.")

if __name__ == "__main__":
    asyncio.run(migrate())
