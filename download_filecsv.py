import os
import re
import time
import pandas as pd
import configparser
import logging
import sys
from datetime import datetime, timedelta
from tqdm import tqdm # Import library progress bar
from selenium import webdriver
# ... (sisa import sama)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException


# --- FUNGSI-FUNGSI (Tidak ada perubahan di sini, Anda bisa langsung skip ke fungsi main) ---
def setup_logging():
    log_directory = "log"
    os.makedirs(log_directory, exist_ok=True)
    log_filename = datetime.now().strftime(f"{log_directory}/log_%Y-%m-%d_%H-%M-%S.txt")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.FileHandler(log_filename, 'w', 'utf-8'), logging.StreamHandler(sys.stdout)])
    logging.info("Sistem logging berhasil diinisialisasi.")
def setup_driver(download_path):
    """Menyiapkan instance WebDriver dengan penyamaran untuk mode headless."""
    chrome_options = Options()
    
    # --- OPSI PENYAMARAN BARU ---
    # Atur User-Agent agar terlihat seperti browser biasa
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    chrome_options.add_argument(f"user-agent={user_agent}")
    
    # Atur ukuran jendela virtual agar tidak terlihat seperti bot
    chrome_options.add_argument("--window-size=1920,1080")
    # ----------------------------

    # Aktifkan mode headless (hapus # jika ingin menggunakan)
    #chrome_options.add_argument("--headless")
    
    # Opsi performa lainnya
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "download.default_directory": download_path
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = webdriver.Chrome(options=chrome_options)
    logging.info("WebDriver disiapkan dengan opsi penyamaran untuk headless.")
    return driver
def sanitize_filename(name):
    if pd.isna(name): return ""
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
            title = sanitize_filename(book_row.get('title', 'Unknown Title')); author = sanitize_filename(book_row.get('author')); publisher = sanitize_filename(book_row.get('publisher', 'Unknown Publisher')); extension = book_row.get('extension', 'dat')
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
            password_field.click()
            password_field.send_keys(password)
            driver.find_element(By.XPATH, "//div[@id='auth_modal_login']//button[@type='submit']").click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "section.navigation-element.logged")))
            logging.info("Login berhasil!")
            return True
        except Exception:
            logging.error(f"Proses login dengan {email} gagal.")
            # --- TAMBAHAN UNTUK DEBUGGING ---
            # Ambil screenshot untuk melihat apa yang terjadi
            screenshot_file = f"debug_login_failed_{email.split('@')[0]}.png"
            driver.save_screenshot(screenshot_file)
            logging.info(f"Screenshot kegagalan disimpan sebagai: {screenshot_file}")
            # ---------------------------------
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

