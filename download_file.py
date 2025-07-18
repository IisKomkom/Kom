import os
import re
import time
import logging
import sys
from datetime import datetime, timedelta
import requests
import config
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, NoSuchWindowException
import pandas as pd
from notify import send_batch_summary, send_fatal_error, send_login_failed, send_limit_hit

# --- Konfigurasi API ---
API_CLAIM_URL = getattr(config, 'API_CLAIM_URL', 'https://www.api.staisenorituban.ac.id/claim_books')
API_UPDATE_URL = config.API_URL
INSTANCE_ID = os.getenv('INSTANCE_ID', f'instance_{os.getpid()}')
BATCH_SIZE = 10

# --- FUNGSI-FUNGSI UTILITY (dari backup/download_file copy.py, tanpa CSV) ---
def setup_logging():
    log_directory = "log"
    os.makedirs(log_directory, exist_ok=True)
    log_filename = datetime.now().strftime(f"{log_directory}/log_download_api_%Y-%m-%d_%H-%M-%S.txt")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.FileHandler(log_filename, 'w', 'utf-8'), logging.StreamHandler(sys.stdout)])
    logging.info("Sistem logging download_file.py (API mode) diinisialisasi.")

def setup_driver(download_path):
    chrome_options = Options()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    chrome_options.add_argument(f"user-agent={user_agent}")
    chrome_options.add_argument("--window-size=1920,1080")
    #chrome_options.add_argument("--headless")
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "download.default_directory": download_path
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument('--log-level=3')
    chrome_options.binary_location = os.path.join("data", "chrome-win64", "chrome.exe")
    chromedriver_path = os.path.join("data", "chromedriver-win64", "chromedriver.exe")
    from selenium.webdriver.chrome.service import Service
    service = Service(executable_path=chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    logging.info(f"WebDriver disiapkan dengan Chrome binary: {chrome_options.binary_location} dan chromedriver: {chromedriver_path}")
    return driver

def sanitize_filename(name):
    if name is None:
        return ""
    return re.sub(r'[<>:"/\\|?*]', '', str(name)).strip()

def wait_for_download_and_rename(download_path, book_row, timeout=600):
    logging.info("Memantau folder download...")
    files_before = set(os.listdir(download_path))
    start_time = time.time()
    while time.time() - start_time < timeout:
        time.sleep(2)
        new_files = set(os.listdir(download_path)) - files_before
        finished_file = next((f for f in new_files if not f.endswith('.crdownload')), None)
        if finished_file:
            logging.info(f"File terdeteksi: {finished_file}")
            original_filepath = os.path.join(download_path, finished_file)
            title = sanitize_filename(book_row.get('title', 'Unknown Title'))
            author = sanitize_filename(book_row.get('author'))
            publisher = sanitize_filename(book_row.get('publisher', 'Unknown Publisher'))
            extension = book_row.get('extension', 'dat')
            name_part = f"{title} - {author}" if author else f"{title} - {publisher}"
            new_filename = f"{name_part}.{extension}"
            new_filepath = os.path.join(download_path, new_filename)
            try:
                os.rename(original_filepath, new_filepath)
                logging.info(f"File diganti nama menjadi: {new_filename}")
                return new_filepath
            except OSError as e:
                logging.error(f"Gagal mengganti nama file: {e}")
                return original_filepath
    logging.warning("Waktu tunggu download habis.")
    return None

def login(driver, email, password):
    logging.info(f"Mencoba login dengan akun: {email}")
    wait = WebDriverWait(driver, 20)
    try:
        driver.find_element(By.CSS_SELECTOR, "section.navigation-element.logged")
        return True
    except NoSuchElementException:
        try:
            login_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "section.not-logged a[data-action='login']")))
            login_link.click()
            wait.until(EC.presence_of_element_located((By.ID, "auth_modal_login")))
            email_field = driver.find_element(By.NAME, "email"); password_field = driver.find_element(By.NAME, "password")
            email_field.clear(); password_field.clear()
            email_field.send_keys(email)
            time.sleep(1)  # Jeda setelah isi email
            password_field.click()
            password_field.send_keys(password)
            driver.find_element(By.XPATH, "//div[@id='auth_modal_login']//button[@type='submit']").click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "section.navigation-element.logged")))
            logging.info("Login berhasil!")
            return True
        except Exception:
            logging.error(f"Proses login dengan {email} gagal.")
            screenshot_file = f"debug_login_failed_{email.split('@')[0]}.png"
            driver.save_screenshot(screenshot_file)
            logging.info(f"Screenshot kegagalan disimpan sebagai: {screenshot_file}")
            return False

