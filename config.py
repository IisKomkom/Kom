import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'freeware_bot'),
    'port': int(os.getenv('DB_PORT', 3306))
}

# Cloud Storage Configuration
MEDIAFIRE_CONFIG = {
    'email': os.getenv('MEDIAFIRE_EMAIL'),
    'password': os.getenv('MEDIAFIRE_PASSWORD'),
    'api_key': os.getenv('MEDIAFIRE_API_KEY')
}

MEGA_CONFIG = {
    'email': os.getenv('MEGA_EMAIL'),
    'password': os.getenv('MEGA_PASSWORD')
}

GDRIVE_CONFIG = {
    'service_account_file': os.getenv('GDRIVE_SERVICE_ACCOUNT'),
    'folder_id': os.getenv('GDRIVE_FOLDER_ID')
}

# Rclone Configuration
RCLONE_CONFIG = {
    'config_file': os.getenv('RCLONE_CONFIG', '~/.config/rclone/rclone.conf'),
    'mediafire_remote': 'mediafire:',
    'mega_remote': 'mega:',
    'gdrive_remote': 'gdrive:'
}

# Target Websites Configuration
TARGET_SITES = {
    'filecr': {
        'base_url': 'https://filecr.com',
        'categories': [
            '/category/windows/',
            '/category/macos/',
            '/category/android/',
            '/category/games/'
        ],
        'selectors': {
            'title': 'h1.entry-title',
            'download_link': 'a[href*="download"]',
            'description': '.entry-content p',
            'version': '.version',
            'size': '.size',
            'category': '.category'
        }
    },
    'nasbandia': {
        'base_url': 'https://nasbandia.com',
        'categories': [
            '/category/software/',
            '/category/games/',
            '/category/mobile/'
        ],
        'selectors': {
            'title': 'h1.post-title',
            'download_link': 'a[href*="link"]',
            'description': '.post-content',
            'version': '.version-info',
            'size': '.file-size'
        }
    },
    'downloadly': {
        'base_url': 'https://downloadly.ir',
        'categories': [
            '/software/',
            '/games/',
            '/mobile/'
        ],
        'selectors': {
            'title': 'h1.title',
            'download_link': 'a.download-btn',
            'description': '.content',
            'version': '.version',
            'size': '.size'
        }
    },
    'apptorent': {
        'base_url': 'https://apptorent.ru',
        'categories': [
            '/windows/',
            '/macos/',
            '/android/'
        ],
        'selectors': {
            'title': 'h1.entry-title',
            'download_link': 'a[href*="torrent"]',
            'description': '.post-content',
            'version': '.version',
            'size': '.torrent-size'
        }
    }
}

# Additional Freeware Sites
ADDITIONAL_SITES = {
    'softpedia': 'https://www.softpedia.com',
    'majorgeeks': 'https://www.majorgeeks.com',
    'techspot': 'https://www.techspot.com/downloads/',
    'ninite': 'https://ninite.com',
    'portableapps': 'https://portableapps.com',
    'fosshub': 'https://www.fosshub.com',
    'sourceforge': 'https://sourceforge.net'
}

# Scraping Configuration
SCRAPING_CONFIG = {
    'delay_between_requests': 2,
    'max_retries': 3,
    'timeout': 30,
    'user_agents': [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ],
    'headers': {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
}

# Download Configuration
DOWNLOAD_CONFIG = {
    'download_folder': './downloads/',
    'max_file_size': 5 * 1024 * 1024 * 1024,  # 5GB
    'allowed_extensions': ['.exe', '.msi', '.dmg', '.app', '.apk', '.zip', '.rar', '.7z'],
    'chunk_size': 8192,
    'concurrent_downloads': 3
}

# Schedule Configuration
SCHEDULE_CONFIG = {
    'update_frequency': 'weekly',  # weekly, daily, hourly
    'update_day': 'monday',
    'update_time': '02:00',
    'check_interval': 60  # minutes
}

# HTML Template Configuration
HTML_CONFIG = {
    'template_folder': './templates/',
    'output_folder': './html_output/',
    'items_per_page': 50,
    'theme': 'modern'
}

# Logging Configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'bot.log',
    'max_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5
}


