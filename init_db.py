# init_db.py
import asyncio
from database import Base, engine
from models import User, Strategy

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tablolar oluşturuldu.")


asyncio.run(create_tables())
