import os
import re
import time
import pandas as pd
import logging
import sys
import requests
from datetime import datetime
from tqdm import tqdm
from PIL import Image, ImageDraw, ImageFilter
import cloudinary
import cloudinary.uploader
import config
from notify import send_fatal_error, send_batch_summary

def setup_logging():
    log_directory = "log"
    os.makedirs(log_directory, exist_ok=True)
    log_filename = datetime.now().strftime(f"{log_directory}/log_cover_pipeline_%Y-%m-%d_%H-%M-%S.txt")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.FileHandler(log_filename, 'w', 'utf-8'), logging.StreamHandler(sys.stdout)])
    logging.info("Sistem logging Cover Pipeline diinisialisasi.")

def sanitize_filename(name):
    if not isinstance(name, str) or pd.isna(name):
        return "untitled"
    name = name.replace(' ', '_')
    name = re.sub(r'[^A-Za-z0-9_]', '', name)
    return name.strip() or "untitled"

def setup_cloudinary():
    cloudinary.config(
        cloud_name=config.CLOUDINARY_CLOUD_NAME,
        api_key=config.CLOUDINARY_API_KEY,
        api_secret=config.CLOUDINARY_API_SECRET,
        secure=True
    )
    logging.info("Konfigurasi Cloudinary berhasil diatur.")

def upload_to_cloudinary(file_path, file_name, folder="book_covers"):
    try:
        if not file_name:
            raise ValueError("Nama file kosong.")
        logging.info(f"Mengunggah '{file_name}' ke Cloudinary...")
        response = cloudinary.uploader.upload(
            file_path,
            public_id=f"{folder}/{file_name.rsplit('.', 1)[0]}",
            overwrite=True,
            resource_type="image",
            timeout=30
        )
        url = response.get("secure_url")
        if url:
            logging.info("Upload ke Cloudinary berhasil!")
            return url
        else:
            logging.error("Upload berhasil tapi URL tidak ditemukan.")
            return None
    except Exception as e:
        logging.error(f"Gagal mengunggah ke Cloudinary: {e}")
        return None

