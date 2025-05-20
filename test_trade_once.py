# test_trade_once.py
import os
import asyncio
from dotenv import load_dotenv
from database import get_async_session
from sqlalchemy import select
from models import User
from prediction_trader import trade_from_latest_prediction

async def main():
    # 1) .env’den TESTNET ve API anahtarlarınızı yükleyin
    load_dotenv()

    # 2) Veritabanından kullanıcıyı bulun
    session = await get_async_session()
    try:
        TEST_EMAIL = "emrgrcn02@gmail.com"   # kendi test email’inizi buraya yazın
        result = await session.execute(select(User).where(User.email == TEST_EMAIL))
        user = result.scalar_one_or_none()

        if not user:
            print("❌ Kullanıcı bulunamadı:", TEST_EMAIL)
            return
        USE_TESTNET = os.getenv("USE_TESTNET", "False") == "True"
        if USE_TESTNET:
            user.api_key    = os.getenv("TESTNET_API_KEY")
            user.api_secret = os.getenv("TESTNET_API_SECRET")

        # 3) Trade miktarını belirleyin (USDT)
        trade_size_usdt = 15000.0

        # 4) Fonksiyonu doğrudan çağırın
        print(f"🔍 {user.email} için {trade_size_usdt} USDT ile test trade başlıyor...")
        await trade_from_latest_prediction(user, trade_size_usdt)
        print("✅ Test trade tamamlandı. Log’ları ve Testnet UI’ı kontrol edin.")

    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())
