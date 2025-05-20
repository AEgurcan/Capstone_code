import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_async_session
from models import Prediction, User
from binance_trader import (
    get_position_amount,
    get_mark_price,
    send_binance_order,
    close_position,
    get_symbol_filters
)
from datetime import datetime, timedelta
import math
from decimal import Decimal, ROUND_DOWN

# Map each trading pair to its fixed quantity
PAIR_TO_FIXED_QTY = {
    "adausdt": 1000,
    "avaxusdt": 50,
    "bnbusdt": 3,
    "btcusdt": 0.01,
    "dogeusdt": 500,
    "dotusdt": 100,
    "ethusdt": 0.05,
    "linkusdt": 30,
    "solusdt": 10
}

def quantize_qty(qty: float, step: float) -> float:
    """
    Round down qty to the nearest multiple of step.
    """
    return float(Decimal(str(qty)).quantize(Decimal(str(step)), rounding=ROUND_DOWN))

async def trade_from_latest_prediction(user: User, trade_size_usdt: float):
    """
    Fetch the latest prediction (4h+1m old) and open/close positions
    using fixed quantities per symbol. Uses send_binance_order for open
    and close_position for closing existing positions.
    """
    session: AsyncSession = await get_async_session()
    try:
        print("🔍 [DEBUG] trade_from_latest_prediction called.")

        cutoff = datetime.utcnow() - timedelta(hours=4, minutes=1)
        result = await session.execute(
            select(Prediction)
            .where(Prediction.timestamp <= cutoff)
            .order_by(Prediction.timestamp.desc())
            .limit(1)
        )
        latest: Prediction = result.scalars().first()

        if not latest:
            print("[❌] No suitable prediction found.")
            return

        print(f"[✅] Processing signals from {latest.timestamp}...")

        for pair, raw_target in PAIR_TO_FIXED_QTY.items():
            sig = getattr(latest, f"{pair}_pred", None)
            if sig not in (-1, 0, 1):
                continue

            symbol = pair.upper()
            current_amt = await get_position_amount(
                user.api_key, user.api_secret, symbol
            )

            # ① Fetch price and exchange filters
            price = float(await get_mark_price(user.api_key, user.api_secret, symbol))
            filters = await get_symbol_filters(user.api_key, user.api_secret, symbol)
            step_size = float(filters.get("stepSize", 1))
            min_notional = float(filters.get("minNotional", 0))

            # ② Quantize the fixed target qty to stepSize
            qty = quantize_qty(raw_target, step_size)

            print(f"[DEBUG] {symbol}: price={price}, stepSize={step_size}, "
                  f"raw_target={raw_target}, final_qty={qty}")

            # ③ Skip if below stepSize or notional < minNotional
            if qty < step_size or qty * price < min_notional:
                print(f"[WARN] {symbol}: final_qty {qty} below stepSize or "
                      f"notional < minNotional ({min_notional}), skipping.")
                continue

            # ④ Execute based on signal
            if sig == 1 and current_amt == 0:
                # Open long
                await send_binance_order(
                    user.api_key, user.api_secret,
                    symbol, "BUY", qty
                )
            elif sig == -1 and current_amt == 0:
                # Open short
                await send_binance_order(
                    user.api_key, user.api_secret,
                    symbol, "SELL", qty
                )
            elif sig == 0 and current_amt != 0:
                # Close existing position
                # close_position handles reduceOnly logic internally
                await close_position(
                    user.api_key, user.api_secret,
                    symbol, abs(current_amt)
                )

        print("[🚀] All trades executed.")

    finally:
        await session.close()
