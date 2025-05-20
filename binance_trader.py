import time
import hmac
import hashlib
import httpx
import urllib.parse
import os
from dotenv import load_dotenv
import math

# Load environment variables
load_dotenv()
USE_TESTNET = os.getenv("USE_TESTNET", "False") == "True"

# Set API base URL for testnet or prod
BASE_URL = "https://testnet.binancefuture.com" if USE_TESTNET else "https://fapi.binance.com"

# --- Signature Creator ---
def create_signature(query_string: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()

# --- Get lot size stepSize for symbol ---
async def get_symbol_step_size(api_key: str, api_secret: str, symbol: str) -> float:
    """Her coin için exchangeInfo'dan lot stepSize'ı döner ve doğru precision hesaplanır."""
    url = f"{BASE_URL}/fapi/v1/exchangeInfo?symbol={symbol}"
    headers = {"X-MBX-APIKEY": api_key}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    symbols = data.get("symbols", [])
    if not symbols:
        raise RuntimeError(f"Exchange info bulunamadı: {symbol}")
    info = symbols[0]
    for f in info.get("filters", []):
        if f.get("filterType") == "LOT_SIZE":
            return float(f.get("stepSize"))
    raise RuntimeError("stepSize bulunamadı")

# binance_trader.py içinde (get_symbol_step_size’ın yanına)
async def get_symbol_filters(api_key: str, api_secret: str, symbol: str) -> dict:
    """
    exchangeInfo’dan hem stepSize hem minNotional değerlerini getirir.
    """
    url = f"{BASE_URL}/fapi/v1/exchangeInfo?symbol={symbol}"
    headers = {"X-MBX-APIKEY": api_key}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        info = resp.json()["symbols"][0]

    out = {}
    for f in info["filters"]:
        if f["filterType"] == "LOT_SIZE":
            out["stepSize"] = float(f["stepSize"])
        elif f["filterType"] == "MIN_NOTIONAL":
            out["minNotional"] = float(f["notional"])
    return out



# --- Get current position amount ---
async def get_position_amount(api_key: str, api_secret: str, symbol: str) -> float:
    endpoint = "/fapi/v2/positionRisk"
    timestamp = int(time.time() * 1000)
    qs = f"symbol={symbol}&timestamp={timestamp}"
    sig = create_signature(qs, api_secret)
    url = f"{BASE_URL}{endpoint}?{qs}&signature={sig}"
    headers = {"X-MBX-APIKEY": api_key}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    for item in data:
        if item.get("symbol") == symbol:
            return float(item.get("positionAmt", 0))
    return 0.0

# --- Get mark price for symbol ---
async def get_mark_price(api_key: str, api_secret: str, symbol: str) -> float:
    endpoint = "/fapi/v1/premiumIndex"
    timestamp = int(time.time() * 1000)
    qs = f"symbol={symbol}&timestamp={timestamp}"
    sig = create_signature(qs, api_secret)
    url = f"{BASE_URL}{endpoint}?{qs}&signature={sig}"
    headers = {"X-MBX-APIKEY": api_key}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return float(data.get("markPrice", 0))

# --- Send Market Order ---
async def send_binance_order(api_key: str, api_secret: str, symbol: str, side: str, quantity: float):
    """
    Send a MARKET order, with fallbacks:
      - İlk olarak istenen quantity ile dener.
      - Precision hatasında integer miktara düşürür.
      - PERCENT_PRICE hatasında (testnet’te likidite yetersizse) güvenli şekilde atlar.
    """
    endpoint = "/fapi/v1/order"
    timestamp = int(time.time() * 1000)
    qty_to_try = quantity

    while True:
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": qty_to_try,
            "timestamp": timestamp
        }
        qs = urllib.parse.urlencode(params, doseq=True)
        sig = create_signature(qs, api_secret)
        url = f"{BASE_URL}{endpoint}?{qs}&signature={sig}"
        headers = {"X-MBX-APIKEY": api_key}

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers)
            data = resp.json()

        # Başarılı
        if resp.status_code == 200:
            print(f"[ORDER RESPONSE] {symbol} {side} qty={qty_to_try} → {data}")
            return data

        code = data.get("code")

        # 1) Precision hatası: tam sayıya düşürüp yeniden dene
        if code == -1111 and qty_to_try != int(qty_to_try):
            fallback = int(qty_to_try)
            print(f"[WARN] {symbol} precision error ({quantity}), retrying with integer qty={fallback}")
            qty_to_try = fallback
            continue

        # 2) PERCENT_PRICE hatası: testnet’te likidite yetersizliği demek,
        #    bunu atlayıp devam etmek için None dönüyoruz
        if code == -4131:
            print(f"[WARN] {symbol} {side}: PERCENT_PRICE filter limit, skipping order.")
            return None

        # Diğer hatalar: yükselt
        raise RuntimeError(f"Order failed: {data}")

# --- Close open position via reverse market order ---
async def close_position(api_key: str, api_secret: str, symbol: str, current_amt: float):
    side = "SELL" if current_amt > 0 else "BUY"
    quantity = abs(current_amt)
    return await send_binance_order(api_key, api_secret, symbol, side, quantity)
