import streamlit as st
import httpx
import time
import os
from dotenv import load_dotenv
from websocket_client import get_binance_ws, get_user_ws

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

dotenv_path = os.path.join(os.path.dirname(__file__), "../backend/.env")
load_dotenv(dotenv_path)

BASE_URL = "http://localhost:8000"

# === Giriş yapılmamışsa ===
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

    elif st.session_state["auth_page"] == "register":
        st.title("🔑 Capstone Projesi – Kayıt Ol")
        st.header("Yeni Hesap Oluştur")
        email = st.text_input("E-posta adresi", key="register_email")
        password = st.text_input("Şifre", type="password", key="register_password")

        col1, col_gap, col2 = st.columns([1, 0.001, 1])
        with col1:
            if st.button("Kayıt Ol"):
                try:
                    with httpx.Client() as client:
                        response = client.post(
                            f"{BASE_URL}/auth/register",
                            json={"email": email, "password": password}
                        )
                    if response.status_code == 200:
                        st.success("Kayıt başarıyla oluşturuldu!")
                    else:
                        try:
                            detail = response.json().get("detail", "Bir hata oluştu.")
                        except Exception:
                            detail = f"Geçersiz yanıt: {response.text}"
                        st.error(detail)
                except Exception as e:
                    st.error(f"Sunucuya bağlanırken hata oluştu: {str(e)}")

        with col2:
            if st.button("Giriş Yap"):
                st.session_state["auth_page"] = "login"
                st.rerun()

# === Giriş yapıldıysa ===
else:
    menu = st.sidebar.radio("Menü", ["API Ayarları", "Kullanıcı Bilgileri", "Market Data"],
                            index=2 if st.session_state["page"] == "Market Data" else 1)

    if menu == "API Ayarları":
        st.header("📡 Binance API Ayarları")
        token = st.session_state["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Mevcut değerleri al
        resp = httpx.get(f"{BASE_URL}/user/api-keys", headers=headers, timeout=5)
        data = resp.json()
        api_key = st.text_input("API Key",    value=data.get("api_key",""))
        api_secret = st.text_input("API Secret", value=data.get("api_secret",""), type="password")

        if st.button("Kaydet"):
            payload = {"api_key": api_key, "api_secret": api_secret}
            r = httpx.post(f"{BASE_URL}/user/api-keys", headers=headers, json=payload, timeout=5)
            if r.status_code == 200:
                st.success("API anahtarınız kaydedildi!")
                st.rerun()
            else:
                st.error("Kaydedilemedi: "+r.text)

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

    elif menu == "Market Data":
        st.session_state["page"] = "Market Data"

        # Sayfa başlığı
        st.markdown("## Canlı Fiyatlar – Binance USDS Futures")

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

        # ======================
        # 1) Ticker yukarıda gösterilsin
        # ======================
        ticker_placeholder = st.empty()
        # Pozisyon/trade placeholder’ları
        port_ph = st.empty()
        trade_title_ph = st.empty()
        trade_body_ph = st.empty()

        # Takip ettiğimiz semboller:
        small_coin_map = {
            "BTCUSDT": "BTC/USDT",
            "ETHUSDT": "ETH/USDT",
            "BNBUSDT": "BNB/USDT",
            "SOLUSDT": "SOL/USDT",
            "XRPUSDT": "XRP/USDT"
        }

        def render_ticker(prices):
            """Her saniye güncellenecek Ticker HTML'ini oluşturur."""
            small_coin_map = {
                "BTCUSDT": "BTC/USDT",
                "ETHUSDT": "ETH/USDT",
                "BNBUSDT": "BNB/USDT",
                "SOLUSDT": "SOL/USDT",
                "XRPUSDT": "XRP/USDT"
            }
            # Eğer websocketten bir coin verisi gelmezse "N/A" gösterilsin
            ticker_html = '<div class="ticker-container">'
            for symbol, short_label in small_coin_map.items():
                raw_price = prices.get(symbol)  # dict.get() -> None if not found
                if raw_price is not None:
                    price_float = float(raw_price)
                    formatted_price = f"${price_float:,.2f}"
                else:
                    formatted_price = "N/A"

                # Ticker kutusu
                ticker_html += (
                    f'<div class="ticker-box">'
                    f'<p class="small-ticker-label">{short_label}</p>'
                    f'<p class="small-ticker-price">{formatted_price}</p>'
                    f'</div>'
                )
            ticker_html += "</div>"
            return ticker_html

        # 6) Portföy render fonksiyonu (positionAmt × currentPrice)
        def render_portfolio(positions, prices):
            total = 0.0
            details = ""
            for sym, lbl in small_coin_map.items():
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
        if not st.session_state["user_ws"]:
            # eğer henüz yoksa kullanıcıdan al
            # backend’den kaydedilmiş keyleri çekip kur
            token = st.session_state["token"]
            headers = {"Authorization": f"Bearer {token}"}
            r = httpx.get(f"{BASE_URL}/user/api-keys", headers=headers, timeout=5)
            d = r.json()
            if d.get("api_key") and d.get("api_secret"):
                st.session_state["user_ws"] = get_user_ws(d["api_key"], d["api_secret"])
            else:
                # st.warning("Lütfen önce API Ayarları sayfasından anahtarlarınızı kaydedin.")
                # st.stop()
                # yoksa boş geç
                st.session_state["user_ws"] = None


        user_ws = st.session_state["user_ws"]

        # 3) Sonsuz döngü — her 1 saniyede bir güncelle
        while True:
            # — Public ticker güncellemesi (her koşulda)
            prices = st.session_state["ws_client"].latest_prices
            ticker_placeholder.markdown(render_ticker(prices), unsafe_allow_html=True)

            # — Kullanıcı stream’i varsa dinamik bölümleri güncelle
            if user_ws:
                # — Portföy güncelle
                port_ph.markdown(
                    render_portfolio(user_ws.positions, prices),
                    unsafe_allow_html=True
                )
            else:
                port_ph.info("Portföy görmek için API anahtarlarınızı girin.")

            # — Açık pozisyonlar / trade history
            if user_ws:
                trades = user_ws.trade_history[-99:]
                trade_title_ph.markdown("### Açık Pozisyonlar")
                if trades:
                    trade_body_ph.table(trades)
                else:
                    trade_body_ph.info("Şu anda açık pozisyonunuz bulunmuyor.")
            else:
                trade_title_ph.empty()
                trade_body_ph.empty()

            time.sleep(1)
