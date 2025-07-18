import subprocess
import time
import pandas as pd
import config
import logging
import os
import requests
from notify import send_fatal_error

# Setup dedicated log file for controller
os.makedirs('log', exist_ok=True)
log_file = 'log/controller_download.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, 'a', 'utf-8'),
        logging.StreamHandler()
    ]
)

CSV_PATH = config.OUTPUT_FILENAME
DOWNLOAD_SCRIPT = 'download_file.py'
UPLOAD_SCRIPT = 'test_rclone_upload.py'
BATCH_SIZE = 10
CHECK_INTERVAL = 30  # detik
MAX_PARALLEL_UPLOADS = 5  # <--- Pengaturan: jumlah proses upload paralel maksimum

API_URL = config.API_URL
REQUIRED_FIELDS = [
    'id', 'files_url_drive'
]

def start_download():
    logging.info("Menjalankan proses download_file.py ...")
    return subprocess.Popen(['python', DOWNLOAD_SCRIPT])

def start_upload():
    logging.info("Menjalankan proses upload batch ke Google Drive ...")
    return subprocess.Popen(['python', UPLOAD_SCRIPT])

def main():
    download_proc = start_download()
    upload_procs = []
    try:
        while True:
            if not os.path.exists(CSV_PATH):
                logging.warning(f"CSV {CSV_PATH} belum ada. Menunggu ...")
                time.sleep(CHECK_INTERVAL)
                continue
            df = pd.read_csv(CSV_PATH)
            mask = (df['download_status'] == 'done') & (
                (df['files_url_drive'].isna()) | (df['files_url_drive'].astype(str).str.strip() == '')
            )
            to_upload = df[mask]
            logging.info(f"{len(to_upload)} file siap upload (belum diupload). {len(upload_procs)} upload aktif.")
            # Bersihkan upload_procs yang sudah selesai
            finished_uploads = [p for p in upload_procs if p.poll() is not None]
            for p in finished_uploads:
                # Setelah upload batch selesai, update database untuk file yang sudah diupload
                df2 = pd.read_csv(CSV_PATH)
                uploaded_mask = (df2['download_status'] == 'done') & (df2['files_url_drive'].notna()) & (df2['files_url_drive'].astype(str).str.strip() != '')
                to_update = df2[uploaded_mask]
                # update_database_via_api(to_update.to_dict('records')) # Removed as per edit hint
                pass  # Notifikasi batch upload sudah di test_rclone_upload.py
            upload_procs = [p for p in upload_procs if p.poll() is None]
            # Selama masih boleh paralel, dan batch tersedia, jalankan upload baru
            while len(to_upload) >= BATCH_SIZE and len(upload_procs) < MAX_PARALLEL_UPLOADS:
                upload_proc = start_upload()
                upload_procs.append(upload_proc)
                to_upload = to_upload.iloc[BATCH_SIZE:]
            # Restart download jika mati
            if download_proc.poll() is not None:
                logging.warning("Proses download_file.py mati. Restart ...")
                download_proc = start_download()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logging.info("Controller dihentikan oleh user.")
        if download_proc: download_proc.terminate()
        for p in upload_procs:
            p.terminate()
    except Exception as e:
        logging.error(f"Fatal error in controller_download.py: {e}")
        send_fatal_error(str(e), context='controller_download.py')

if __name__ == '__main__':
    main() 