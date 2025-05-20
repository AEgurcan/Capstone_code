import streamlit as st
import httpx
import urllib.parse
import time
import asyncio
import os
from dotenv import load_dotenv
from websocket_client import get_binance_ws, get_user_ws
import pandas as pd
from dotenv import load_dotenv
from websocket_client import get_binance_ws, get_user_ws
from database import get_async_session
from models import User
from background_jobs import start_user_loop, stop_user_loop
from sqlalchemy.future import select
from datetime import datetime
from prediction_trader import trade_from_latest_prediction


load_dotenv()  
USE_TESTNET = os.getenv("USE_TESTNET", "False") == "True"

st.set_page_config(layout="wide") # sayfanın geniş olmasını sağlıyor


# === Session State Initialize ===
if "token" not in st.session_state:
    st.session_state["token"] = ""
if "auth_page" not in st.session_state:
    st.session_state["auth_page"] = "login"
if "ws_client" not in st.session_state:
    st.session_state["ws_client"] = get_binance_ws()
if "page" not in st.session_state:
    st.session_state["page"] = "Market Data"
if "user_ws" not in st.session_state:
    st.session_state["user_ws"] = None
if "trading_active" not in st.session_state:
    st.session_state["trading_active"] = False

# .env dosyasını yukle
dotenv_path = os.path.join(os.path.dirname(__file__), "../backend/.env")
load_dotenv(dotenv_path)

BASE_URL = "http://localhost:8000"

# Eger URL'de reset_token varsa, sifre sifirlama ekranini goster

# 1) Eğer token query'de varsa ve geçerliyse, belleğe al

if "reset_token" not in st.session_state:
    query_params = st.query_params
    raw_token = query_params.get("reset_token")
    if raw_token:
        st.session_state["reset_token"] = urllib.parse.unquote(raw_token)

# 2) Artık sadece session_state üzerinden kontrol ederiz
reset_token = st.session_state.get("reset_token")




if reset_token:
    st.title("🔒 Şifre Sıfırlama")
    st.info("Lütfen yeni şifrenizi girin.")

    new_password = st.text_input("Yeni Şifre", type="password")
    confirm = st.text_input("Yeni Şifre (Tekrar)", type="password")

    if st.button("Şifreyi Güncelle"):
        if new_password != confirm:
            st.error("Şifreler uyuşmuyor.")
        elif len(new_password) < 6:
            st.warning("Şifre en az 6 karakter olmalı.")
        else:
            try:
                response = httpx.post(
                    f"{BASE_URL}/auth/reset-password",
                    json={
                        "token": reset_token,
                        "new_password": new_password
                    },
                    timeout=60
                )
                if response.status_code == 200:
                    st.success("Şifreniz başarıyla güncellendi! Giriş yapabilirsiniz.")
                    st.session_state.pop("reset_token", None)  # Token'ı bellekte tutma
                else:
                    st.error("Şifre güncellenemedi: " + response.text)
            except Exception as e:
                st.error(f"Hata oluştu: {e}")


    st.stop()  # Diğer giriş ekranlarını göstermemek için
    