# --- SKRIP UTAMA (DENGAN PENYEMPURNAAN) ---
def main():
    setup_logging()
    start_time = time.time() # Catat waktu mulai
    driver = None
    
    # Inisialisasi counter untuk laporan akhir
    stats = {"processed": 0, "downloaded": 0, "failed": 0, "limit_hit": 0}

    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        # Baca dari [Paths]
        paths = config['Paths']
        books_csv_path = paths['books_csv']
        accounts_csv_path = paths['accounts_csv']
        download_dir_name = paths['download_dir']
        
        # Baca dari [Settings]
        settings = config['Settings']
        start_row = settings.getint('start_row', fallback=None)
        end_row = settings.getint('end_row', fallback=None)

        download_full_path = os.path.join(os.getcwd(), download_dir_name)
        os.makedirs(download_full_path, exist_ok=True)
        
        df_accounts = pd.read_csv(accounts_csv_path)
        if 'last_limit_date' not in df_accounts.columns: df_accounts['last_limit_date'] = ''
        
        today_str = datetime.now().date().isoformat()
        available_accounts_df = df_accounts[df_accounts['last_limit_date'] != today_str]
        accounts_list = available_accounts_df.to_dict('records')

        if not accounts_list:
            logging.warning("Semua akun telah mencapai limit untuk hari ini.")
            return
        logging.info(f"Ditemukan {len(accounts_list)} akun tersedia.")
        
        df_books = pd.read_csv(books_csv_path)
        if 'download_path' not in df_books.columns: df_books['download_path'] = ""
        if 'download_status' not in df_books.columns: df_books['download_status'] = ""
        
        driver = setup_driver(download_full_path)
        current_account_index = 0
        
        start_index = 0 if start_row is None else start_row - 1
        end_index = len(df_books) if end_row is None else end_row
        books_to_process = df_books.iloc[start_index:end_index]

        # Gunakan tqdm untuk progress bar
        for index, book_row in tqdm(books_to_process.iterrows(), total=len(books_to_process), desc="Memproses Buku"):
            stats["processed"] += 1
            if book_row.get('download_status') == 'done':
                logging.info(f"Baris {index + 1}: Buku '{book_row['title']}' sudah 'done'. Melewati.")
                continue
            
            logging.info(f"\n--- Memproses Baris {index + 1}: {book_row.get('title')} ---")
            
            download_successful = False
            while not download_successful:
                if current_account_index >= len(accounts_list):
                    logging.warning("Semua akun yang tersedia telah habis.")
                    stats["failed"] += 1
                    df_books.to_csv(books_csv_path, index=False, encoding='utf-8')
                    return

                current_account = accounts_list[current_account_index]
                driver.get(book_row['book_url'])

                if not login(driver, current_account['email'], current_account['password']):
                    cooldown_seconds = 45
                    logging.warning(f"Login gagal. Menunggu {cooldown_seconds} detik.")
                    time.sleep(cooldown_seconds)
                    current_account_index += 1
                    continue
                
                try:
                    download_button = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.btn.btn-default.addDownloadedBook')))
                    download_button.click()
                    time.sleep(1)

                    if check_limit_reached(driver):
                        logging.warning(f"Limit tercapai untuk akun: {current_account['email']}.")
                        stats["limit_hit"] += 1
                        acc_index = df_accounts[df_accounts['email'] == current_account['email']].index[0]
                        df_accounts.loc[acc_index, 'last_limit_date'] = today_str
                        df_accounts.to_csv(accounts_csv_path, index=False, encoding='utf-8')
                        logout(driver)
                        current_account_index += 1
                    else:
                        new_filepath = wait_for_download_and_rename(download_full_path, book_row)
                        if new_filepath:
                            df_books.loc[index, 'download_path'] = new_filepath
                            df_books.loc[index, 'download_status'] = 'done'
                            logging.info(f"Status baris {index + 1} diupdate menjadi 'done'.")
                            stats["downloaded"] += 1
                        else:
                            df_books.loc[index, 'download_status'] = 'failed'
                            logging.error(f"Status baris {index + 1} diupdate menjadi 'failed'.")
                            stats["failed"] += 1
                        df_books.to_csv(books_csv_path, index=False, encoding='utf-8')
                        download_successful = True
                except TimeoutException:
                    logging.error("Tombol download tidak ditemukan. Menandai 'failed'.")
                    df_books.loc[index, 'download_status'] = 'failed'
                    df_books.to_csv(books_csv_path, index=False, encoding='utf-8')
                    stats["failed"] += 1
                    download_successful = True

    except Exception:
        logging.critical("Terjadi error fatal yang tidak terduga.", exc_info=True)
    finally:
        # Tampilkan Laporan Akhir
        end_time = time.time()
        total_seconds = int(end_time - start_time)
        run_time = timedelta(seconds=total_seconds)
        
        logging.info("\n" + "="*50)
        logging.info("--- LAPORAN AKHIR ---")
        logging.info(f"Total Waktu Berjalan : {run_time}")
        logging.info(f"Total Buku Diproses  : {stats['processed']}")
        logging.info(f"Berhasil Diunduh     : {stats['downloaded']}")
        logging.info(f"Gagal Diunduh        : {stats['failed']}")
        logging.info(f"Akun Mencapai Limit  : {stats['limit_hit']}")
        logging.info("="*50)
        
        if driver:
            logging.info("Menutup browser.")
            driver.quit()

if __name__ == "__main__":
    main()