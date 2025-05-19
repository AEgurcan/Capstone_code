import asyncio, threading, time, hmac, hashlib, json, websockets, httpx
from urllib.parse import urlencode
from typing import List, Dict

FAPI_REST = "https://fapi.binance.com"
FAPI_WS   = "wss://fstream.binance.com/ws"

def _get_server_time() -> int:
    r = httpx.get(f"{FAPI_REST}/fapi/v1/time", timeout=5)
    r.raise_for_status()
    return r.json()["serverTime"]

def _signed_request(api_key: str, api_secret: str, path: str, params: dict):
    server_ts = _get_server_time()
    params["timestamp"] = server_ts
    params["recvWindow"] = 5_000
    qs = urlencode(params)
    sig = hmac.new(api_secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
    url = f"{FAPI_REST}{path}?{qs}&signature={sig}"
    headers = {"X-MBX-APIKEY": api_key}
    resp = httpx.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def start_user_data_stream(api_key: str):
    headers = {"X-MBX-APIKEY": api_key}
    r = httpx.post(f"{FAPI_REST}/fapi/v1/listenKey", headers=headers, timeout=5)
    r.raise_for_status()
    return r.json()["listenKey"]

def keepalive_user_data_stream(api_key: str, listen_key: str):
    headers = {"X-MBX-APIKEY": api_key}
    httpx.put(f"{FAPI_REST}/fapi/v1/listenKey", headers=headers, params={"listenKey": listen_key}, timeout=5)

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
        self.past_trades = []

        self._refresh_positions()
        self._fetch_past_trades()
        self.listen_key = start_user_data_stream(self.api_key)

        threading.Thread(target=self._run_stream, daemon=True).start()
        threading.Thread(target=self._refresh_loop, daemon=True).start()

    def _refresh_positions(self):
        risks = _signed_request(self.api_key, self.api_secret, "/fapi/v2/positionRisk", {})
        new = {}
        for r in risks:
            if float(r.get("positionAmt", 0)) != 0:
                new[r["symbol"]] = {
                    "positionAmt": r["positionAmt"],
                    "entryPrice": r["entryPrice"],
                    "leverage": r["leverage"],
                    "unRealizedProfit": r["unRealizedProfit"],
                    "marginType": r["marginType"],
                    "liquidationPrice": r.get("liquidationPrice", ""),
                }
        self.positions = new

    def _fetch_past_trades(self):
        symbols = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","AVAXUSDT","DOGEUSDT","DOTUSDT","LINKUSDT"]
        for sym in symbols:
            try:
                trades = _signed_request(self.api_key, self.api_secret, "/fapi/v1/userTrades", {"symbol": sym, "limit": 500})
                for t in trades:
                    dt = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t["time"]/1000))
                    self.past_trades.append({
                        "Coin": t["symbol"],
                        "Side": t["side"],
                        "Miktar": t["qty"],
                        "Fiyat": t["price"],
                        "Komisyon": f'{t["commission"]} {t["commissionAsset"]}',
                        "Tarih": dt
                    })
            except Exception as e:
                print(f"⚠️ {sym} geçmiş trade alınamadı:", e)

    def fetch_user_trades(self, symbol: str, startTime: int, endTime: int) -> List[dict]:
        params = {"symbol": symbol, "startTime": startTime, "endTime": endTime}
        return _signed_request(self.api_key, self.api_secret, "/fapi/v1/userTrades", params)

    def _refresh_loop(self):
        while True:
            time.sleep(30)
            try:
                self._refresh_positions()
            except Exception as e:
                print("⚠️ Pozisyon yenileme hatası:", e)

    async def _keepalive(self):
        while True:
            await asyncio.sleep(30*60)
            keepalive_user_data_stream(self.api_key, self.listen_key)

    async def _listen(self):
        async with websockets.connect(f"{FAPI_WS}/{self.listen_key}") as ws:
            await asyncio.create_task(self._keepalive())
            while True:
                ev = json.loads(await ws.recv())
                if ev.get("e") == "ACCOUNT_UPDATE":
                    for p in ev["a"].get("P", []):
                        sym = p["s"]
                        amt = float(p["pa"])
                        if amt != 0:
                            old = self.positions.get(sym, {})
                            old["positionAmt"] = p["pa"]
                            old["entryPrice"] = p["ep"]
                            old["leverage"] = p["cr"]
                            old["unRealizedProfit"] = p["up"]
                            self.positions[sym] = old
                        else:
                            self.positions.pop(sym, None)
                elif ev.get("e") == "ORDER_TRADE_UPDATE":
                    o = ev["o"]
                    if o.get("x") == "TRADE":
                        dt = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(o["T"]/1000))
                        self.trade_history.append({
                            "coin":     o["s"],
                            "side":     o["S"],
                            "quantity": o["q"],
                            "price":    o["p"],
                            "time":     dt
                        })

    def _run_stream(self):
        asyncio.run(self._listen())

def get_user_ws(api_key: str, api_secret: str):
    return BinanceUserWS(api_key, api_secret)
