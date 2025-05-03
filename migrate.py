import sqlite3

conn = sqlite3.connect("capstone.db")
cursor = conn.cursor()
cursor.execute("ALTER TABLE users ADD COLUMN api_key TEXT")
cursor.execute("ALTER TABLE users ADD COLUMN api_secret TEXT")
conn.commit()
conn.close()
print("users tablosuna api_key ve api_secret sütunları eklendi.")
