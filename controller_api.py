import subprocess
import logging
import sys
import os
import time
from datetime import datetime
import csv
import requests
import config  # import config.py
import pandas as pd

# --- Logging Setup (from controller.py) ---
def setup_logging():
    os.makedirs("log", exist_ok=True)
    log_file = datetime.now().strftime("log/log_controller_%Y-%m-%d_%H-%M-%S.txt")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, 'w', 'utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("Controller with Real-Time Output + Retry started.")
    return log_file

# --- Run Script with Retry and Stream (from controller.py) ---
def run_script_with_retry_and_stream(script_name, log_path, max_retry=3, delay_between_retry=5):
    for attempt in range(1, max_retry + 1):
        logging.info(f"Menjalankan {script_name} - Attempt {attempt}/{max_retry}")
        with open(log_path, 'a', encoding='utf-8') as logf:
            process = subprocess.Popen(
                [sys.executable, script_name],
                stdout=logf,
                stderr=logf
            )
            process.wait()

        if process.returncode == 0:
            logging.info(f"✅ {script_name} selesai sukses.")
            return True
        else:
            logging.warning(f"❌ {script_name} gagal dengan exit code {process.returncode}.")
            if attempt == max_retry:
                logging.error(f"❌ {script_name} gagal setelah {max_retry} percobaan. Pipeline dihentikan.")
                return False
            else:
                logging.info(f"🔄 Mencoba ulang dalam {delay_between_retry} detik...")
                time.sleep(delay_between_retry)
    return False

# --- API & CSV Logic (from controller_api.py) ---
batch_size = 10
api_url = config.API_URL

def send_data_from_csv(csv_file, api_url):
    try:
        df = pd.read_csv(csv_file)
        df = df.where(pd.notnull(df), None)
        batch = []
        for row in df.to_dict('records'):
            id_val = row.get('id') or row.get('\ufeffid')
            if not id_val or not str(id_val).strip():
                logging.warning(f"Lewati baris tanpa id: {row}")
                continue
            row['id'] = id_val
            if '\ufeffid' in row:
                del row['\ufeffid']
            batch.append(row)
            if len(batch) >= batch_size:
                logging.info(f"Mengirim batch: contoh data pertama: {batch[0]}")
                post_batch(batch, api_url)
                batch = []
                time.sleep(1)
        if batch:
            logging.info(f"Mengirim batch: contoh data pertama: {batch[0]}")
            post_batch(batch, api_url)
    except Exception as e:
        logging.error(f"Error saat mengirim data: {e}")

def post_batch(batch, api_url):
    try:
        response = requests.post(api_url, json=batch, timeout=15)
        if response.status_code in [200, 201]:
            logging.info(f"Berhasil kirim batch {len(batch)} data. Response: {response.json()}")
        else:
            logging.warning(f"Gagal kirim batch. Response: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Exception saat POST batch: {e}")

def mark_keyword_done(keyword_file, keyword_to_mark):
    updated = []
    try:
        with open(keyword_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['input'] == keyword_to_mark:
                    row['status'] = 'done'
                updated.append(row)
        with open(keyword_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=updated[0].keys())
            writer.writeheader()
            writer.writerows(updated)
        logging.info(f"✅ Keyword '{keyword_to_mark}' ditandai sebagai done.")
    except Exception as e:
        logging.error(f"❌ Error saat update {keyword_file}: {e}")

def process_keyword(keyword, log_path):
    logging.info(f"🚀 Memulai proses keyword: {keyword}")
    if not run_script_with_retry_and_stream("scrape.py", log_path):
        return
    if not run_script_with_retry_and_stream("deduplicate.py", log_path):
        return
    if not run_script_with_retry_and_stream("download_coverc.py", log_path):
        return
    send_data_from_csv(config.OUTPUT_FILENAME, api_url)
    mark_keyword_done(config.KEYWORD_LIST_CSV, keyword)

def main():
    log_path = setup_logging()
    try:
        with open(config.KEYWORD_LIST_CSV, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['status'].strip().lower() != 'done':
                    process_keyword(row['input'], log_path)
    except Exception as e:
        logging.error(f"❌ Error saat membaca {config.KEYWORD_LIST_CSV}: {e}")
    logging.info("Semua pipeline selesai sukses.")

if __name__ == "__main__":
    main()