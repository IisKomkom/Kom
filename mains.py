from flask import Flask, jsonify, Response, stream_with_context, request
import threading
import subprocess
import logging
import sys
import os
import time
from datetime import datetime
import glob
import pandas as pd

app = Flask(__name__)

def get_latest_logfile(log_dir='log'):
    log_files = glob.glob(os.path.join(log_dir, 'log_controller_*.txt'))
    if not log_files:
        return None
    return max(log_files, key=os.path.getmtime)

def get_latest_download_logfile(log_dir='log'):
    log_files = glob.glob(os.path.join(log_dir, 'log_controller_download_*.txt'))
    if not log_files:
        return None
    return max(log_files, key=os.path.getmtime)

def get_jumlah_buku(csv_path='data/csv/zlibrary_scraped_books.csv'):
    try:
        df = pd.read_csv(csv_path)
        total = len(df)
        uploaded = df['files_url_drive'].notna() & (df['files_url_drive'].astype(str).str.strip() != '')
        cover = df['cover_url_final'].notna() & (df['cover_url_final'].astype(str).str.strip() != '')
        downloaded = (df['download_status'] == 'done').sum() if 'download_status' in df.columns else 0
        failed = (df['download_status'] == 'failed').sum() if 'download_status' in df.columns else 0
        n_uploaded = uploaded.sum()
        n_cover = cover.sum()
        return {
            'total': total,
            'uploaded': int(n_uploaded),
            'cover': int(n_cover),
            'downloaded': int(downloaded),
            'failed': int(failed)
        }
    except Exception as e:
        return f"Error: {e}"

# Setup Logging
def setup_logging():
    os.makedirs("log", exist_ok=True)
    log_file = datetime.now().strftime("log/log_flask_controller_%Y-%m-%d_%H-%M-%S.txt")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file, 'w', 'utf-8')]
    )
    # Tambahkan StreamHandler ke root logger secara manual, tanpa set encoding
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(sh)
    logging.info("Flask Controller with Status & Retry started.")

# Hapus semua variabel dan mekanisme locking
# Hapus: pipeline_running, download_running, lock, dan semua with lock
# Hapus pengecekan pipeline_running/download_running di route /start_pipeline dan /start_download_controller
# Jalankan pipeline dan download controller langsung di thread baru tanpa pengecekan status

# API Routes
@app.route('/')
def home():
    jumlah_buku = get_jumlah_buku()
    log_file = get_latest_logfile()
    log_file_display = os.path.basename(log_file) if log_file else 'Tidak ada log pipeline.'
    download_log_file = get_latest_download_logfile()
    download_log_file_display = os.path.basename(download_log_file) if download_log_file else 'Tidak ada log download controller.'
    if isinstance(jumlah_buku, dict):
        buku_info = (
            f"Total: <b>{jumlah_buku['total']}</b> | "
            f"Uploaded: <b>{jumlah_buku['uploaded']}</b> | "
            f"Cover: <b>{jumlah_buku['cover']}</b> | "
            f"Downloaded: <b>{jumlah_buku['downloaded']}</b> | "
            f"Failed: <b>{jumlah_buku['failed']}</b>"
        )
    else:
        buku_info = jumlah_buku
    return f'''
    <html>
    <head>
        <title>Scraper Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f7f7fa; color: #222; margin:0; padding:0; }}
            .container {{ max-width: 600px; margin: 40px auto; background: #fff; border-radius: 12px; box-shadow: 0 2px 12px #0001; padding: 32px; }}
            h2 {{ margin-top:0; }}
            .btn {{ background: #4f8cff; color: #fff; border: none; border-radius: 6px; padding: 12px 28px; font-size: 1.1em; cursor: pointer; transition: background 0.2s; }}
            .btn:hover {{ background: #2563eb; }}
            .info {{ margin: 18px 0; font-size: 1.1em; }}
            pre#logbox {{ background: #181c2f; color: #e0e6f8; padding: 14px; border-radius: 8px; max-height: 320px; overflow:auto; font-size: 0.98em; margin-top: 0; }}
            .footer {{ margin-top: 32px; color: #888; font-size: 0.95em; text-align: center; }}
            a {{ color: #4f8cff; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            .logfile-label {{ color: #888; font-size: 0.97em; margin-bottom: 4px; }}
        </style>
    </head>
    <body>
    <div class="container">
        <h2>Scraper Dashboard</h2>
        <div class="info">Jumlah buku di database: {buku_info}</div>
        <form action="/start_pipeline" method="get" style="margin-bottom:12px;display:inline-block;">
            <button class="btn" type="submit">Start Pipeline</button>
        </form>
        <form action="/start_download_controller" method="get" style="margin-bottom:18px;display:inline-block;margin-left:10px;">
            <button class="btn" type="submit" style="background:#22c55e;">Start Download Controller</button>
        </form>
        <div class="info">Status pipeline: <span id="status">memuat...</span></div>
        <div class="info">Status download controller: <span id="download_status">memuat...</span></div>
        <div class="logfile-label">Log pipeline: <b>{log_file_display}</b></div>
        <div class="logfile-label">Log download controller: <b>{download_log_file_display}</b></div>
        <div style="margin:10px 0 8px 0; font-weight:500;">Log Terbaru (Realtime):</div>
        <pre id="logbox">Memuat log...</pre>
        <div class="footer">
            <a href="/status">Cek Status Pipeline</a> &bull; <a href="/log_poll" target="_blank">Lihat Log Penuh</a>
        </div>
        <div class="info" style="color:#eab308; font-size:1em; margin-top:10px;" id="warning_box"></div>
    </div>
    <script>
    function fetchLog() {{
        fetch('/log_poll').then(r => r.text()).then(txt => {{
            document.getElementById('logbox').textContent = txt;
            var logbox = document.getElementById('logbox');
            logbox.scrollTop = logbox.scrollHeight;
        }});
    }}
    setInterval(fetchLog, 1000);
    fetchLog();
    function fetchStatus() {{
        fetch('/status').then(r => r.json()).then(js => {{
            document.getElementById('status').textContent = js.pipeline_status;
            document.getElementById('download_status').textContent = js.download_status;
            if(js.pipeline_status === 'running' && js.download_status === 'running') {{
                document.getElementById('warning_box').textContent = '⚠️ Pipeline dan Download Controller berjalan bersamaan. Pastikan tidak terjadi konflik data!';
            }} else {{
                document.getElementById('warning_box').textContent = '';
            }}
        }});
    }}
    setInterval(fetchStatus, 2000);
    fetchStatus();
    </script>
    </body>
    </html>
    '''

