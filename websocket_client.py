import asyncio
import threading
import websockets
import json
import httpx
import os

# ——— Public Ticker WebSocket ———

class BinanceWS:
    def __init__(self):
        self.latest_prices = {}
        self._start_ws_thread()

    async def _listen(self):
        # Combined stream URL: tüm coinlerin stream isimleri tamamen küçük harflerle olmalı.
        uri = ("wss://fstream.binance.com/stream?streams="
               "btcusdt@markPrice/ethusdt@markPrice/bnbusdt@markPrice/"
               "solusdt@markPrice/xrpusdt@markPrice/adausdt@markPrice/"
               "avaxusdt@markPrice/dogeusdt@markPrice/dotusdt@markPrice/linkusdt@markPrice")
        async with websockets.connect(uri) as ws:
            while True:
                try:
                    message = await ws.recv()
                    data = json.loads(message)
                    # Combined stream mesajları: {"stream": "<streamName>", "data": { ... }}
                    if "data" in data:
                        data = data["data"]
                    if "s" in data and "p" in data:
                        self.latest_prices[data["s"]] = data["p"]
                        print(f"Received {data['s']} price: {data['p']}")
                except Exception as e:
                    print("WebSocket error:", e)
                    break

    def _start_ws_thread(self):
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        asyncio.run(self._listen())


def get_binance_ws():
    return BinanceWS()


# ——— User Data Stream WebSocket ———

FAPI_REST = "https://fapi.binance.com"
FAPI_WS = "wss://fstream.binance.com/ws"

def start_user_data_stream(api_key: str):
    headers = {"X-MBX-APIKEY": api_key}
    r = httpx.post(f"{FAPI_REST}/fapi/v1/listenKey", headers=headers, timeout=5)
    r.raise_for_status()
    return r.json()["listenKey"]

def keepalive_user_data_stream(api_key: str, listen_key: str):
    headers = {"X-MBX-APIKEY": api_key}
    httpx.put(
        f"{FAPI_REST}/fapi/v1/listenKey",
        headers=headers,
        params={"listenKey": listen_key},
        timeout=5
    )

class BinanceUserWS:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.listen_key = start_user_data_stream(api_key)
        self.positions = {}
        self.trade_history = []
        self._start()

    async def _keepalive(self):
        while True:
            await asyncio.sleep(30*60)
            keepalive_user_data_stream(self.api_key, self.listen_key)

    async def _listen(self):
        uri = f"{FAPI_WS}/{self.listen_key}"
        async with websockets.connect(uri) as ws:
            # keepalive’i schedule et
            _task = asyncio.create_task(self._keepalive())
            while True:
                msg = await ws.recv()
                ev  = json.loads(msg)
                e   = ev.get("e")
                if e == "ACCOUNT_UPDATE":
                    for p in ev["a"].get("P", []):
                        self.positions[p["s"]] = p
                elif e == "ORDER_TRADE_UPDATE":
                    o = ev["o"]
                    if o.get("x") == "TRADE":
                        self.trade_history.append({
                            "coin":     o["s"],
                            "side":     o["S"],
                            "quantity": o["q"],
                            "price":    o["p"],
                            "time":     o["T"]
                        })

    def _start(self):
        threading.Thread(target=lambda: asyncio.run(self._listen()), daemon=True).start()

def get_user_ws(api_key: str, api_secret: str):
    return BinanceUserWS(api_key, api_secret)
