import asyncio
from datetime import datetime, timedelta
from typing import Dict
from prediction_trader import trade_from_latest_prediction
from models import User

# Kullanıcıya ait asyncio task'larını tutan sözlük
user_tasks: Dict[int, asyncio.Task] = {}

def start_user_loop(user: User, trade_size_usdt: float):
    """
    Kullanıcının Binance hesabı için trade döngüsünü başlatır.
    Her gün 00:01, 04:01, 08:01, 12:01, 16:01, 20:01 saatlerinde prediction tablosunu okuyarak işlem yapar.
    """
    async def periodic_task():
        # İlk tetik zamanını hesapla
        now = datetime.now()
        block = (now.hour // 4) + 1
        next_hour = (block * 4) % 24
        next_run = now.replace(hour=next_hour, minute=1, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        # İlk uyku: bir sonraki 4h+1dk noktasına kadar bekle
        initial_delay = (next_run - now).total_seconds()
        await asyncio.sleep(initial_delay)

        # Döngü: her 4 saatte bir tetikle
        while True:
            try:
                await trade_from_latest_prediction(user, trade_size_usdt)
            except asyncio.CancelledError:
                print(f"[❌] Task iptal edildi: user_id={user.id}")
                break
            except Exception as e:
                print(f"[⚠️] Task hata verdi (user_id={user.id}): {e}")

            # Bir sonraki çalıştırma için 4 saat bekle
            await asyncio.sleep(4 * 3600)

    # Aynı kullanıcı için tekrar başlatma kontrolü
    if user.id in user_tasks:
        print(f"[ℹ️] Kullanıcı zaten çalışıyor: user_id={user.id}")
        return

    # Görevi başlat ve kaydet
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
