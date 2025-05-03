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

        resp = httpx.get(f"{BASE_URL}/user/api-keys", headers=headers, timeout=5)
        data = resp.json()
        api_key = st.text_input("API Key", value=data.get("api_key", ""))
        api_secret = st.text_input("API Secret", value=data.get("api_secret", ""), type="password")

        if st.button("Kaydet"):
            payload = {"api_key": api_key, "api_secret": api_secret}
            r = httpx.post(f"{BASE_URL}/user/api-keys", headers=headers, json=payload, timeout=5)
            if r.status_code == 200:
                st.success("API anahtarınız kaydedildi!")
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

    elif menu == "Market Data":
        st.session_state["page"] = "Market Data"
        st.markdown("## Canlı Fiyatlar – Binance USDS Futures")

        # Burada uzun WebSocket & canlı fiyat izleme kodları yer alıyor
        # Onları sen zaten göndermiştin, burada herhangi bir değişiklik yapılmadı.