def logout(driver):
    logging.info("Melakukan logout dengan menghapus cookies...")
    try:
        driver.delete_all_cookies(); driver.refresh()
        wait = WebDriverWait(driver, 15)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "section.not-logged a[data-action='login']")))
        logging.info("Logout berhasil dikonfirmasi.")
    except Exception as e:
        logging.error(f"Terjadi masalah saat proses logout: {e}")

def check_limit_reached(driver):
    try:
        driver.find_element(By.XPATH, "//*[contains(text(), 'Daily limit reached')]")
        return True
    except NoSuchElementException:
        return False

def claim_books(batch_size=BATCH_SIZE, max_retries=3):
    retries = 0
    while retries < max_retries:
        try:
            resp = requests.post(API_CLAIM_URL, json={"batch_size": batch_size, "instance_id": INSTANCE_ID}, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 500:
                retries += 1
                logging.error(f'Gagal claim books dari API: 500 Server Error. Retry {retries}/3 dalam 3 detik...')
                time.sleep(3)
                continue
            else:
                logging.error(f'Gagal claim books dari API: {e}')
                return []
        except Exception as e:
            logging.error(f'Gagal claim books dari API: {e}')
            return []
    logging.error('Gagal claim books dari API setelah 3x retry.')
    return []

def update_book_status(book_id, status, download_path=None):
    data = {"id": book_id, "download_status": status}
    if download_path:
        data["download_path"] = download_path
    try:
        resp = requests.post(API_UPDATE_URL, json=data, timeout=30)
        if resp.status_code in [200, 201]:
            logging.info(f"Update status ke API sukses untuk {book_id}: {status}")
        else:
            logging.error(f"Update status ke API gagal untuk {book_id}: {resp.status_code} - {resp.text}")
    except Exception as e:
        logging.error(f"Exception update status ke API untuk {book_id}: {e}")

def load_accounts(accounts_csv='data/csv/akun.csv'):
    df = pd.read_csv(accounts_csv)
    today_str = datetime.now().date().strftime('%m/%d/%Y')
    available = df[
        (df['last_limit_date'].isna()) |
        (df['last_limit_date'].astype(str).str.strip() == '') |
        (df['last_limit_date'] != today_str)
    ]
    return available.to_dict(orient='records')

def main():
    setup_logging()
    download_dir_name = getattr(config, 'DOWNLOAD_DIR', 'download_files')
    download_full_path = os.path.join(os.getcwd(), download_dir_name)
    os.makedirs(download_full_path, exist_ok=True)
    driver = setup_driver(download_full_path)
    accounts_list = load_accounts()
    current_account_index = 0
    try:
        stats = {"processed": 0, "downloaded": 0, "failed": 0, "limit_hit": 0}
        while True:
            books = claim_books()
            if not books:
                logging.info("Tidak ada buku pending, selesai.")
                send_batch_summary(stats['downloaded'], stats['failed'], batch_type='Download', extra='Tidak ada buku pending.')
                break
            for book in tqdm(books, desc="Memproses Buku"):
                stats["processed"] += 1
                book_id = book.get('id')
                title = book.get('title')
                url = book.get('book_url')
                author = book.get('author')
                publisher = book.get('publisher')
                extension = book.get('extension')
                logging.info(f"Mulai download: {book_id} - {title}")
                download_successful = False
                retry_url_attempts = 0
                max_url_retries = 3
                while not download_successful:
                    if accounts_list:
                        if current_account_index >= len(accounts_list):
                            logging.warning("Semua akun yang tersedia telah habis.")
                            stats["failed"] += 1
                            send_fatal_error("Semua akun yang tersedia telah habis.", context='download_file.py')
                            return
                        current_account = accounts_list[current_account_index]
                        # --- Retry logic for 502 Bad Gateway and auto-login if logged out ---
                        while retry_url_attempts < max_url_retries:
                            driver.get(url)
                            time.sleep(2)
                            page_source = driver.page_source
                            if '502 Bad Gateway' in page_source and 'Angie/1.10.0' in page_source:
                                logging.warning(f"502 Bad Gateway detected. Retry {retry_url_attempts+1}/{max_url_retries}...")
                                retry_url_attempts += 1
                                time.sleep(3)
                                continue
                            # Check if logged out (login form present)
                            if 'auth_modal_login' in page_source or 'name=\"email\"' in page_source:
                                logging.warning("Detected logged out state. Attempting to re-login...")
                                if not login(driver, current_account['email'], current_account['password']):
                                    cooldown_seconds = 10
                                    logging.warning(f"Login gagal. Menunggu {cooldown_seconds} detik.")
                                    send_login_failed(current_account['email'])
                                    time.sleep(cooldown_seconds)
                                    current_account_index += 1
                                    break
                                else:
                                    logging.info("Re-login berhasil. Reloading book URL...")
                                    retry_url_attempts += 1
                                    continue
                            break  # Exit retry loop if no 502 and not logged out
                        else:
                            # After 3 retries, try one more time to open the main URL from DB
                            logging.warning(f"Gagal membuka URL setelah {max_url_retries} percobaan. Mencoba sekali lagi buka ulang URL utama dari database...")
                            driver.get(url)
                            time.sleep(2)
                            page_source = driver.page_source
                            if '502 Bad Gateway' in page_source and 'Angie/1.10.0' in page_source:
                                logging.error(f"Tetap gagal (502 Bad Gateway) setelah percobaan ulang ke URL utama. Menandai gagal.")
                                update_book_status(book_id, 'failed')
                                stats["failed"] += 1
                                send_fatal_error("Tetap gagal (502 Bad Gateway) setelah percobaan ulang ke URL utama.", context='download_file.py')
                                download_successful = True
                                continue
                            # else: continue as normal if not 502
                        # --- End retry logic ---
                        if not login(driver, current_account['email'], current_account['password']):
                            cooldown_seconds = 45
                            logging.warning(f"Login gagal. Menunggu {cooldown_seconds} detik.")
                            send_login_failed(current_account['email'])
                            time.sleep(cooldown_seconds)
                            current_account_index += 1
                            continue
                    try:
                        # Setelah login berhasil, klik tombol download
                        download_button = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.btn.btn-default.addDownloadedBook'))
                        )
                        driver.execute_script("arguments[0].removeAttribute('target'); arguments[0].click();", download_button)
                        time.sleep(1)
                        main_tab = driver.window_handles[0]
                        limit_detected = False
                        if len(driver.window_handles) > 1:
                            try:
                                driver.switch_to.window(driver.window_handles[-1])
                                # Wait for the new tab to load and check for limit or download status
                                time.sleep(2)  # Give the page time to load
                                # Optionally, check for limit or download confirmation here
                                try:
                                    # Check for limit message in new tab
                                    if check_limit_reached(driver):
                                        logging.warning(f"Limit tercapai (detected in new tab) untuk akun: {current_account['email']}.")
                                        stats["limit_hit"] += 1
                                        send_limit_hit(current_account['email'])
                                        limit_detected = True
                                except Exception as e:
                                    logging.debug(f"Could not check limit in new tab: {e}")
                                driver.close()
                            except NoSuchWindowException:
                                logging.warning("Tab baru sudah tertutup atau tidak ditemukan saat close.")
                            finally:
                                # Pastikan kembali ke tab utama jika masih ada
                                if driver.window_handles:
                                    driver.switch_to.window(driver.window_handles[0])
                        else:
                            if check_limit_reached(driver):
                                logging.warning(f"Limit tercapai untuk akun: {current_account['email']}.")
                                stats["limit_hit"] += 1
                                send_limit_hit(current_account['email'])
                                limit_detected = True
                        if limit_detected:
                            logout(driver)
                            current_account_index += 1
                            download_successful = True
                            continue

                        book_row = {
                                'title': title,
                                'author': author,
                                'publisher': publisher,
                                'extension': extension
                            }
                        new_filepath = wait_for_download_and_rename(download_full_path, book_row)
                        if new_filepath:
                            update_book_status(book_id, 'done', new_filepath)
                            logging.info(f"Sukses download: {book_id}")
                            stats["downloaded"] += 1
                        else:
                            update_book_status(book_id, 'failed')
                            logging.error(f"Status {book_id} diupdate menjadi 'failed'.")
                            stats["failed"] += 1
                        download_successful = True
                    except TimeoutException:
                        update_book_status(book_id, 'failed')
                        logging.error(f"Tombol download tidak ditemukan untuk {book_id}. Menandai 'failed'.")
                        stats["failed"] += 1
                        send_fatal_error("Tombol download tidak ditemukan untuk buku.", context='download_file.py')
                        download_successful = True
    except Exception:
        logging.critical("Terjadi error fatal yang tidak terduga.", exc_info=True)
        send_fatal_error("Terjadi error fatal yang tidak terduga.", context='download_file.py')
    finally:
        driver.quit()
        logging.info("Browser Selenium ditutup.")
        # Laporan akhir
        logging.info("\n" + "="*50)
        logging.info("--- LAPORAN AKHIR ---")
        logging.info(f"Total Buku Diproses  : {stats['processed']}")
        logging.info(f"Berhasil Diunduh     : {stats['downloaded']}")
        logging.info(f"Gagal Diunduh        : {stats['failed']}")
        logging.info(f"Akun Mencapai Limit  : {stats['limit_hit']}")
        logging.info("="*50)
        send_batch_summary(stats['downloaded'], stats['failed'], batch_type='Download')

if __name__ == "__main__":
    main()
