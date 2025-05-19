import asyncio, threading, time, hmac, hashlib, json, websockets, httpx

# Binance Futures REST/WebSocket endpoints
FAPI_REST = "https://fapi.binance.com"
FAPI_WS   = "wss://fstream.binance.com/ws"

def start_user_data_stream(api_key: str):
    headers = {"X-MBX-APIKEY": api_key}
    r = httpx.post(f"{FAPI_REST}/fapi/v1/listenKey", headers=headers, timeout=5)
    r.raise_for_status()
    return r.json()["listenKey"]

def keepalive_user_data_stream(api_key: str, listen_key: str):
    headers = {"X-MBX-APIKEY": api_key}
    httpx.put(f"{FAPI_REST}/fapi/v1/listenKey",
              headers=headers,
              params={"listenKey": listen_key},
              timeout=5)

class BinanceWS:
    def __init__(self):
        self.latest_prices = {}
        threading.Thread(target=self._run, daemon=True).start()

    async def _listen(self):
        uri = (
            "wss://fstream.binance.com/stream?streams="
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

    def _run(self):
        asyncio.run(self._listen())

def get_binance_ws():
    return BinanceWS()

class BinanceUserWS:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.positions = {}
        self.trade_history = []

        self._refresh_positions()
        self.listen_key = start_user_data_stream(self.api_key)
        threading.Thread(target=self._run_stream, daemon=True).start()
        threading.Thread(target=self._refresh_loop, daemon=True).start()

    def _refresh_positions(self):
        ts = int(time.time() * 1000)
        qs = f"timestamp={ts}"
        sig = hmac.new(self.api_secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
        url = f"{FAPI_REST}/fapi/v2/account?{qs}&signature={sig}"
        headers = {"X-MBX-APIKEY": self.api_key}
        r = httpx.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        new = {}
        for p in r.json().get("positions", []):
            if float(p.get("positionAmt", 0)) != 0:
                new[p["symbol"]] = p
        self.positions = new

    def _refresh_loop(self):
        while True:
            time.sleep(30)
            try:
                self._refresh_positions()
            except Exception as e:
                print("⚠ Pozisyon yenileme hatası:", e)

    async def _keepalive(self):
        while True:
            await asyncio.sleep(30 * 60)
            keepalive_user_data_stream(self.api_key, self.listen_key)

    async def _listen(self):
        async with websockets.connect(f"{FAPI_WS}/{self.listen_key}") as ws:
            asyncio.create_task(self._keepalive())
            while True:
                ev = json.loads(await ws.recv())
                evt = ev.get("e")
                if evt == "ACCOUNT_UPDATE":
                    for p in ev["a"].get("P", []):
                        sym = p["s"]
                        amt = float(p.get("positionAmt", 0))
                        if amt != 0:
                            self.positions[sym] = p
                        else:
                            self.positions.pop(sym, None)
                elif evt == "ORDER_TRADE_UPDATE":
                    o = ev["o"]
                    if o.get("x") == "TRADE":
                        self.trade_history.append({
                            "coin":     o["s"],
                            "side":     o["S"],
                            "quantity": o["q"],
                            "price":    o["p"],
                            "time":     o["T"]
                        })

    def _run_stream(self):
        asyncio.run(self._listen())

def get_user_ws(api_key: str, api_secret: str):
    return BinanceUserWS(api_key, api_secret)
