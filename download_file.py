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
import random

# --- Konfigurasi API ---
API_CLAIM_URL = getattr(config, 'API_CLAIM_URL', 'https://www.api.staisenorituban.ac.id/claim_books')
API_UPDATE_URL = config.API_URL
INSTANCE_ID = os.getenv('INSTANCE_ID', f'instance_{os.getpid()}')
BATCH_SIZE = 10

# --- Enhanced Error Handling Configuration ---
MAX_RETRY_ATTEMPTS = 5
BASE_RETRY_DELAY = 2  # Base delay in seconds
MAX_RETRY_DELAY = 30  # Maximum delay in seconds
SESSION_REUSE_THRESHOLD = 50  # Number of downloads before forced session refresh
ACCOUNT_COOLDOWN_TIME = 300  # 5 minutes cooldown for failed accounts

# Global session tracking
current_session_downloads = 0
failed_accounts_cooldown = {}

# --- FUNGSI-FUNGSI UTILITY (Enhanced) ---
def setup_logging():
    log_directory = "log"
    os.makedirs(log_directory, exist_ok=True)
    log_filename = datetime.now().strftime(f"{log_directory}/log_download_api_%Y-%m-%d_%H-%M-%S.txt")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.FileHandler(log_filename, 'w', 'utf-8'), logging.StreamHandler(sys.stdout)])
    logging.info("Sistem logging download_file.py (API mode) diinisialisasi dengan enhanced error handling.")

def exponential_backoff(attempt, base_delay=BASE_RETRY_DELAY, max_delay=MAX_RETRY_DELAY):
    """Calculate exponential backoff delay with jitter"""
    delay = min(base_delay * (2 ** attempt), max_delay)
    # Add jitter to prevent thundering herd
    jitter = random.uniform(0.5, 1.5)
    return delay * jitter

def is_account_in_cooldown(email):
    """Check if account is in cooldown period"""
    if email in failed_accounts_cooldown:
        cooldown_end = failed_accounts_cooldown[email]
        if datetime.now() < cooldown_end:
            remaining = (cooldown_end - datetime.now()).seconds
            logging.info(f"Account {email} masih dalam cooldown. Sisa waktu: {remaining} detik")
            return True
        else:
            # Cooldown expired, remove from list
            del failed_accounts_cooldown[email]
    return False

def add_account_to_cooldown(email):
    """Add account to cooldown list"""
    failed_accounts_cooldown[email] = datetime.now() + timedelta(seconds=ACCOUNT_COOLDOWN_TIME)
    logging.warning(f"Account {email} ditambahkan ke cooldown selama {ACCOUNT_COOLDOWN_TIME} detik")

def setup_driver(download_path):
    chrome_options = Options()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    chrome_options.add_argument(f"user-agent={user_agent}")
    chrome_options.add_argument("--window-size=1920,1080")
    #chrome_options.add_argument("--headless")
    
    # Enhanced Chrome options for stability
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-features=TranslateUI")
    chrome_options.add_argument("--disable-ipc-flooding-protection")
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "download.default_directory": download_path,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
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
    
    # Add timeout configuration for driver
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(10)  # Implicit wait for elements
    driver.set_page_load_timeout(60)  # Page load timeout
    
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
    check_interval = 2
    
    while time.time() - start_time < timeout:
        time.sleep(check_interval)
        try:
            current_files = set(os.listdir(download_path))
            new_files = current_files - files_before
            
            # Check for completed downloads (not .crdownload)
            finished_file = next((f for f in new_files if not f.endswith('.crdownload') and not f.endswith('.tmp')), None)
            
            if finished_file:
                logging.info(f"File terdeteksi: {finished_file}")
                original_filepath = os.path.join(download_path, finished_file)
                
                # Wait a bit more to ensure file is fully written
                time.sleep(2)
                
                title = sanitize_filename(book_row.get('title', 'Unknown Title'))
                author = sanitize_filename(book_row.get('author'))
                publisher = sanitize_filename(book_row.get('publisher', 'Unknown Publisher'))
                extension = book_row.get('extension', 'dat')
                name_part = f"{title} - {author}" if author else f"{title} - {publisher}"
                new_filename = f"{name_part}.{extension}"
                new_filepath = os.path.join(download_path, new_filename)
                
                try:
                    # Check if file exists and is not empty
                    if os.path.exists(original_filepath) and os.path.getsize(original_filepath) > 0:
                        os.rename(original_filepath, new_filepath)
                        logging.info(f"File diganti nama menjadi: {new_filename}")
                        return new_filepath
                    else:
                        logging.warning(f"File {finished_file} kosong atau tidak valid")
                        continue
                except OSError as e:
                    logging.error(f"Gagal mengganti nama file: {e}")
                    return original_filepath
        except Exception as e:
            logging.error(f"Error saat memantau download: {e}")
            continue
    
    logging.warning("Waktu tunggu download habis.")
    return None

