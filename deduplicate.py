import pandas as pd
import logging
import sys
import os
from datetime import datetime
import config
from notify import send_fatal_error, send_batch_summary

def setup_logging():
    os.makedirs("log", exist_ok=True)
    log_file = datetime.now().strftime("log/log_deduplicate_%Y-%m-%d_%H-%M-%S.txt")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, 'w', 'utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("Deduplication process started.")

def main():
    setup_logging()
    try:
        if not os.path.exists(config.OUTPUT_FILENAME):
            logging.error(f"File {config.OUTPUT_FILENAME} tidak ditemukan.")
            send_fatal_error(f"File {config.OUTPUT_FILENAME} tidak ditemukan.", context='deduplicate.py')
            sys.exit(1)
        # Backup sebelum overwrite
        backup_path = f"{config.OUTPUT_FILENAME}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.rename(config.OUTPUT_FILENAME, backup_path)
        df = pd.read_csv(backup_path)
        before = len(df)
        df.drop_duplicates(subset=['id', 'title'], inplace=True)
        after = len(df)
        df.to_csv(config.OUTPUT_FILENAME, index=False, encoding='utf-8-sig')
        logging.info(f"Dedup selesai. Sebelum: {before} | Sesudah: {after} | Duplikat dihapus: {before-after}")
        send_batch_summary(after, before-after, batch_type='Dedup', extra='Dedup selesai.')
    except Exception as e:
        logging.error(f"❌ Error saat dedup: {e}")
        send_fatal_error(f"Error saat dedup: {e}", context='deduplicate.py')
        sys.exit(1)

if __name__ == "__main__":
    main()
