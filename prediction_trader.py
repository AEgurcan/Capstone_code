import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_async_session
from models import Prediction, User
from binance_trader import send_binance_order, close_position, get_position_amount
from datetime import datetime, timedelta

PAIR_KEYS = [
    "adausdt", "avaxusdt", "bnbusdt", "btcusdt",
    "dogeusdt", "dotusdt", "ethusdt", "linkusdt", "solusdt"
]

POSITION_SIDE = {
    1: ("BUY", "LONG"),
    -1: ("SELL", "SHORT")
}


async def trade_from_latest_prediction(user: User):
    async with get_async_session() as session:
        # 1. Son tahmin verisini al (4 saatlik + 1 dakika gecikmeli)
        threshold = datetime.utcnow() - timedelta(hours=4, minutes=-1)
        result = await session.execute(
            select(Prediction).where(Prediction.timestamp <= threshold).order_by(Prediction.timestamp.desc()).limit(1)
        )
        latest = result.scalar_one_or_none()

        if not latest:
            print("[❌] Uygun prediction verisi bulunamadı.")
            return

        print(f"[✅] {latest.timestamp} zamanlı sinyaller işleniyor...")

        # 2. Coin başına emir işlemleri
        for pair in PAIR_KEYS:
            column = f"{pair}_pred"
            signal = getattr(latest, column, None)

            if signal is None:
                continue

            symbol = pair.upper()
            position_amt = await get_position_amount(user.api_key, user.api_secret, symbol, POSITION_SIDE.get(1)[1])
            
            if signal == 1:
                if position_amt == 0:
                    await send_binance_order(user.api_key, user.api_secret, symbol, *POSITION_SIDE[1], quantity=1)
            elif signal == -1:
                if position_amt == 0:
                    await send_binance_order(user.api_key, user.api_secret, symbol, *POSITION_SIDE[-1], quantity=1)
            elif signal == 0:
                if position_amt > 0:
                    await close_position(user.api_key, user.api_secret, symbol, POSITION_SIDE[1][1], quantity=position_amt)
                elif position_amt < 0:
                    await close_position(user.api_key, user.api_secret, symbol, POSITION_SIDE[-1][1], quantity=abs(position_amt))

        print("[🚀] Tüm işlemler tamamlandı.")