def handle_http_errors(driver, url, max_retries=MAX_RETRY_ATTEMPTS):
    """Enhanced function to handle various HTTP errors including 505"""
    for attempt in range(max_retries):
        try:
            logging.info(f"Membuka URL (attempt {attempt + 1}/{max_retries}): {url}")
            driver.get(url)
            
            # Wait for page to load
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            page_source = driver.page_source.lower()
            
            # Check for various HTTP errors
            error_patterns = {
                '502': '502 bad gateway',
                '503': '503 service unavailable', 
                '504': '504 gateway timeout',
                '505': '505 http version not supported',
                '500': '500 internal server error'
            }
            
            detected_error = None
            for error_code, pattern in error_patterns.items():
                if pattern in page_source:
                    detected_error = error_code
                    break
            
            if detected_error:
                delay = exponential_backoff(attempt)
                logging.warning(f"HTTP {detected_error} error detected. Retry {attempt + 1}/{max_retries} dalam {delay:.2f} detik...")
                
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    
                    # Try refreshing the page for certain errors
                    if detected_error in ['502', '503', '504', '505']:
                        try:
                            logging.info("Mencoba refresh halaman...")
                            driver.refresh()
                            time.sleep(3)
                        except Exception as e:
                            logging.warning(f"Refresh gagal: {e}")
                    continue
                else:
                    logging.error(f"Tetap gagal setelah {max_retries} attempts dengan HTTP {detected_error} error")
                    return False
            else:
                # No errors detected, success
                logging.info("Halaman berhasil dimuat tanpa error")
                return True
                
        except TimeoutException:
            delay = exponential_backoff(attempt)
            logging.warning(f"Timeout loading page. Retry {attempt + 1}/{max_retries} dalam {delay:.2f} detik...")
            if attempt < max_retries - 1:
                time.sleep(delay)
                continue
            else:
                logging.error(f"Timeout persisten setelah {max_retries} attempts")
                return False
        except WebDriverException as e:
            delay = exponential_backoff(attempt)
            logging.warning(f"WebDriver error: {e}. Retry {attempt + 1}/{max_retries} dalam {delay:.2f} detik...")
            if attempt < max_retries - 1:
                time.sleep(delay)
                continue
            else:
                logging.error(f"WebDriver error persisten setelah {max_retries} attempts")
                return False
    
    return False

