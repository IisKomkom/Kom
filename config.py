import os

# Automatically detect the base directory (folder where config.py is located)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==============================================================================
# Z-LIBRARY SCRAPER CONFIGURATION
# ==============================================================================

# --- Z-Library Base URL and Authentication ---
BASE_URL = "https://z-library.sk/"

# List of cookie JSON sets for authentication fallback.
FALLBACK_COOKIES_JSON = [
    # Primary Cookies (Account 1)
    """
    [
    {"domain": ".z-library.sk", "expirationDate": 1756204781.177271, "hostOnly": false, "httpOnly": false, "name": "remix_userid", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": null, "value": "6896047"},
    {"domain": ".z-library.sk", "expirationDate": 1754920581, "hostOnly": false, "httpOnly": false, "name": "zlib-searchSettings", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": null, "value": "%7B%22length%22%3A0%7D"},
    {"domain": ".z-library.sk", "expirationDate": 1755165365, "hostOnly": false, "httpOnly": false, "name": "zlib-searchOrder", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": null, "value": "year"},
    {"domain": ".z-library.sk", "expirationDate": 1756204781.177198, "hostOnly": false, "httpOnly": false, "name": "remix_userkey", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": null, "value": "4b80d03d9fd7b77e896552f3d9bc41be"},
    {"domain": ".z-library.sk", "expirationDate": 1755283180.655748, "hostOnly": false, "httpOnly": false, "name": "selectedSiteMode", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": null, "value": "books"},
    {"domain": ".z-library.sk", "expirationDate": 1786632153.387159, "hostOnly": false, "httpOnly": false, "name": "siteLanguage", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": null, "value": "en"},
    {"domain": ".z-library.sk", "expirationDate": 1755183577, "hostOnly": false, "httpOnly": false, "name": "zlib-searchView", "path": "/", "sameSite": "no_restriction", "secure": true, "session": false, "storeId": null, "value": "list"}
    ]
    """,
    # Fallback Cookies (Account 2) - Optional
    """
    [
        {"name": "remix_sessionid", "value": "paste_sessionid_for_account_2_here"},
        {"name": "remix_userkey", "value": "paste_userkey_for_account_2_here"}
    ]
    """
]

# --- Scraping Parameters ---
LANGUAGES_TO_SCRAPE = ["indonesian", "english"]
FILE_EXTENSIONS = ["MOBI", "PDF", "EPUB", "DJVU", "CBZ"]
SORT_ORDERS = ["popular", "year", "date", "titleA"]
MAX_PAGES_PER_ORDER = 10
CUSTOM_QUERIES = ["", ""]
MAX_DATA_PER_KEYWORD = 0  # 0/None for unlimited

# --- File Paths (Unified for all scripts) ---
KEYWORD_LIST_CSV = os.path.join(BASE_DIR, "keyword_list.csv")
OUTPUT_FILENAME = os.path.join(BASE_DIR, "data", "csv", "zlibrary_scraped_books.csv")
ACCOUNTS_CSV = os.path.join(BASE_DIR, "data", "csv", "akun.csv")
DOWNLOAD_DIR = "download_files"  # relative to project root
BACKGROUND_IMAGE_PATH = os.path.join(BASE_DIR, "data", "image", "bg.png")
# Google Sheets keyword list (export CSV URL)
KEYWORD_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1Mk9HwWQLPsUc-0LlltjA_KlOsO5cvlC8XkyB6uVpBdE/export?format=csv"

# --- API Integration ---
API_URL = "https://www.api.staisenorituban.ac.id/upload_data"
# Endpoint untuk claim batch buku download
API_CLAIM_URL = "https://www.api.staisenorituban.ac.id/claim_books"

# --- ImageKit (if used) ---
IMAGEKIT_PRIVATE_KEY = "private_J1/4FQ81jMIoNRGmn3KP/DbEIW0="
IMAGEKIT_PUBLIC_KEY = "public_mg/N0MGJvDD1prirfhnoPWpgxyk="
IMAGEKIT_URL_ENDPOINT = "https://ik.imagekit.io/uj3f2gmukl"

# --- Image Transformation Settings ---
IMAGE_TRANSFORM_SETTINGS = {
    'border_size': 50,
    'corner_radius': 25,
    'target_cover_height': 675,
    'shadow_color_r': 0,
    'shadow_color_g': 0,
    'shadow_color_b': 0,
    'shadow_color_alpha': 200,
    'shadow_offset_x': 15,
    'shadow_offset_y': 15,
    'shadow_blur_radius': 40
}

# --- Cloudinary ---
CLOUDINARY_CLOUD_NAME = "duwgvawwz"
CLOUDINARY_API_KEY = "126294172827318"
CLOUDINARY_API_SECRET = "Yc-2V2krS7lIc-E9lH2sfEUK9WA"

# --- Optional: Start/End Row for Download (None means all) ---
START_ROW = None
END_ROW = None


