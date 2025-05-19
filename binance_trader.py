import time
import hmac
import hashlib
import httpx
import urllib.parse

BINANCE_BASE_URL = "https://fapi.binance.com"

# --- Signature Creator ---
def create_signature(query_string: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()

# --- Get current position amount ---
async def get_position_amount(api_key: str, api_secret: str, symbol: str) -> float:
    endpoint = "/fapi/v2/positionRisk"
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = create_signature(query_string, api_secret)
    full_url = f"{BINANCE_BASE_URL}{endpoint}?{query_string}&signature={signature}"

    headers = {"X-MBX-APIKEY": api_key}
    async with httpx.AsyncClient() as client:
        resp = await client.get(full_url, headers=headers)
        data = resp.json()

    for item in data:
        if item["symbol"] == symbol:
            return float(item["positionAmt"])

    return 0.0

# --- Send Market Order ---
async def send_binance_order(api_key: str, api_secret: str, symbol: str, side: str, quantity: float):
    endpoint = "/fapi/v1/order"
    timestamp = int(time.time() * 1000)

    params = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": quantity,
        "timestamp": timestamp
    }

    query_string = urllib.parse.urlencode(params)
    signature = create_signature(query_string, api_secret)
    url = f"{BINANCE_BASE_URL}{endpoint}?{query_string}&signature={signature}"

    headers = {"X-MBX-APIKEY": api_key}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers)
        data = resp.json()

    if resp.status_code != 200:
        raise RuntimeError(f"Order failed: {data}")

    return data

# --- Close open position (via reverse order) ---
async def close_position(api_key: str, api_secret: str, symbol: str, current_amt: float):
    side = "SELL" if current_amt > 0 else "BUY"
    quantity = abs(current_amt)
    return await send_binance_order(api_key, api_secret, symbol, side, quantity)