def apply_transformation(bg_path, cover_path, output_path, settings):
    try:
        bg_image = Image.open(bg_path).convert("RGBA")
        cover_image = Image.open(cover_path).convert("RGBA")

        bordered_cover = Image.new("RGBA", (cover_image.width + 2 * settings['border_size'], cover_image.height + 2 * settings['border_size']), "white")
        bordered_cover.paste(cover_image, (settings['border_size'], settings['border_size']))

        w_b, h_b = bordered_cover.size
        aspect_ratio = w_b / h_b
        new_h = settings['target_cover_height']
        new_w = int(new_h * aspect_ratio)
        resized_cover = bordered_cover.resize((new_w, new_h), Image.Resampling.LANCZOS)

        radius = settings['corner_radius']
        mask = Image.new('L', resized_cover.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, resized_cover.width, resized_cover.height), radius=radius, fill=255)
        rounded_cover = resized_cover
        rounded_cover.putalpha(mask)

        shadow_canvas = Image.new('RGBA', rounded_cover.size, (0,0,0,0))
        shadow_draw = ImageDraw.Draw(shadow_canvas)
        shadow_color = (settings['shadow_color_r'], settings['shadow_color_g'], settings['shadow_color_b'], settings['shadow_color_alpha'])
        shadow_draw.rounded_rectangle((0, 0, rounded_cover.width, rounded_cover.height), radius=radius, fill=shadow_color)
        blurred_shadow = shadow_canvas.filter(ImageFilter.GaussianBlur(radius=settings['shadow_blur_radius']))

        final_image = bg_image.copy()
        shadow_pos = ( (bg_image.width - new_w) // 2 + settings['shadow_offset_x'], (bg_image.height - new_h) // 2 + settings['shadow_offset_y'] )
        cover_pos = ( (bg_image.width - new_w) // 2, (bg_image.height - new_h) // 2 )

        final_image.paste(blurred_shadow, shadow_pos, blurred_shadow)
        final_image.paste(rounded_cover, cover_pos, rounded_cover)

        final_image = final_image.convert("RGB")
        final_image.save(output_path, "JPEG", quality=85)
        logging.info("🖼️ Gambar sampul berhasil ditransformasi.")
        return True
    except Exception as e:
        logging.error(f"❌ Gagal memproses '{os.path.basename(cover_path)}': {e}")
        return False

def main():
    setup_logging()
    try:
        csv_filename = config.OUTPUT_FILENAME
        bg_path = config.BACKGROUND_IMAGE_PATH
        setup_cloudinary()
        transform_settings = config.IMAGE_TRANSFORM_SETTINGS
        temp_img_dir = "temp_img_covers"
        os.makedirs(temp_img_dir, exist_ok=True)

        df = pd.read_csv(csv_filename)
        logging.info(f"Berhasil membaca '{csv_filename}'.")

        if 'cover_url_final' not in df.columns:
            df['cover_url_final'] = pd.NA
        df['cover_url_final'] = df['cover_url_final'].astype('object')

        books_to_process = df[(df['cover_image_url'].notna()) & (df['cover_url_final'].isna())].copy()
        if books_to_process.empty:
            logging.info("✅ Semua sampul buku sudah diproses. Tidak ada pekerjaan baru.")
            return

        logging.info(f"Ditemukan {len(books_to_process)} sampul baru untuk diproses.")

        save_counter = 0
        failed_counter = 0
        for index, row in tqdm(books_to_process.iterrows(), total=len(books_to_process), desc="Memproses Sampul"):
            title = str(row.get('title', 'untitled'))
            short_title = title[:50]
            original_url = row['cover_image_url']

            temp_path_original = os.path.join(temp_img_dir, f"{index}_original.jpg")
            try:
                original_url_fixed = re.sub(r"/covers\d+/", "/covers1000/", str(original_url))
                response = requests.get(original_url_fixed, timeout=20)
                response.raise_for_status()
                with open(temp_path_original, 'wb') as f:
                    f.write(response.content)
            except requests.exceptions.RequestException as e:
                logging.error(f"Gagal mengunduh sampul untuk '{short_title}...': {e}")
                failed_counter += 1
                continue

            temp_path_processed = os.path.join(temp_img_dir, f"{index}_processed.jpg")
            success = apply_transformation(bg_path, temp_path_original, temp_path_processed, transform_settings)

            if success:
                final_filename = f"{sanitize_filename(title)[:100]}.jpg"
                cloud_url = upload_to_cloudinary(temp_path_processed, final_filename)
                if cloud_url:
                    df.loc[index, 'cover_url_final'] = cloud_url
                    save_counter += 1
                else:
                    failed_counter += 1
                    logging.error(f"Gagal upload ke Cloudinary untuk '{short_title}'")
            else:
                failed_counter += 1
                logging.error(f"Gagal transformasi gambar untuk '{short_title}'")

            if os.path.exists(temp_path_original):
                os.remove(temp_path_original)
            if os.path.exists(temp_path_processed):
                os.remove(temp_path_processed)

            if save_counter > 0 and save_counter % 25 == 0:
                logging.info(f"\n--- BATCH SAVE --- Menyimpan progres setelah memproses {save_counter} sampul...")
                df.to_csv(csv_filename, index=False, encoding='utf-8-sig')

        logging.info("\nMenyimpan sisa progres terakhir...")
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        logging.info("Pipeline gambar selesai.")
        send_batch_summary(save_counter, failed_counter, batch_type='Cover', extra='Pipeline gambar selesai.')

    except Exception:
        logging.critical("Terjadi error fatal.", exc_info=True)
        send_fatal_error("Terjadi error fatal.", context='download_coverc.py')

if __name__ == "__main__":
    main()
