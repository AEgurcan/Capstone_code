# cd .venv\backend
# uvicorn main:app --reload

# cd .venv\frontend
# streamlit run streamlit_app.py

# lokal db için
# DATABASE_URL=sqlite+aiosqlite:///./capstone.db

# güncel db'yi özel karakterlere uyumlu hale getiren kod
# from urllib.parse import quote_plus
# print(quote_plus("(,2(hpK.6Ywz"))  # => %28%2C2%28hpK.6Ywz

"""
import bcrypt

# Veritabanından çektiğin hash
hashed_password = b"$2b$12$E6aPK5.efEwRVk572LIw0.kiN4mOOx9447kAbluDxePbruBVqZUMy"

# Giriş yaparken denediğin şifre (kayıt olurken ne girdiysen aynısını buraya yaz)
plain_password = b"berkay"

# Şifreyi doğrula
if bcrypt.checkpw(plain_password, hashed_password):
    print("Şifre DOĞRU!")
else:
    print("Şifre YANLIŞ!")


import sqlite3

conn = sqlite3.connect("capstone.db")
cursor = conn.cursor()

cursor.execute("SELECT email, hashed_password FROM users")  # Kullanıcıları getir
rows = cursor.fetchall()

for row in rows:
    print("E-posta:", row[0])
    print("Hashlenmiş Şifre:", row[1])

conn.close()


import sqlite3

conn = sqlite3.connect("capstone.db")
cursor = conn.cursor()

# Aynı e-posta ile birden fazla kayıt olup olmadığını kontrol et
cursor.execute("SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1")
duplicate_users = cursor.fetchall()

if duplicate_users:
    for email, count in duplicate_users:
        print(f"Fazladan kayıt bulunan e-posta: {email}, {count} adet")
        cursor.execute("DELETE FROM users WHERE email = ?", (email,))

    conn.commit()
    print("Fazla kayıtlar temizlendi.")

else:
    print("Fazla kayıt bulunamadı.")

conn.close()


import sqlite3

conn = sqlite3.connect("capstone.db")
cursor = conn.cursor()

# Boş e-posta kaydını sil
cursor.execute("DELETE FROM users WHERE email IS NULL OR email = ''")

conn.commit()
conn.close()

print("Boş e-posta içeren kayıtlar temizlendi.")
"""


# migrate.py
import sqlite3

conn = sqlite3.connect("capstone.db")
cursor = conn.cursor()
cursor.execute("ALTER TABLE users ADD COLUMN api_key TEXT")
cursor.execute("ALTER TABLE users ADD COLUMN api_secret TEXT")
conn.commit()
conn.close()
print("users tablosuna api_key ve api_secret sütunları eklendi.")
