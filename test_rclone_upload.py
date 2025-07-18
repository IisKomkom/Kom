import os
import subprocess
import logging
import requests
import config
import socket
from notify import send_batch_summary, send_fatal_error

# Configuration
DOWNLOAD_DIR = 'download_files'
RCLONE_REMOTE_PREFIXES = ['gdrive1', 'gdrive2', 'gdrive3']  # Use your actual remote names
REMOTE_FOLDER = 'ebook'
RCLONE_CONFIG = os.path.join('data', 'rclone.conf')
SERVICE_ACCOUNTS_DIR = 'service_accounts'
RCLONE_EXE = os.path.join(os.getcwd(), 'rclone-v1.70.3-windows-amd64', 'rclone.exe')
API_CLAIM_UPLOAD_BATCH = getattr(config, 'API_CLAIM_UPLOAD_BATCH', 'https://www.api.staisenorituban.ac.id/claim_upload_batch')
API_UPDATE_URL = config.API_URL
BATCH_SIZE = int(os.environ.get('UPLOAD_BATCH_SIZE', 10))
INSTANCE_ID = os.environ.get('INSTANCE_ID') or socket.gethostname() or 'uploader'

# Prepare logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def claim_upload_batch(batch_size=BATCH_SIZE, instance_id=INSTANCE_ID):
    try:
        resp = requests.post(
            API_CLAIM_UPLOAD_BATCH,
            json={"batch_size": batch_size, "instance_id": instance_id},
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.error(f'Gagal claim upload batch dari API: {e}')
        return []

def update_upload_status(book_id, files_url_drive, files_url_share, files_url_direct):
    data = {
        "id": book_id,
        "files_url_drive": files_url_drive,
        "files_url_share": files_url_share,
        "files_url_direct": files_url_direct
    }
    try:
        resp = requests.post(API_UPDATE_URL, json=data, timeout=30)
        if resp.status_code in [200, 201]:
            logging.info(f"Update upload status sukses untuk {book_id}")
        else:
            logging.error(f"Update upload status gagal untuk {book_id}: {resp.status_code} - {resp.text}")
    except Exception as e:
        logging.error(f"Exception update upload status ke API untuk {book_id}: {e}")

def get_direct_download_link(share_link):
    import re
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', share_link)
    if match:
        file_id = match.group(1)
        return f'https://drive.google.com/uc?export=download&id={file_id}'
    return ''

def main():
    # Gather service account files
    service_accounts = sorted([
        os.path.join(SERVICE_ACCOUNTS_DIR, f)
        for f in os.listdir(SERVICE_ACCOUNTS_DIR)
        if f.endswith('.json')
    ])
    if not service_accounts:
        logging.error('No service account JSON files found!')
        return
    logging.info(f"Service accounts found: {service_accounts}")

    books = claim_upload_batch()
    if not books:
        logging.info('Tidak ada file siap upload.')
        return

    files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
    if not files:
        logging.warning('No files to upload in download_files.')
        return

    try:
        success_count = 0
        failed_count = 0
        current_remote = 0
        for book in books:
            # Cari file lokal berdasarkan metadata buku
            # Misal: nama file = "{title} - {author}.pdf" atau pola lain sesuai download_file.py
            title = book.get('title', '').strip()
            author = book.get('author', '').strip()
            publisher = book.get('publisher', '').strip()
            extension = book.get('extension', 'pdf').strip()
            name_part = f"{title} - {author}" if author else f"{title} - {publisher}"
            filename = f"{name_part}.{extension}"
            local_path = os.path.join(DOWNLOAD_DIR, filename)
            if not os.path.exists(local_path):
                logging.warning(f"File tidak ditemukan: {local_path}")
                failed_count += 1
                continue
            uploaded = False
            share_link = ''
            direct_link = ''
            while current_remote < len(RCLONE_REMOTE_PREFIXES):
                remote_path = f"{RCLONE_REMOTE_PREFIXES[current_remote]}:{REMOTE_FOLDER}/{filename}"
                logging.info(f"Uploading {filename} to {remote_path} ...")
                result = subprocess.run([
                    RCLONE_EXE, '--config', RCLONE_CONFIG,
                    'copyto', local_path, remote_path
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    logging.info(f"SUCCESS: {filename} uploaded to {RCLONE_REMOTE_PREFIXES[current_remote]}")
                    # Get share link
                    result_link = subprocess.run([
                        RCLONE_EXE, '--config', RCLONE_CONFIG,
                        'link', remote_path
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if result_link.returncode == 0:
                        share_link = result_link.stdout.strip()
                        direct_link = get_direct_download_link(share_link)
                        logging.info(f"Share link: {share_link}")
                        logging.info(f"Direct download link: {direct_link}")
                    else:
                        logging.warning(f"Failed to get share link for {filename}: {result_link.stderr}")
                        share_link = ''
                        direct_link = ''
                    # Update ke API
                    update_upload_status(book['id'], remote_path, share_link, direct_link)
                    uploaded = True
                    success_count += 1
                    try:
                        os.remove(local_path)
                        logging.info(f"File lokal dihapus: {local_path}")
                    except Exception as e:
                        logging.warning(f"Gagal menghapus file lokal {local_path}: {e}")
                    break
                elif 'quotaExceeded' in result.stderr or 'userRateLimitExceeded' in result.stderr:
                    logging.warning(f"Quota hit for {RCLONE_REMOTE_PREFIXES[current_remote]}, switching to next account.")
                    current_remote += 1
                else:
                    logging.error(f"FAILED: {filename} | Error: {result.stderr}")
                    failed_count += 1
                    break
            if not uploaded:
                logging.error(f"All accounts exhausted or failed for {filename}.")
                failed_count += 1
                break
        send_batch_summary(success_count, failed_count, batch_type='Upload')
    except Exception as e:
        logging.error(f"Fatal error in upload: {e}")
        send_fatal_error(str(e), context='test_rclone_upload.py')

if __name__ == "__main__":
    main() 