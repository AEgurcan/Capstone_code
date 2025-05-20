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

# List of trading pairs to process
PAIR_KEYS = [
    "adausdt", "avaxusdt", "bnbusdt", "btcusdt",
    "dogeusdt", "dotusdt", "ethusdt", "linkusdt", "solusdt"
]

async def trade_from_latest_prediction(user: User, trade_size_usdt: float):
    """
    Reads the most recent prediction (after a 4h+1m delay) and executes
    MARKET orders on the appropriate TESTNET or PROD endpoint.
    trade_size_usdt defines how much USDT to risk per trade.
    """
    session: AsyncSession = await get_async_session()
    try:
        print("🔍 [DEBUG] trade_from_latest_prediction called.")

        # Calculate cutoff timestamp: 4 hours and 1 minute ago
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

        for pair in PAIR_KEYS:
            sig = getattr(latest, f"{pair}_pred")
            if sig not in (-1, 0, 1):
                continue

            symbol = pair.upper()
            current_amt = await get_position_amount(
                user.api_key, user.api_secret, symbol
            )

            # ① Fetch price and exchange filters
            price = float(await get_mark_price(user.api_key, user.api_secret, symbol))
            filters = await get_symbol_filters(user.api_key, user.api_secret, symbol)
            step = filters.get("stepSize")
            min_notional = filters.get("minNotional", 0)

            # ② Compute raw qty and adjust to stepSize precision
            precision = int(round(-math.log10(step), 0))
            raw_qty = trade_size_usdt / price
            qty_floor = math.floor(raw_qty * (10 ** precision)) / (10 ** precision)

            # ③ Ensure minNotional: compute minimum qty to satisfy NB*price >= min_notional
            min_qty = math.ceil((min_notional / price) / step) * step
            qty = max(qty_floor, min_qty)

            print(f"[DEBUG] {symbol}: price={price}, step={step}, raw_qty={raw_qty}, qty_floor={qty_floor}, min_qty={min_qty}, final_qty={qty}")

            # Skip if below stepSize or zero or notional < minNotional
            if qty < step or qty * price < min_notional:
                print(f"[WARN] {symbol}: final_qty {qty} below stepSize or notional < minNotional, skipping.")
                continue

            # ④ Execute based on signal
            if sig == 1 and current_amt == 0:
                await send_binance_order(
                    user.api_key, user.api_secret, symbol, "BUY", qty,
                )
            elif sig == -1 and current_amt == 0:
                await send_binance_order(
                    user.api_key, user.api_secret, symbol, "SELL", qty,
                    
                )
            elif sig == 0 and current_amt != 0:
                # Closing position: similar adjustments
                raw_close = abs(current_amt)
                close_floor = math.floor(raw_close * (10 ** precision)) / (10 ** precision)
                close_qty = max(close_floor, math.ceil((min_notional / price) / step) * step)
                if close_qty < step or close_qty * price < min_notional:
                    print(f"[WARN] {symbol}: close_qty {close_qty} below stepSize or notional < minNotional, skipping close.")
                    continue
                side = "SELL" if current_amt > 0 else "BUY"
                await send_binance_order(
                    user.api_key, user.api_secret, symbol, side, close_qty
                )

        print("[🚀] All trades executed.")

    finally:
        await session.close()