def login_with_retry(driver, email, password, max_retries=3):
    """Enhanced login function with retry logic"""
    global current_session_downloads
    
    logging.info(f"Mencoba login dengan akun: {email}")
    
    for attempt in range(max_retries):
        try:
            wait = WebDriverWait(driver, 30)
            
            # Check if already logged in
            try:
                logged_in_element = driver.find_element(By.CSS_SELECTOR, "section.navigation-element.logged")
                logging.info("Sudah dalam kondisi login")
                return True
            except NoSuchElementException:
                pass
            
            # Click login link
            try:
                login_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "section.not-logged a[data-action='login']")))
                login_link.click()
            except TimeoutException:
                # Try alternative login method
                try:
                    driver.get(driver.current_url + "?action=login")
                    time.sleep(2)
                except:
                    pass
            
            # Wait for login modal
            wait.until(EC.presence_of_element_located((By.ID, "auth_modal_login")))
            
            # Fill login form
            email_field = driver.find_element(By.NAME, "email")
            password_field = driver.find_element(By.NAME, "password")
            
            email_field.clear()
            password_field.clear()
            
            # Type with delays to avoid detection
            for char in email:
                email_field.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            time.sleep(random.uniform(0.5, 1.5))
            password_field.click()
            
            for char in password:
                password_field.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            # Submit form
            submit_button = driver.find_element(By.XPATH, "//div[@id='auth_modal_login']//button[@type='submit']")
            submit_button.click()
            
            # Wait for login success
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "section.navigation-element.logged")))
            
            logging.info("Login berhasil!")
            current_session_downloads = 0  # Reset session counter
            return True
            
        except Exception as e:
            delay = exponential_backoff(attempt, base_delay=3)
            logging.warning(f"Login attempt {attempt + 1} gagal: {e}. Retry dalam {delay:.2f} detik...")
            
            if attempt < max_retries - 1:
                time.sleep(delay)
                # Save screenshot for debugging
                try:
                    screenshot_file = f"debug_login_attempt_{attempt + 1}_{email.split('@')[0]}.png"
                    driver.save_screenshot(screenshot_file)
                except:
                    pass
                continue
    
    logging.error(f"Login gagal setelah {max_retries} attempts untuk {email}")
    return False

def smart_logout(driver):
    """Smart logout that preserves session when possible"""
    global current_session_downloads
    
    # Only logout if we've done many downloads or session seems unstable
    if current_session_downloads < SESSION_REUSE_THRESHOLD:
        logging.info(f"Session masih fresh ({current_session_downloads} downloads), mempertahankan session")
        return
    
    logging.info("Melakukan logout dengan menghapus cookies...")
    try:
        driver.delete_all_cookies()
        driver.refresh()
        wait = WebDriverWait(driver, 15)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "section.not-logged a[data-action='login']")))
        logging.info("Logout berhasil dikonfirmasi.")
        current_session_downloads = 0
    except Exception as e:
        logging.error(f"Terjadi masalah saat proses logout: {e}")

def check_limit_reached(driver):
    try:
        # Check for various limit messages
        limit_indicators = [
            "daily limit reached",
            "limit tercapai", 
            "download limit",
            "batas download",
            "too many downloads"
        ]
        
        page_text = driver.page_source.lower()
        for indicator in limit_indicators:
            if indicator in page_text:
                return True
                
        # Also check for specific elements
        try:
            driver.find_element(By.XPATH, "//*[contains(text(), 'Daily limit reached')]")
            return True
        except NoSuchElementException:
            pass
            
        return False
    except Exception as e:
        logging.error(f"Error checking limit: {e}")
        return False

def claim_books(batch_size=BATCH_SIZE, max_retries=3):
    for attempt in range(max_retries):
        try:
            delay = exponential_backoff(attempt, base_delay=1, max_delay=10)
            if attempt > 0:
                time.sleep(delay)
                
            resp = requests.post(API_CLAIM_URL, json={"batch_size": batch_size, "instance_id": INSTANCE_ID}, timeout=30)
            resp.raise_for_status()
            return resp.json()
            
        except requests.exceptions.HTTPError as e:
            if resp.status_code in [500, 502, 503, 504]:
                logging.error(f'API error {resp.status_code}. Retry {attempt + 1}/{max_retries}...')
                continue
            else:
                logging.error(f'Gagal claim books dari API: {e}')
                return []
        except Exception as e:
            logging.error(f'Exception claim books: {e}. Retry {attempt + 1}/{max_retries}...')
            continue
    
    logging.error('Gagal claim books dari API setelah retries.')
    return []

