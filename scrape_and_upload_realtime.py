import os
import sys
import threading
import logging
import time
import pandas as pd
import requests
from datetime import datetime
import config
from notify import send_fatal_error, send_batch_summary

# Fungsi upload ke API
def upload_to_api(csv_path, api_url):
    try:
        df = pd.read_csv(csv_path)
        df = df.where(pd.notnull(df), None)
        batch = df.to_dict('records')
        response = requests.post(api_url, json=batch, timeout=30)
        if response.status_code in [200, 201]:
            logging.info(f"Upload batch sukses. Response: {response.text}")
        else:
            logging.warning(f"Upload batch gagal. Response: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Error upload ke API: {e}")
        send_fatal_error(f"Error upload ke API: {e}", context='scrape_and_upload_realtime.py')

# Fungsi dedup per keyword (overwrite CSV sementara)
def dedup_csv(csv_path):
    try:
        df = pd.read_csv(csv_path)
        before = len(df)
        df.drop_duplicates(subset=['id', 'title'], inplace=True)
        after = len(df)
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logging.info(f"Dedup selesai. Sebelum: {before} | Sesudah: {after} | Duplikat dihapus: {before-after}")
    except Exception as e:
        logging.error(f"Dedup error: {e}")
        send_fatal_error(f"Dedup error: {e}", context='scrape_and_upload_realtime.py')

# Fungsi scraping satu keyword (gunakan logic dari scrape.py)
def scrape_one_keyword(keyword, input_type):
    from scrape import scrape_search_or_category, scrape_booklist
    import config
    import pandas as pd
    from urllib.parse import quote
    result_data = []
    if input_type == 'keyword':
        search_url = f"{config.BASE_URL}/s/{quote(keyword)}"
        result_data = scrape_search_or_category(search_url, 'keyword')
    elif input_type == 'category':
        result_data = scrape_search_or_category(keyword, 'category')
    elif input_type == 'booklist':
        result_data = scrape_booklist(keyword)
    else:
        logging.warning(f"Tipe input tidak dikenal: {input_type}")
        return False
    if result_data:
        # Simpan ke CSV sementara (per keyword)
        temp_csv = f"temp_scrape_{int(time.time())}.csv"
        pd.DataFrame(result_data).to_csv(temp_csv, index=False, encoding='utf-8-sig')
        return temp_csv
    return None

# Main workflow per-keyword
def process_keyword(keyword, input_type):
    logging.info(f"Mulai scraping: {keyword} ({input_type})")
    temp_csv = scrape_one_keyword(keyword, input_type)
    if not temp_csv:
        logging.warning(f"Tidak ada hasil untuk {keyword}")
        return
    dedup_csv(temp_csv)
    # Upload ke API di thread terpisah agar scraping tidak terblokir
    t = threading.Thread(target=upload_to_api, args=(temp_csv, config.API_URL))
    t.start()
    # Gabungkan hasil ke file utama (opsional)
    if os.path.exists(config.OUTPUT_FILENAME):
        df_main = pd.read_csv(config.OUTPUT_FILENAME)
        df_new = pd.read_csv(temp_csv)
        df_all = pd.concat([df_main, df_new], ignore_index=True)
        df_all.drop_duplicates(subset=['id', 'title'], inplace=True)
        df_all.to_csv(config.OUTPUT_FILENAME, index=False, encoding='utf-8-sig')
    else:
        os.rename(temp_csv, config.OUTPUT_FILENAME)
    logging.info(f"Selesai proses {keyword}")

# Ambil keyword dari DB/API
def get_keywords_from_db():
    try:
        resp = requests.get('http://localhost:8080/get_keywords')
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logging.error(f'Gagal mengambil keyword dari DB: {e}')
    return []

def main():
    os.makedirs('log', exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    keywords = get_keywords_from_db()
    if not keywords:
        logging.error("Tidak ada keyword/kategori/booklist yang ditemukan di database.")
        return
    for row in keywords:
        keyword = str(row['input'])
        input_type = str(row.get('type', '')).strip().lower()
        process_keyword(keyword, input_type)
        # Tidak perlu menunggu upload selesai, lanjut ke keyword berikutnya
        time.sleep(1)  # Optional: beri jeda agar tidak overload
    logging.info("Selesai semua keyword.")

if __name__ == "__main__":
    main() 