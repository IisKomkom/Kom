import os
import sys
import json
import time
import logging
import pandas as pd
from urllib.parse import quote, urljoin
from requests.models import PreparedRequest
from bs4 import BeautifulSoup
from datetime import datetime
import requests

# --- Setup Logging ---
def setup_logging():
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)
    log_file = datetime.now().strftime(f"{log_dir}/log_pipeline_%Y-%m-%d_%H-%M-%S.txt")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, 'w', 'utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("Logging system initialized.")

setup_logging()
try:
    import config
except ImportError:
    logging.critical("config.py tidak ditemukan.")
    sys.exit(1)

# --- Status JSON ---
STATUS_PATH = 'keyword_status.json'
SHEET_URL = config.KEYWORD_SHEET_CSV_URL

# --- Load Status JSON ---
def load_status():
    if os.path.exists(STATUS_PATH):
        try:
            with open(STATUS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            logging.warning('File status kosong/invalid, sinkronisasi ulang dari sheet...')
            import pandas as pd
            try:
                df_keywords = pd.read_csv(SHEET_URL)
                status_dict = {}
                for idx, row in df_keywords.iterrows():
                    keyword = str(row['input'])
                    input_type = str(row.get('type', '')).strip().lower()
                    sheet_status = str(row.get('status', '')).strip().lower()
                    if keyword not in status_dict:
                        status_dict[keyword] = {}
                    if sheet_status == 'done':
                        status_dict[keyword][input_type] = 'done'
                save_status(status_dict)
                return status_dict
            except Exception as e:
                logging.error(f'Gagal sinkronisasi status dari sheet: {e}')
                return {}
    return {}

def save_status(status_dict):
    with open(STATUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(status_dict, f, ensure_ascii=False, indent=2)

# --- Setup Session with Cookies ---
http_session = requests.Session()
current_cookie_index = 0

def setup_session(cookie_index):
    global http_session
    if cookie_index >= len(config.FALLBACK_COOKIES_JSON):
        logging.error("Semua cookies gagal. Keluar.")
        return False
    cookie_json = config.FALLBACK_COOKIES_JSON[cookie_index]
    if "paste_your" in cookie_json:
        logging.critical(f"Harap isi cookie di config.py (set #{cookie_index + 1}).")
        return False
    try:
        cookie_list = json.loads(cookie_json)
        cookies_dict = {c['name']: c['value'] for c in cookie_list}
    except json.JSONDecodeError:
        logging.critical(f"JSON cookies invalid (set #{cookie_index + 1}).")
        return False
    http_session = requests.Session()
    http_session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    })
    http_session.cookies.update(cookies_dict)
    logging.info(f"Menggunakan Cookie Set #{cookie_index + 1}")
    return True

