import asyncio
from typing import Dict
from prediction_trader import trade_from_latest_prediction
from models import User

# Her kullanıcı için asyncio task'larını tutan sözlük
user_tasks: Dict[int, asyncio.Task] = {}

def start_user_loop(user: User):
    """
    Kullanıcının Binance hesabı için trade döngüsünü başlatır.
    4 saatte bir (ve 1 dakika sonra) prediction tablosunu okuyarak işlem yapar.
    """
    async def periodic_task():
        try:
            while True:
                now = asyncio.get_event_loop().time()
                delay_until_next_block = 4 * 60 * 60  # 4 saat
                one_minute = 60
                await asyncio.sleep(delay_until_next_block + one_minute)
                await trade_from_latest_prediction(user)
        except asyncio.CancelledError:
            print(f"[❌] Task iptal edildi: user_id={user.id}")
        except Exception as e:
            print(f"[⚠️] Task hata verdi (user_id={user.id}): {e}")

    # Aynı kullanıcı için tekrar başlatma
    if user.id in user_tasks:
        print(f"[ℹ️] Kullanıcı zaten çalışıyor: user_id={user.id}")
        return

    # Görevi başlat
    task = asyncio.create_task(periodic_task())
    user_tasks[user.id] = task
    print(f"[✅] Görev başlatıldı: user_id={user.id}")

def stop_user_loop(user_id: int):
    """
    Belirtilen kullanıcının trade döngüsünü durdurur.
    """
    task = user_tasks.get(user_id)
    if task and not task.done():
        task.cancel()
        print(f"[🛑] Görev durduruldu: user_id={user_id}")
    user_tasks.pop(user_id, None)
