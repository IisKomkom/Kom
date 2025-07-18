import os
import requests
import time
from threading import Lock

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'xxxx')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', 'yyyy')

# Untuk anti-spam: simpan waktu notifikasi terakhir per event
_last_sent = {}
_lock = Lock()

def send_telegram(message, tag=None, min_interval=300):
    """
    Kirim notifikasi ke Telegram, dengan anti-spam per tag.
    - tag: string unik untuk event (misal: 'login_failed', 'fatal_error')
    - min_interval: detik minimal antar notifikasi event yang sama
    """
    global _last_sent
    now = time.time()
    with _lock:
        if tag:
            last = _last_sent.get(tag, 0)
            if now - last < min_interval:
                # Skip notifikasi jika terlalu sering
                return
            _last_sent[tag] = now
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram token/chat_id belum diatur.")
        return
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    try:
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'})
        if resp.status_code != 200:
            print(f"Telegram error: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Telegram exception: {e}")

def send_batch_summary(success, failed, batch_type='Download', extra=''):
    msg = f"📦 <b>{batch_type} Batch Selesai</b>\n✅ Sukses: <b>{success}</b>\n❌ Gagal: <b>{failed}</b>"
    if extra:
        msg += f"\n{extra}"
    send_telegram(msg, tag=f'batch_{batch_type.lower()}')

def send_fatal_error(error_msg, context=''):
    msg = f"🔥 <b>Fatal Error</b> {context}\n<code>{error_msg}</code>"
    send_telegram(msg, tag='fatal_error', min_interval=600)

def send_login_failed(email):
    msg = f"⚠️ <b>Login gagal</b> untuk akun: <b>{email}</b>"
    send_telegram(msg, tag=f'login_failed_{email}', min_interval=900)

def send_limit_hit(email):
    msg = f"🚫 <b>Akun limit</b>: <b>{email}</b>"
    send_telegram(msg, tag=f'limit_{email}', min_interval=900) 