def update_book_status(book_id, status, download_path=None, max_retries=3):
    data = {"id": book_id, "download_status": status}
    if download_path:
        data["download_path"] = download_path
    
    for attempt in range(max_retries):
        try:
            delay = exponential_backoff(attempt, base_delay=1, max_delay=5)
            if attempt > 0:
                time.sleep(delay)
                
            resp = requests.post(API_UPDATE_URL, json=data, timeout=30)
            if resp.status_code in [200, 201]:
                logging.info(f"Update status ke API sukses untuk {book_id}: {status}")
                return True
            else:
                logging.warning(f"Update status ke API gagal untuk {book_id}: {resp.status_code}")
                continue
                
        except Exception as e:
            logging.error(f"Exception update status untuk {book_id}: {e}. Retry {attempt + 1}/{max_retries}...")
            continue
    
    logging.error(f"Gagal update status {book_id} setelah {max_retries} retries")
    return False

def load_accounts(accounts_csv='data/csv/akun.csv'):
    try:
        df = pd.read_csv(accounts_csv)
        today_str = datetime.now().date().strftime('%m/%d/%Y')
        available = df[
            (df['last_limit_date'].isna()) |
            (df['last_limit_date'].astype(str).str.strip() == '') |
            (df['last_limit_date'] != today_str)
        ]
        
        # Filter out accounts in cooldown
        filtered_accounts = []
        for account in available.to_dict(orient='records'):
            if not is_account_in_cooldown(account['email']):
                filtered_accounts.append(account)
        
        logging.info(f"Loaded {len(filtered_accounts)} available accounts (filtered from {len(available)} total)")
        return filtered_accounts
    except Exception as e:
        logging.error(f"Error loading accounts: {e}")
        return []