@app.route('/log_poll')
def log_poll():
    log_file = get_latest_logfile()
    if not log_file:
        return "Tidak ada file log ditemukan."
    with open(log_file, encoding='utf-8') as f:
        lines = f.readlines()[-100:]
    return "\n".join(line.rstrip() for line in lines)

@app.route('/ping')
def ping():
    return jsonify({"status": "Server is Alive"})

@app.route('/start_pipeline', methods=['GET'])
def start_pipeline():
    def run_pipeline_with_retry():
        max_retry = 3
        delay_between_retry = 5
        for attempt in range(1, max_retry + 1):
            logging.info(f"🚀 Menjalankan controller.py - Attempt {attempt}/{max_retry}")
            process = subprocess.Popen(
                [sys.executable, "controller_api.py"],
                stdout=sys.stdout,
                stderr=sys.stderr
            )
            process.wait()
            if process.returncode == 0:
                logging.info("✅ Pipeline selesai sukses.")
                break
            else:
                logging.warning(f"❌ Pipeline gagal dengan exit code {process.returncode}.")
                if attempt < max_retry:
                    logging.info(f"🔄 Mencoba ulang dalam {delay_between_retry} detik...")
                    time.sleep(delay_between_retry)
                else:
                    logging.error(f"❌ Gagal setelah {max_retry} percobaan. Berhenti.")
    threading.Thread(target=run_pipeline_with_retry).start()
    return jsonify({"status": "Pipeline dimulai di background."})

@app.route('/start_download_controller', methods=['GET'])
def start_download_controller():
    def run_download_controller():
        max_retry = 3
        delay_between_retry = 5
        log_file = datetime.now().strftime("log/log_controller_download_%Y-%m-%d_%H-%M-%S.txt")
        for attempt in range(1, max_retry + 1):
            logging.info(f"🚀 Menjalankan controller_download.py - Attempt {attempt}/{max_retry}")
            with open(log_file, 'a', encoding='utf-8') as logf:
                process = subprocess.Popen(
                    [sys.executable, "controller_download.py"],
                    stdout=logf,
                    stderr=logf
                )
                process.wait()
            if process.returncode == 0:
                logging.info("✅ Download Controller selesai sukses.")
                break
            else:
                logging.warning(f"❌ Download Controller gagal dengan exit code {process.returncode}.")
                if attempt < max_retry:
                    logging.info(f"🔄 Mencoba ulang dalam {delay_between_retry} detik...")
                    time.sleep(delay_between_retry)
                else:
                    logging.error(f"❌ Gagal setelah {max_retry} percobaan. Berhenti.")
    threading.Thread(target=run_download_controller).start()
    return jsonify({"status": "Download Controller dimulai di background."})

@app.route('/status')
def status():
    return jsonify({
        "pipeline_status": "unknown",
        "download_status": "unknown"
    })

if __name__ == '__main__':
    setup_logging()
    app.run(host='0.0.0.0', port=8089)
