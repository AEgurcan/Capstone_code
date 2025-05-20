import os
import time
import threading
import asyncio
import hmac
import hashlib
import json
from urllib.parse import urlencode
from typing import List, Dict
import websockets
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
USE_TESTNET = os.getenv("USE_TESTNET", "False") == "True"

# Set REST and WebSocket endpoints based on environment
# For futures: REST at testnet.binancefuture.com or fapi.binance.com
# WS at fstream.binancefuture.com or fstream.binance.com
domain_rest = "https://testnet.binancefuture.com" if USE_TESTNET else "https://fapi.binance.com"
domain_ws = "wss://fstream.binancefuture.com" if USE_TESTNET else "wss://fstream.binance.com"

# --- Utility functions ---
def _get_server_time() -> int:
    """Fetch server time in milliseconds."""
    url = f"{domain_rest}/fapi/v1/time"
    r = httpx.get(url, timeout=5)
    r.raise_for_status()
    return r.json().get("serverTime")


def _signed_request(api_key: str, api_secret: str, path: str, params: dict) -> dict:
    """Make a signed request to REST API."""
    server_ts = _get_server_time()
    params["timestamp"] = server_ts
    params["recvWindow"] = 5000
    qs = urlencode(params, doseq=True)
    sig = hmac.new(api_secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
    url = f"{domain_rest}{path}?{qs}&signature={sig}"
    headers = {"X-MBX-APIKEY": api_key}
    resp = httpx.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


# --- Start & keepalive user data stream ---
def start_user_data_stream(api_key: str) -> str:
    """Start user data stream to get listenKey."""
    headers = {"X-MBX-APIKEY": api_key}
    url = f"{domain_rest}/fapi/v1/listenKey"
    r = httpx.post(url, headers=headers, timeout=5)
    r.raise_for_status()
    return r.json().get("listenKey")


def keepalive_user_data_stream(api_key: str, listen_key: str) -> None:
    """Keepalive user data stream."""
    headers = {"X-MBX-APIKEY": api_key}
    url = f"{domain_rest}/fapi/v1/listenKey"
    httpx.put(url, headers=headers, params={"listenKey": listen_key}, timeout=5)


# --- Public price WebSocket ---
class BinanceWS:
    def __init__(self):
        self.latest_prices: Dict[str, float] = {}
        threading.Thread(target=self._run, daemon=True).start()

    async def _listen(self):
        uri = (
            f"{domain_ws}/stream?streams="
            "btcusdt@markPrice/ethusdt@markPrice/"
            "bnbusdt@markPrice/solusdt@markPrice/"
            "xrpusdt@markPrice/adausdt@markPrice/"
            "avaxusdt@markPrice/dogeusdt@markPrice/"
            "dotusdt@markPrice/linkusdt@markPrice"
        )
        async with websockets.connect(uri) as ws:
            while True:
                msg = await ws.recv()
                d = json.loads(msg).get("data", {})
                if "s" in d and "p" in d:
                    self.latest_prices[d["s"]] = d["p"]

    def _run(self) -> None:
        asyncio.run(self._listen())


def get_binance_ws() -> BinanceWS:
    return BinanceWS()


# --- Private user WebSocket for account updates ---
class BinanceUserWS:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.positions: Dict[str, dict] = {}
        self.trade_history: List[dict] = []

        # Initial fetch
        self._refresh_positions()
        self._fetch_past_trades()

        # Start user data stream
        self.listen_key = start_user_data_stream(self.api_key)
        threading.Thread(target=self._run_stream, daemon=True).start()
        threading.Thread(target=self._refresh_loop, daemon=True).start()

    def _refresh_positions(self) -> None:
        """Fetch non-zero positions via REST API."""
        risks = _signed_request(self.api_key, self.api_secret, "/fapi/v2/positionRisk", {})
        new = {}
        for r in risks:
            amt = float(r.get("positionAmt", 0))
            if amt != 0:
                new[r["symbol"]] = {
                    "positionAmt": r["positionAmt"],
                    "entryPrice": r["entryPrice"],
                    "leverage": r["leverage"],
                    "unRealizedProfit": r.get("unRealizedProfit", ""),
                    "marginType": r.get("marginType", ""),
                    "liquidationPrice": r.get("liquidationPrice", ""),
                }
        self.positions = new

    def _fetch_past_trades(self) -> None:
        """Fetch recent trades for predefined symbols."""
        symbols = [
            "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT",
            "XRPUSDT","ADAUSDT","AVAXUSDT","DOGEUSDT",
            "DOTUSDT","LINKUSDT"
        ]
        for sym in symbols:
            try:
                trades = _signed_request(self.api_key, self.api_secret, "/fapi/v1/userTrades", {"symbol": sym, "limit": 500})
                for t in trades:
                    dt = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t.get("time",0)/1000))
                    self.trade_history.append({
                        "coin": t.get("symbol"),
                        "side": t.get("side"),
                        "quantity": t.get("qty"),
                        "price": t.get("price"),
                        "commission": f"{t.get('commission')} {t.get('commissionAsset')}",
                        "time": dt
                    })
            except Exception as e:
                print(f"⚠️ {sym} trade geçmişi alınamadı: {e}")

    def fetch_user_trades(self, symbol: str, startTime: int, endTime: int) -> List[dict]:
        return _signed_request(self.api_key, self.api_secret, "/fapi/v1/userTrades", {"symbol": symbol, "startTime": startTime, "endTime": endTime})

    def _refresh_loop(self) -> None:
        """Periodically refresh positions every 30 seconds."""
        while True:
            time.sleep(30)
            try:
                self._refresh_positions()
            except Exception as e:
                print(f"⚠️ Pozisyon yenileme hatası: {e}")

    async def _keepalive(self) -> None:
        """Send keepalive every 30 minutes."""
        while True:
            await asyncio.sleep(30 * 60)
            keepalive_user_data_stream(self.api_key, self.listen_key)

    async def _listen(self) -> None:
        """Listen to user account updates via WebSocket."""
        uri = f"{domain_ws}/ws/{self.listen_key}"
        async with websockets.connect(uri) as ws:
            await asyncio.create_task(self._keepalive())
            while True:
                msg = await ws.recv()
                ev = json.loads(msg)
                if ev.get("e") == "ACCOUNT_UPDATE":
                    for p in ev.get("a", {}).get("P", []):
                        sym = p.get("s")
                        amt = float(p.get("pa", 0))
                        if amt != 0:
                            old = self.positions.get(sym, {})
                            old.update({
                                "positionAmt": p.get("pa"),
                                "entryPrice": p.get("ep"),
                                "leverage": p.get("cr"),
                                "unRealizedProfit": p.get("up"),
                            })
                            self.positions[sym] = old
                        else:
                            self.positions.pop(sym, None)
                elif ev.get("e") == "ORDER_TRADE_UPDATE":
                    o = ev.get("o", {})
                    if o.get("x") == "TRADE":
                        dt = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(o.get("T",0)/1000))
                        self.trade_history.append({
                            "coin": o.get("s"),
                            "side": o.get("S"),
                            "quantity": o.get("q"),
                            "price": o.get("p"),
                            "time": dt
                        })

    def _run_stream(self) -> None:
        asyncio.run(self._listen())


def get_user_ws(api_key: str, api_secret: str) -> BinanceUserWS:
    return BinanceUserWS(api_key, api_secret)