def main():
    global current_session_downloads
    setup_logging()
    download_dir_name = getattr(config, 'DOWNLOAD_DIR', 'download_files')
    download_full_path = os.path.join(os.getcwd(), download_dir_name)
    os.makedirs(download_full_path, exist_ok=True)
    
    driver = None
    max_driver_restarts = 3
    driver_restart_count = 0
    
    try:
        driver = setup_driver(download_full_path)
        accounts_list = load_accounts()
        current_account_index = 0
        stats = {"processed": 0, "downloaded": 0, "failed": 0, "limit_hit": 0, "errors_505": 0}
        
        while True:
            try:
                books = claim_books()
                if not books:
                    logging.info("Tidak ada buku pending, selesai.")
                    send_batch_summary(stats['downloaded'], stats['failed'], batch_type='Download', extra='Tidak ada buku pending.')
                    break
                    
                # Refresh accounts list periodically
                if len(accounts_list) == 0 or current_account_index >= len(accounts_list):
                    logging.info("Memuat ulang daftar akun...")
                    accounts_list = load_accounts()
                    current_account_index = 0
                    
                    if not accounts_list:
                        logging.warning("Tidak ada akun yang tersedia. Menunggu 5 menit...")
                        time.sleep(300)  # Wait 5 minutes
                        continue
                
                for book in tqdm(books, desc="Memproses Buku"):
                    stats["processed"] += 1
                    book_id = book.get('id')
                    title = book.get('title', 'Unknown Title')
                    url = book.get('book_url')
                    author = book.get('author', '')
                    publisher = book.get('publisher', 'Unknown Publisher')
                    extension = book.get('extension', 'dat')
                    
                    logging.info(f"Mulai download: {book_id} - {title}")
                    download_successful = False
                    book_retry_count = 0
                    max_book_retries = 3
                    
                    while not download_successful and book_retry_count < max_book_retries:
                        book_retry_count += 1
                        
                        if current_account_index >= len(accounts_list):
                            # Reload accounts if we've exhausted them
                            logging.info("Semua akun habis, memuat ulang daftar akun...")
                            accounts_list = load_accounts()
                            current_account_index = 0
                            
                            if not accounts_list:
                                logging.warning("Tidak ada akun yang tersedia.")
                                stats["failed"] += 1
                                update_book_status(book_id, 'failed')
                                download_successful = True
                                break
                        
                        current_account = accounts_list[current_account_index]
                        email = current_account['email']
                        password = current_account['password']
                        
                        # Skip account if in cooldown
                        if is_account_in_cooldown(email):
                            current_account_index += 1
                            continue
                        
                        # Handle URL loading with comprehensive error handling
                        if not handle_http_errors(driver, url):
                            stats["errors_505"] += 1
                            if book_retry_count >= max_book_retries:
                                logging.error(f"Gagal membuka URL untuk {book_id} setelah {max_book_retries} attempts")
                                update_book_status(book_id, 'failed')
                                stats["failed"] += 1
                                download_successful = True
                                break
                            else:
                                # Wait before retry
                                retry_delay = exponential_backoff(book_retry_count - 1)
                                logging.info(f"Menunggu {retry_delay:.2f} detik sebelum retry...")
                                time.sleep(retry_delay)
                                continue
                        
                        # Enhanced login handling
                        page_source = driver.page_source.lower()
                        needs_login = any(indicator in page_source for indicator in [
                            'auth_modal_login', 'name="email"', 'sign in', 'login'
                        ])
                        
                        if needs_login:
                            logging.info("Perlu login, mencoba login...")
                            if not login_with_retry(driver, email, password):
                                add_account_to_cooldown(email)
                                logging.warning(f"Login gagal untuk {email}, beralih ke akun berikutnya")
                                send_login_failed(email)
                                current_account_index += 1
                                continue
                        
                        try:
                            # Enhanced download button detection and clicking
                            download_selectors = [
                                'a.btn.btn-default.addDownloadedBook',
                                'a[href*="download"]',
                                '.download-btn',
                                '.btn-download'
                            ]
                            
                            download_button = None
                            for selector in download_selectors:
                                try:
                                    download_button = WebDriverWait(driver, 10).until(
                                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                                    )
                                    logging.info(f"Download button found with selector: {selector}")
                                    break
                                except TimeoutException:
                                    continue
                            
                            if not download_button:
                                logging.error(f"Tombol download tidak ditemukan untuk {book_id}")
                                current_account_index += 1
                                continue
                            
                            # Click download button with enhanced handling
                            try:
                                driver.execute_script("arguments[0].removeAttribute('target'); arguments[0].click();", download_button)
                            except:
                                # Fallback to regular click
                                download_button.click()
                            
                            time.sleep(random.uniform(1, 3))  # Random delay
                            
                            # Handle multiple tabs/windows
                            original_handles = driver.window_handles
                            main_tab = original_handles[0]
                            limit_detected = False
                            
                            if len(driver.window_handles) > len(original_handles):
                                try:
                                    # Switch to new tab
                                    new_tab = [h for h in driver.window_handles if h not in original_handles][0]
                                    driver.switch_to.window(new_tab)
                                    
                                    # Wait for page to load and check for limit
                                    time.sleep(3)
                                    
                                    if check_limit_reached(driver):
                                        logging.warning(f"Limit tercapai untuk akun: {email}")
                                        stats["limit_hit"] += 1
                                        send_limit_hit(email)
                                        limit_detected = True
                                    
                                    driver.close()
                                except Exception as e:
                                    logging.warning(f"Error handling new tab: {e}")
                                finally:
                                    # Return to main tab
                                    if driver.window_handles:
                                        driver.switch_to.window(main_tab)
                            else:
                                # Check for limit in current tab
                                if check_limit_reached(driver):
                                    logging.warning(f"Limit tercapai untuk akun: {email}")
                                    stats["limit_hit"] += 1
                                    send_limit_hit(email)
                                    limit_detected = True
                            
                            if limit_detected:
                                smart_logout(driver)
                                current_account_index += 1
                                continue
                            
                            # Wait for download and rename file
                            book_row = {
                                'title': title,
                                'author': author,
                                'publisher': publisher,
                                'extension': extension
                            }
                            
                            new_filepath = wait_for_download_and_rename(download_full_path, book_row, timeout=120)
                            
                            if new_filepath:
                                update_book_status(book_id, 'done', new_filepath)
                                logging.info(f"✅ Sukses download: {book_id} - {title}")
                                stats["downloaded"] += 1
                                current_session_downloads += 1
                                download_successful = True
                                
                                # Periodic session refresh
                                if current_session_downloads >= SESSION_REUSE_THRESHOLD:
                                    logging.info("Melakukan refresh session preventif...")
                                    smart_logout(driver)
                                    current_session_downloads = 0
                                    
                            else:
                                logging.error(f"❌ Download timeout untuk {book_id}")
                                if book_retry_count >= max_book_retries:
                                    update_book_status(book_id, 'failed')
                                    stats["failed"] += 1
                                    download_successful = True
                                else:
                                    # Retry with exponential backoff
                                    retry_delay = exponential_backoff(book_retry_count - 1)
                                    logging.info(f"Retry download dalam {retry_delay:.2f} detik...")
                                    time.sleep(retry_delay)
                                    
                        except TimeoutException:
                            logging.error(f"Timeout mencari tombol download untuk {book_id}")
                            if book_retry_count >= max_book_retries:
                                update_book_status(book_id, 'failed')
                                stats["failed"] += 1
                                download_successful = True
                            else:
                                current_account_index += 1
                                
                        except WebDriverException as e:
                            logging.error(f"WebDriver error untuk {book_id}: {e}")
                            driver_restart_count += 1
                            
                            if driver_restart_count <= max_driver_restarts:
                                logging.info(f"Restarting driver ({driver_restart_count}/{max_driver_restarts})...")
                                try:
                                    driver.quit()
                                except:
                                    pass
                                time.sleep(5)
                                driver = setup_driver(download_full_path)
                                current_session_downloads = 0
                            else:
                                logging.error("Max driver restarts reached")
                                raise e
                                
                        except Exception as e:
                            logging.error(f"Unexpected error untuk {book_id}: {e}")
                            if book_retry_count >= max_book_retries:
                                update_book_status(book_id, 'failed')
                                stats["failed"] += 1
                                download_successful = True
                            else:
                                retry_delay = exponential_backoff(book_retry_count - 1)
                                time.sleep(retry_delay)
                    
                    # Small delay between books
                    time.sleep(random.uniform(0.5, 2.0))
                    
            except KeyboardInterrupt:
                logging.info("Program dihentikan oleh user")
                break
            except Exception as e:
                logging.error(f"Error dalam main loop: {e}")
                time.sleep(10)
                continue
                
    except Exception as e:
        logging.critical(f"Fatal error: {e}", exc_info=True)
        send_fatal_error(f"Fatal error: {e}", context='download_file.py')
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("Browser Selenium ditutup.")
            except:
                pass
        
        # Enhanced final report
        logging.info("\n" + "="*60)
        logging.info("--- LAPORAN AKHIR DOWNLOAD ---")
        logging.info(f"Total Buku Diproses    : {stats['processed']}")
        logging.info(f"Berhasil Diunduh       : {stats['downloaded']}")
        logging.info(f"Gagal Diunduh          : {stats['failed']}")
        logging.info(f"Akun Mencapai Limit    : {stats['limit_hit']}")
        logging.info(f"Error 505/HTTP         : {stats['errors_505']}")
        logging.info(f"Success Rate           : {(stats['downloaded']/max(stats['processed'], 1)*100):.1f}%")
        logging.info(f"Total Session Downloads: {current_session_downloads}")
        logging.info("="*60)
        send_batch_summary(stats['downloaded'], stats['failed'], batch_type='Download')

if __name__ == "__main__":
    main()