# --- Scrape Search/Category Handler ---
def scrape_search_or_category(base_url, keyword_type):
    scraped_data = []
    for order in config.SORT_ORDERS:
        for page_num in range(1, config.MAX_PAGES_PER_ORDER + 1):
            params = {
                'languages[]': config.LANGUAGES_TO_SCRAPE,
                'extensions[]': config.FILE_EXTENSIONS,
                'order': order,
                'page': page_num
            }

            req = PreparedRequest()
            req.prepare_url(base_url, params)
            logging.info(f"{keyword_type.upper()} | Page {page_num} - {req.url}")

            try:
                response = http_session.get(base_url, params=params, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                book_cards = soup.find_all('z-bookcard')

                if not book_cards:
                    logging.info("Tidak ada buku di halaman ini.")
                    break

                for card in book_cards:
                    scraped_data.append({
                        'id': card.get('id'),
                        'title': card.find('div', attrs={'slot': 'title'}).get_text(strip=True) if card.find('div', attrs={'slot': 'title'}) else 'N/A',
                        'author': card.find('div', attrs={'slot': 'author'}).get_text(strip=True) if card.find('div', attrs={'slot': 'author'}) else 'N/A',
                        'year': card.get('year'),
                        'publisher': card.get('publisher'),
                        'language': card.get('language'),
                        'extension': card.get('extension'),
                        'filesize': card.get('filesize'),
                        'book_url': urljoin(config.BASE_URL, card.get('href', '')),
                        'cover_image_url': card.find('img').get('data-src', 'N/A') if card.find('img') else 'N/A',
                        'source_type': keyword_type
                    })
                    # Batasi jumlah data per keyword untuk test
                    if len(scraped_data) >= getattr(config, 'MAX_DATA_PER_KEYWORD', 0) > 0:
                        logging.info(f"Batas MAX_DATA_PER_KEYWORD ({config.MAX_DATA_PER_KEYWORD}) tercapai, hentikan scraping untuk keyword ini.")
                        return scraped_data
                time.sleep(1)
            except Exception as e:
                logging.error(f"Error saat mengambil halaman: {e}")
                break
    return scraped_data

# --- Scrape Booklist Handler ---
def scrape_booklist(booklist_url):
    scraped_data = []
    try:
        logging.info(f"BOOKLIST - {booklist_url}")
        import re
        match = re.search(r'/booklist/(\d+)', booklist_url)
        if match:
            readlist_id = match.group(1)
            base_url = re.match(r'^(https?://[^/]+)', booklist_url).group(1)
            page = 1
            seen_ids = set()
            while True:
                api_url = f"{base_url}/papi/booklist/{readlist_id}/get-books/{page}"
                try:
                    response = http_session.post(
                        api_url,
                        data="{}",  # body kosong atau '{}'
                        headers={
                            "Content-Type": "text/plain;charset=UTF-8",
                            "Origin": base_url,
                            "Referer": booklist_url,
                        },
                        timeout=30
                    )
                    data = response.json()
                except Exception as e:
                    logging.error(f"❌ Gagal ambil data JSON booklist: {e}")
                    break
                books = data.get('books', [])
                for item in books:
                    book = item.get('book', {})
                    book_id = book.get('id')
                    if not book_id:
                        # fallback: buat id dari title+author+year
                        book_id = f"{book.get('title','')}_{book.get('author','')}_{book.get('year','')}".replace(' ', '_')
                    if book_id in seen_ids:
                        continue
                    seen_ids.add(book_id)
                    scraped_data.append({
                        'id': book_id,
                        'title': book.get('title'),
                        'author': book.get('author'),
                        'year': book.get('year'),
                        'publisher': book.get('publisher'),
                        'language': book.get('language'),
                        'extension': book.get('extension'),
                        'filesize': book.get('filesizeString'),
                        'book_url': base_url + book.get('href', '') if book.get('href') else None,
                        'cover_image_url': book.get('cover'),
                        'source_type': 'booklist'
                    })
                    # Tambahkan limit di sini
                    if getattr(config, 'MAX_DATA_PER_KEYWORD', 0) > 0 and len(scraped_data) >= config.MAX_DATA_PER_KEYWORD:
                        logging.info(f"Batas MAX_DATA_PER_KEYWORD ({config.MAX_DATA_PER_KEYWORD}) tercapai, hentikan scraping untuk keyword ini.")
                        return scraped_data
                # Jangan break jika books kosong, lanjutkan ke page berikutnya selama pagination.next masih ada
                if not data.get('pagination', {}).get('next'):
                    break
                page += 1
            return scraped_data
        # Fallback ke scraping HTML jika tidak ada readlist_id
        response = http_session.get(booklist_url, timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')
        book_items = soup.select('z-bookcard')
        if not book_items:
            logging.info("Tidak ada buku dalam booklist.")
            return scraped_data
        seen_ids = set()
        for card in book_items:
            book_id = card.get('id') or card.attrs.get('id')
            title = card.find('div', {'slot': 'title'}).get_text(strip=True) if card.find('div', {'slot': 'title'}) else None
            author = card.find('div', {'slot': 'author'}).get_text(strip=True) if card.find('div', {'slot': 'author'}) else None
            year = card.get('year')
            if not book_id:
                book_id = f"{title}_{author}_{year}".replace(' ', '_')
            if book_id in seen_ids:
                continue
            seen_ids.add(book_id)
            publisher = None  # Tidak ada di HTML contoh
            language = card.get('language')
            extension = card.get('extension')
            filesize = card.get('filesize')
            book_url = urljoin(config.BASE_URL, card.get('href')) if card.get('href') else None
            cover_image_url = card.find('img')['data-src'] if card.find('img') else None
            scraped_data.append({
                'id': book_id,
                'title': title,
                'author': author,
                'year': year,
                'publisher': publisher,
                'language': language,
                'extension': extension,
                'filesize': filesize,
                'book_url': book_url,
                'cover_image_url': cover_image_url,
                'source_type': 'booklist'
            })
            # Tambahkan limit di sini juga
            if getattr(config, 'MAX_DATA_PER_KEYWORD', 0) > 0 and len(scraped_data) >= config.MAX_DATA_PER_KEYWORD:
                logging.info(f"Batas MAX_DATA_PER_KEYWORD ({config.MAX_DATA_PER_KEYWORD}) tercapai, hentikan scraping untuk keyword ini.")
                return scraped_data
    except Exception as e:
        logging.error(f"❌ Error saat mengambil booklist: {e}")
    return scraped_data

# --- Main Function ---
def main():
    global current_cookie_index
    if not setup_session(current_cookie_index):
        sys.exit(1)

    # Baca keyword dari Google Sheets
    df_keywords = pd.read_csv(SHEET_URL)
    status_dict = load_status()

    # Sinkronisasi otomatis status 'done' dari Google Sheets ke status lokal
    for idx, row in df_keywords.iterrows():
        keyword = str(row['input'])
        input_type = str(row.get('type', '')).strip().lower()
        sheet_status = str(row.get('status', '')).strip().lower()
        if keyword not in status_dict:
            status_dict[keyword] = {}
        if sheet_status == 'done':
            status_dict[keyword][input_type] = 'done'
    save_status(status_dict)

    for idx, row in df_keywords.iterrows():
        keyword = str(row['input'])
        input_type = str(row.get('type', '')).strip().lower()
        status = status_dict.get(keyword, {}).get(input_type, 'pending')
        if status == 'done':
            logging.info(f"{keyword} ({input_type}) sudah done, skip.")
            continue
        elif status == 'in_progress':
            logging.info(f"{keyword} ({input_type}) sedang diproses oleh script lain, skip.")
            continue
        elif status == 'error':
            logging.info(f"{keyword} ({input_type}) sebelumnya error, skip atau retry manual.")
            continue
        # Tandai in_progress sebelum proses (agar script lain tahu)
        if keyword not in status_dict:
            status_dict[keyword] = {}
        status_dict[keyword][input_type] = 'in_progress'
        save_status(status_dict)
        try:
            input_value = row['input']
            logging.info(f"🚀 Memproses '{input_value}' - Type: {input_type}")

            if input_type == 'keyword':
                search_url = f"{config.BASE_URL}/s/{quote(input_value)}"
                result_data = scrape_search_or_category(search_url, 'keyword')

            elif input_type == 'category':
                result_data = scrape_search_or_category(input_value, 'category')

            elif input_type == 'booklist':
                result_data = scrape_booklist(input_value)

            else:
                logging.warning(f"⚠️ Tipe '{input_type}' tidak dikenal. Melewati.")
                continue

            if result_data:
                result_df = pd.DataFrame(result_data)
                if not os.path.exists(config.OUTPUT_FILENAME):
                    result_df.to_csv(config.OUTPUT_FILENAME, index=False, encoding='utf-8-sig')
                else:
                    result_df.to_csv(config.OUTPUT_FILENAME, mode='a', header=False, index=False, encoding='utf-8-sig')

            status_dict[keyword][input_type] = 'done'
        except Exception as e:
            logging.error(f"❌ Gagal memproses '{keyword}' ({input_type}): {e}")
            status_dict[keyword][input_type] = 'error'
        finally:
            save_status(status_dict)
            logging.info(f"Status {keyword} ({input_type}) diupdate jadi {status_dict[keyword][input_type]} di file lokal.")
    logging.info("Selesai semua keyword.")

    # Cek apakah semua kombinasi keyword+type sudah done
    semua_done = True
    for idx, row in df_keywords.iterrows():
        keyword = str(row['input'])
        input_type = str(row.get('type', '')).strip().lower()
        status = status_dict.get(keyword, {}).get(input_type, 'pending')
        if status != 'done':
            semua_done = False
            break
    if semua_done:
        logging.info('Semua keyword sudah done. Reload script dalam 60 detik untuk cek sheet baru...')
        time.sleep(60)
        os.execv(sys.executable, [sys.executable] + sys.argv)

if __name__ == "__main__":
    main()