# === Giriş yapılmamışsa, sidebar gizle ve login/register sayfası göster ===
if not st.session_state["token"]:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {display: none;}
        </style>
        """,
        unsafe_allow_html=True
    )

    if st.session_state["auth_page"] == "login":
        st.title("🔑 Capstone Projesi – Giriş")
        st.header("Kullanıcı Girişi")
        email = st.text_input("E-posta adresi", key="login_email")
        password = st.text_input("Şifre", type="password", key="login_password")

        col1, col_gap, col2 = st.columns([1, 0.001, 1])
        with col1:
            if st.button("Giriş Yap"):
                with httpx.Client() as client:
                    response = client.post(
                        f"{BASE_URL}/auth/login",
                        json={"email": email, "password": password}
                    )
                if response.status_code == 200:
                    st.session_state["token"] = response.json()['access_token']
                    st.success("Başarıyla giriş yaptınız!")
                    st.session_state["page"] = "Market Data"
                    st.rerun()
                else:
                    st.error(response.json().get("detail", "Hata oluştu."))

        with col2:
            if st.button("Kayıt Ol"):
                st.session_state["auth_page"] = "register"
                st.rerun()

        if st.button("Şifremi Unuttum"):
            st.session_state["auth_page"] = "reset_request"
            st.rerun()

    elif st.session_state["auth_page"] == "reset_request":
        st.title("🔐 Şifre Yenileme Talebi")
        st.info("E-posta adresinizi girin. Şifre yenileme bağlantısı gönderilecektir.")
        reset_email = st.text_input("E-posta Adresi")

        if st.button("Gönder"):
            if not reset_email.strip():
                st.error("Lütfen geçerli bir e-posta adresi girin.")
            else:
                try:
                    resp = httpx.post(
                        f"{BASE_URL}/auth/request-password-reset",
                        json={"email": reset_email},
                        timeout=60
                    )
                    if resp.status_code == 200:
                        st.success("Yenileme bağlantısı e-posta adresinize gönderildi!")
                    else:
                        st.error("Gönderilemedi: " + resp.text)
                except Exception as e:
                    st.error(f"Hata oluştu: {e}")

        if st.button("← Giriş Ekranına Dön"):
            st.session_state["auth_page"] = "login"
            st.rerun()


    elif st.session_state["auth_page"] == "register":
        st.title("🔑 Capstone Projesi – Kayıt Ol")
        st.header("Yeni Hesap Oluştur")
        email = st.text_input("E-posta adresi", key="register_email")
        password = st.text_input("Şifre", type="password", key="register_password")

        # Üç kolon: boşluğu neredeyse sıfıra çekmek için
        col1, col_gap, col2 = st.columns([1, 0.001, 1])
        with col1:
            if st.button("Kayıt Ol"):
                with httpx.Client() as client:
                    response = client.post(
                        f"{BASE_URL}/auth/register",
                        json={"email": email, "password": password},
                        timeout=5
                    )
                if response.status_code == 200:
                    st.success("Kayıt başarıyla oluşturuldu!")
                else:
                    # JSONDecodeError'tan kaçınmak için önce JSON mu diye deneyelim:
                    try:
                        body = response.json()
                        detail = body.get("detail") or str(body)
                    except ValueError:
                        # JSON değilse düz text olarak al
                        detail = response.text or f"Hata kodu: {response.status_code}"
                    st.error(detail)

        with col2:
            if st.button("Giriş Yap"):
                st.session_state["auth_page"] = "login"
                st.rerun()



# === Giriş yapıldıysa ===
else:
    menu = st.sidebar.radio("Menü", ["API Ayarları","Kullanıcı Bilgileri","Market Data"],
                            index=2 if st.session_state["page"] == "Market Data" else 1)

    # --- API Ayarları: Anahtar / Secret girilecek form ---
    if menu == "API Ayarları":
        st.header("📡 Binance API Ayarları")
        token = st.session_state["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # --- 1) Backend’den gerçek değeri oku ---
        resp = httpx.get(f"{BASE_URL}/user/api-keys", headers=headers, timeout=5)
        data = resp.json()
        raw_api_key = data.get("api_key", "")
        raw_api_secret = data.get("api_secret", "")


        # --- 2) Maskelme fonksiyonu ---
        def mask_key(k: str) -> str:
            if len(k) <= 4:
                return "*" * len(k)
            return k[:2] + "*" * (len(k) - 4) + k[-2:]


        # --- 3) Ekranda maskeli göster, ama değeri sakla ---
        st.text_input("Mevcut API Key", value=mask_key(raw_api_key), disabled=True)
        st.text_input("Mevcut API Secret", value=mask_key(raw_api_secret), disabled=True, type="password")

        st.markdown("---")
        st.write("### Yeni Anahtarlar (isteğe bağlı)")
        new_key = st.text_input("Yeni API Key", placeholder="Yapıştırın veya boş bırakın")
        new_secret = st.text_input("Yeni API Secret", placeholder="Yapıştırın veya boş bırakın", type="password")

        if st.button("Kaydet"):
            # Yeni girildiyse onu, yoksa eskisini kullan
            send_key = new_key if new_key else raw_api_key
            send_secret = new_secret if new_secret else raw_api_secret

            r = httpx.post(
                f"{BASE_URL}/user/api-keys",
                headers=headers,
                json={"api_key": send_key, "api_secret": send_secret},
                timeout=5
            )
            if r.status_code == 200:
                st.success("API anahtarınız başarıyla kaydedildi!")
                # user_ws’i sıfırla ki yeni anahtarla yeniden deneyelim
                st.session_state.pop("user_ws", None)
                st.rerun()
            else:
                st.error("Kaydedilemedi: " + r.text)


    elif menu == "Kullanıcı Bilgileri":
        st.header("Kullanıcı Bilgilerim")

        token = st.session_state["token"]
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            with httpx.Client() as client:
                response = client.get(f"{BASE_URL}/user/me", headers=headers)
            if response.status_code == 200:
                user_data = response.json()
                st.markdown(
                    f"""
                    <div style="background-color: #fff; border: 1px solid #ddd;
                                border-radius: 12px; padding: 20px; margin-bottom: 20px;
                                box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                        <p><strong>E-posta:</strong> {user_data['email']}</p>
                        <p><strong>Kayıt Tarihi:</strong> {user_data['created_at']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.error("Kullanıcı bilgileri alınamadı!")
        else:
            st.warning("Lütfen yeniden giriş yapın.")

        if st.button("Çıkış Yap"):
            st.session_state["token"] = ""
            st.session_state["auth_page"] = "login"
            st.session_state["page"] = "Market Data"
            st.rerun()

    
    
    async def handle_trading_button(trade_size_usdt: float):
        session = await get_async_session()
        try:
            token = st.session_state["token"]
            headers = {"Authorization": f"Bearer {token}"}
            resp = httpx.get(f"{BASE_URL}/user/me", headers=headers)
            if resp.status_code == 200:
                email = resp.json().get("email")
                result = await session.execute(select(User).where(User.email == email))
                user = result.scalar_one_or_none()
                if user:
                    if st.session_state["trading_active"]:
                        stop_user_loop(user.id)
                        st.session_state["trading_active"] = False
                    else:
                        start_user_loop(user, trade_size_usdt)
                        st.session_state["trading_active"] = True
                else:
                    st.error("Kullanıcı bulunamadı.")
        finally:
            await session.close()


    if menu == "Market Data":


        # Sayfa başlığı
        st.markdown("## Canlı Fiyatlar – Binance USDS Futures")

        trade_size_usdt = st.number_input(
            "Pozisyon Büyüklüğü (USDT):",
            min_value=1.0,
            value=10.0,
            step=1.0,
            help="Her işlemde kullanmak istediğiniz USDT miktarı"
        )

        


        # 1) Toggle button (calls your async start/stop logic)
        
        if st.button(
            ("🟢 Başlat" if not st.session_state["trading_active"] else "🔴 Durdur"),
            key="trade_toggle"
        ):
            asyncio.run(handle_trading_button(trade_size_usdt))


        # ======================
        # 0) Ortak CSS
        # ======================
        st.markdown(
            """
            <style>
            .ticker-container {
                display: flex; 
                gap: 15px; 
                justify-content: center; 
                flex-wrap: wrap; 
                margin-bottom: 15px;
            }
            .ticker-box {
                background-color: #fafafa; 
                border-radius: 8px; 
                padding: 6px 10px; 
                text-align: center; 
                box-shadow: 1px 1px 4px rgba(0,0,0,0.1); 
                min-width: 80px;
            }
            .small-ticker-label {
                color: #555; 
                font-size: 12px; 
                margin: 0; 
                font-weight: 600;
            }
            .small-ticker-price {
                color: #007bff; 
                font-size: 14px; 
                font-weight: 600; 
                margin: 0; 
                transition: all 0.3s ease-in-out;
            }
            /* Portföy */
            .portfolio-container {
                margin-top: 20px; 
                padding: 15px 20px; 
                border-radius: 10px; 
                background-color: #f0f2f6; 
                text-align: center; 
                box-shadow: 2px 2px 6px rgba(0,0,0,0.1);
            }
            .portfolio-title {
                font-size: 20px; 
                color: #333; 
                margin-bottom: 10px; 
                font-weight: 600;
            }
            .portfolio-value {
                font-size: 28px; 
                color: #007bff; 
                font-weight: bold; 
                margin-bottom: 8px;
            }
            .portfolio-changes {
                display: flex; 
                justify-content: center; 
                gap: 15px; 
                margin-top: 10px;
            }
            .change-box {
                background-color: #fff; 
                padding: 6px 8px; 
                border-radius: 8px; 
                box-shadow: 1px 1px 4px rgba(0,0,0,0.1); 
                min-width: 70px;
            }
            .change-label {
                font-size: 12px; 
                color: #666; 
                margin-bottom: 3px;
            }
            .change-value {
                font-size: 14px; 
                font-weight: bold;
            }
            /* Trade History */
            .trade-history {
                margin-top: 20px;
            }
            .trade-history h3 {
                font-size: 18px; 
                font-weight: 600; 
                margin-bottom: 8px;
            }
            table.trade-table {
                width: 100%; 
                border-collapse: collapse;
            }
            table.trade-table th, table.trade-table td {
                padding: 6px; 
                border: 1px solid #ddd; 
                text-align: left; 
                font-size: 12px;
            }
            table.trade-table th {
                background-color: #eee;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.session_state["page"] = "Market Data"

        if "trading_active" not in st.session_state:
            st.session_state["trading_active"] = False

        from background_jobs import start_user_loop, stop_user_loop
        from models import User
        from database import get_async_session
        from sqlalchemy.future import select   
        import asyncio 


        # ======================
        # 1) Ticker yukarıda gösterilsin
        # ======================
        # İki placeholder oluştur
        top_ph = st.empty()
        bot_ph = st.empty()

        # Pozisyon/trade placeholder’ları
        # Portföy için tek placeholder
        portfolio_ph = st.empty()
        trade_title_ph = st.empty()
        trade_body_ph = st.empty()

        # Takip ettiğimiz semboller:
        top_coins = {
            "BTCUSDT": "BTC/USDT",
            "ETHUSDT": "ETH/USDT",
            "BNBUSDT": "BNB/USDT",
            "SOLUSDT": "SOL/USDT",
            "XRPUSDT": "XRP/USDT",
        }
        bottom_coins = {
            "ADAUSDT": "ADA/USDT",
            "AVAXUSDT": "AVAX/USDT",
            "DOGEUSDT": "DOGE/USDT",
            "DOTUSDT": "DOT/USDT",
            "LINKUSDT": "LINK/USDT",
        }

        # ➊ Üst ve altı birleştiriyoruz
        all_coins = {**top_coins, **bottom_coins}
        

        def render_ticker(prices, coin_map):
            html = '<div class="ticker-container">'
            for sym, lbl in coin_map.items():
                raw = prices.get(sym)
                if raw is not None:
                    price = float(raw)
                    disp = f"${price:,.2f}"
                else:
                    disp = "N/A"
                html += (
                    f'<div class="ticker-box">'
                    f'  <p class="small-ticker-label">{lbl}</p>'
                    f'  <p class="small-ticker-price">{disp}</p>'
                    f'</div>'
                )
            html += "</div>"
            return html
        

        # 6) Portföy render fonksiyonu (positionAmt × currentPrice)
        def render_portfolio(positions, prices, coin_map):
            total = 0.0
            details = ""
            for sym, lbl in coin_map.items():
                amt = float(positions.get(sym, {}).get("positionAmt", 0))
                price = float(prices.get(sym, 0))
                val = amt * price
                total += val
                details += f"<div><strong>{lbl}:</strong> {amt} @ {price:,.2f} USD</div>"
            return (
                "<div class=\"portfolio-container\">"
                "<div class=\"portfolio-title\">Portföy Değeri</div>"
                f"<div class=\"portfolio-value\">${total:,.2f}</div>"
                f"<div class=\"portfolio-details\">{details}</div>"
                "</div>"
            )

        # ---- User Stream: Pozisyon & Trade History ----
        # 1) Backend’den gerçek API anahtarlarını al
        token = st.session_state["token"]
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = httpx.get(f"{BASE_URL}/user/api-keys", headers=headers, timeout=5)
            if resp.status_code != 200:
                st.error(f"Anahtarları alırken hata: {resp.status_code} {resp.text}")
                raw_api_key = raw_api_secret = ""
            else:
                data = resp.json()
                raw_api_key = data.get("api_key", "")
                raw_api_secret = data.get("api_secret", "")
        except (httpx.HTTPError, ValueError) as e:
            st.error(f"Anahtarları alırken beklenmedik hata: {e}")
            raw_api_key = raw_api_secret = ""

        # 2) Eğer daha önce user_ws oluşturulmadıysa ve anahtar varsa başlat
        if st.session_state["user_ws"] is None and raw_api_key:
            try:
                st.session_state["user_ws"] = get_user_ws(raw_api_key, raw_api_secret)
            except httpx.HTTPStatusError:
                st.error("Binance API anahtarlarınız geçersiz veya yetkisiz.")
                st.session_state["user_ws"] = None

        user_ws = st.session_state["user_ws"]
        

        st.markdown("## Pozisyon Geçmişi (Son 7 Gün)")
        hist_ph = st.empty()

        # 3) Sonsuz döngü — her 1 saniyede bir güncelle
        while True:
            # — Public ticker güncellemesi (her koşulda)
            prices = st.session_state["ws_client"].latest_prices
            # üst satır
            top_ph.markdown(
                render_ticker(prices, top_coins),
                unsafe_allow_html=True
            )
            # alt satır
            bot_ph.markdown(
                render_ticker(prices, bottom_coins),
                unsafe_allow_html=True
            )

            # — Kullanıcı stream’i varsa dinamik bölümleri güncelle
            if user_ws:
                portfolio_ph.markdown(
                    render_portfolio(user_ws.positions, prices, all_coins),
                    unsafe_allow_html=True
                )
            else:
                portfolio_ph.info("Portföy görmek için API anahtarlarınızı girin.")

            # — Açık Pozisyonlar / trade history —
            if user_ws:
                trade_title_ph.markdown("### Açık Pozisyonlar")

                rows = []
                for sym, pos in user_ws.positions.items():
                    amt = float(pos.get("positionAmt", 0))
                    if amt == 0:
                        continue

                    entry = float(pos.get("entryPrice", 0))
                    cur = float(prices.get(sym, 0))
                    notional = amt * cur
                    leverage = pos.get("leverage", "")
                    liq_price = pos.get("liquidationPrice") or ""
                    pnl = amt * (cur - entry)
                    pos_side = pos.get("positionSide", "")
                    margin_typ = pos.get("marginType", "")

                    if amt > 0:
                        pos_side = "LONG"
                    else:
                        pos_side = "SHORT"

                    rows.append({
                        "Coin": all_coins.get(sym, sym),
                        "Miktar": f"{amt:.4f}",
                        "Giriş Fiyatı": f"${entry:,.2f}",
                        "Mevcut Fiyat": f"${cur:,.2f}",
                        "Değer (USDT)": f"${notional:,.2f}",
                        "Kaldıraç": leverage,
                        "Margin Type": margin_typ,
                        "Position Side": pos_side,
                        "Liq. Fiyatı": f"${float(liq_price):,.2f}" if liq_price else "-",
                        "P&L": f"${pnl:,.2f}"
                    })

                if rows:
                    # Sırasıyla istediğin kolonları göster
                    df = pd.DataFrame(rows)[[
                        "Coin", "Miktar", "Giriş Fiyatı", "Mevcut Fiyat",
                        "Değer (USDT)", "Kaldıraç", "Margin Type",
                        "Position Side", "Liq. Fiyatı", "P&L"
                    ]]
                    # indexi gizleyip yazdır
                    trade_body_ph.dataframe(df, use_container_width=True)

                else:
                    trade_body_ph.info("Şu anda açık pozisyonunuz bulunmuyor.")
            else:
                trade_title_ph.empty()
                trade_body_ph.empty()
            if user_ws:
                now_ms = int(time.time() * 1000)
                seven_days_ago = now_ms - 7 * 24 * 3600 * 1000

                # ➋ Tüm semboller için trade’leri çek
                all_trades = []
                for sym in all_coins.keys():
                    try:
                        trades = user_ws.fetch_user_trades(sym,
                                                           startTime=seven_days_ago,
                                                           endTime=now_ms)
                        all_trades += trades
                    except Exception as e:
                        st.warning(f"{sym} trade geçmişi alınırken hata: {e}")

                # ➌ Chrono-sort
                all_trades.sort(key=lambda t: t["time"])

                # ➍ Pozisyon bazında grupla
                history = []
                # state: sym → (net_qty, open_ts, pnl_acc, comm_acc, open_dir)
                state = {}

                for t in all_trades:
                    sym = t["symbol"]
                    qty = float(t["qty"])
                    side = t["side"]  # "BUY" veya "SELL"
                    pnl = float(t.get("realizedPnl", 0))
                    comm = float(t.get("commission", 0))

                    # trade yönü LONG için +, SHORT için −
                    # hedge açıksa positionSide kullanacağız, yoksa side’a bakacağız
                    ps_api = t.get("positionSide")
                    if ps_api in ("LONG", "SHORT"):
                        # hedge modunda
                        sign = 1 if ps_api == "LONG" else -1
                    else:
                        # one-way modda, BUY→LONG, SELL→SHORT
                        sign = 1 if side == "BUY" else -1

                    net, open_ts, pnl_acc, comm_acc, open_dir = state.get(
                        sym, (0, None, 0, 0, None)
                    )

                    prev_net = net
                    net += sign * qty
                    pnl_acc += pnl
                    comm_acc += comm

                    # pozisyon açılışı
                    if prev_net == 0 and net != 0:
                        open_ts = t["time"]
                        open_dir = sign

                    # pozisyon kapanışı
                    if prev_net != 0 and net == 0 and open_ts is not None:
                        history.append({
                            "Coin": sym,
                            "PositionSide": "LONG" if open_dir > 0 else "SHORT",
                            "OpenTime": datetime.fromtimestamp(open_ts / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                            "CloseTime": datetime.fromtimestamp(t["time"] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                            "RealizedPnL": round(pnl_acc, 6),
                            "Commission": round(comm_acc, 6),
                        })
                        # reset for next
                        open_ts, pnl_acc, comm_acc, open_dir = None, 0, 0, None

                    state[sym] = (net, open_ts, pnl_acc, comm_acc, open_dir)

                if history:
                    df_hist = pd.DataFrame(history)[[
                        "Coin", "PositionSide", "OpenTime", "CloseTime", "RealizedPnL", "Commission"
                    ]]
                    hist_ph.dataframe(df_hist, use_container_width=True)
                else:
                    hist_ph.info("Son 7 gün içinde tamamlanmış pozisyonunuz yok.")
            else:
                hist_ph.info("Pozisyon geçmişini görmek için geçerli API anahtarlarınızı girin.")    

        time.sleep(1)
