import os
import telebot
import requests
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
from functools import wraps
import hashlib
import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Enhanced Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7825591642:AAGh4zVMhLdOSnW-FV-FPaq5f5OVxiia3xw')
API_BASE_URL = os.getenv('BOOK_API_BASE_URL', 'https://www.api.staisenorituban.ac.id')
API_SEARCH_URL = f"{API_BASE_URL}/search_books"
API_STATS_URL = f"{API_BASE_URL}/stats"
API_DIRECT_LINK_URL = f"{API_BASE_URL}/get_direct_link"
API_BOOKMARK_URL = f"{API_BASE_URL}/bookmark"
API_BOOK_DETAIL_URL = f"{API_BASE_URL}/book_detail"

# Enhanced Bot Settings
RESULTS_PER_PAGE = 5
MAX_SEARCH_RESULTS = 100
CACHE_TTL = 300  # 5 minutes cache
RATE_LIMIT_WINDOW = 60  # 1 minute
RATE_LIMIT_MAX_REQUESTS = 30
ADMIN_USER_IDS = [int(x) for x in os.getenv('ADMIN_USER_IDS', '').split(',') if x.strip()]

# Setup enhanced logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/telegram_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize bot with enhanced settings
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode='HTML', threaded=True)

# Enhanced state management with persistence
user_state = {}
user_cache = {}
rate_limit_tracker = {}
bot_stats = {
    'total_users': 0,
    'total_searches': 0,
    'total_downloads': 0,
    'start_time': datetime.now()
}

# Thread locks for thread safety
state_lock = threading.Lock()
cache_lock = threading.Lock()
stats_lock = threading.Lock()

class BotSession:
    """Enhanced user session management"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.last_query = None
        self.last_results = []
        self.current_page = 1
        self.bookmarks = []
        self.search_history = []
        self.last_activity = datetime.now()
        self.search_count = 0
        self.download_count = 0
        
    def update_activity(self):
        self.last_activity = datetime.now()
    
    def add_search(self, query: str, results_count: int):
        self.search_history.append({
            'query': query,
            'results': results_count,
            'timestamp': datetime.now().isoformat()
        })
        # Keep only last 10 searches
        self.search_history = self.search_history[-10:]
        self.search_count += 1
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'last_query': self.last_query,
            'current_page': self.current_page,
            'search_count': self.search_count,
            'download_count': self.download_count,
            'last_activity': self.last_activity.isoformat()
        }

def rate_limit_check(user_id: int) -> bool:
    """Enhanced rate limiting per user"""
    now = time.time()
    
    if user_id not in rate_limit_tracker:
        rate_limit_tracker[user_id] = []
    
    # Clean old requests
    rate_limit_tracker[user_id] = [
        req_time for req_time in rate_limit_tracker[user_id] 
        if now - req_time < RATE_LIMIT_WINDOW
    ]
    
    # Check if user has exceeded rate limit
    if len(rate_limit_tracker[user_id]) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    # Add current request
    rate_limit_tracker[user_id].append(now)
    return True

def get_user_session(user_id: int) -> BotSession:
    """Get or create user session"""
    with state_lock:
        if user_id not in user_state:
            user_state[user_id] = BotSession(user_id)
            with stats_lock:
                bot_stats['total_users'] += 1
        
        user_state[user_id].update_activity()
        return user_state[user_id]

def cache_get(key: str) -> Optional[Dict]:
    """Get cached data with TTL check"""
    with cache_lock:
        if key in user_cache:
            cached_data, timestamp = user_cache[key]
            if time.time() - timestamp < CACHE_TTL:
                return cached_data
            else:
                del user_cache[key]
    return None

def cache_set(key: str, data: Dict):
    """Set cached data with timestamp"""
    with cache_lock:
        user_cache[key] = (data, time.time())

def admin_required(func):
    """Decorator for admin-only commands"""
    @wraps(func)
    def wrapper(message):
        if message.from_user.id not in ADMIN_USER_IDS:
            bot.reply_to(message, "❌ Access denied. Admin privileges required.")
            return
        return func(message)
    return wrapper

def rate_limited(func):
    """Decorator for rate limiting"""
    @wraps(func)
    def wrapper(message):
        if not rate_limit_check(message.from_user.id):
            bot.reply_to(message, "⏳ Rate limit exceeded. Please wait a moment before trying again.")
            return
        return func(message)
    return wrapper

def error_handler(func):
    """Decorator for error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            if args and hasattr(args[0], 'chat'):
                bot.send_message(args[0].chat.id, "❌ An error occurred. Please try again later.")
    return wrapper

def make_api_request(url: str, params: Dict = None, timeout: int = 30) -> Optional[Dict]:
    """Enhanced API request with retry logic"""
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limited
                time.sleep(2 ** attempt)
                continue
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"API request failed (attempt {attempt + 1}): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    
    return None

def fetch_books(query: str, page: int = 1) -> tuple:
    """Enhanced book search with caching"""
    cache_key = f"search:{hashlib.md5(f'{query}:{page}'.encode()).hexdigest()}"
    
    # Try cache first
    cached_result = cache_get(cache_key)
    if cached_result:
        logger.info(f"Cache hit for search: {query}")
        return cached_result['results'], cached_result['total'], cached_result['all_results']
    
    # Make API request
    api_response = make_api_request(API_SEARCH_URL, {
        'q': query,
        'page': page,
        'per_page': RESULTS_PER_PAGE
    })
    
    if not api_response:
        return [], 0, []
    
    results = api_response.get('results', [])
    total = api_response.get('total', 0)
    
    # Cache the results
    cache_data = {
        'results': results,
        'total': total,
        'all_results': results
    }
    cache_set(cache_key, cache_data)
    
    return results, total, results

def fetch_stats() -> Optional[Dict]:
    """Fetch database statistics with caching"""
    cache_key = "stats"
    cached_stats = cache_get(cache_key)
    if cached_stats:
        return cached_stats
    
    stats = make_api_request(API_STATS_URL)
    if stats:
        cache_set(cache_key, stats)
    
    return stats

def create_main_keyboard():
    """Create main menu keyboard"""
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add(
        KeyboardButton("🔍 Search Books"),
        KeyboardButton("📊 Statistics")
    )
    keyboard.add(
        KeyboardButton("📚 My Bookmarks"),
        KeyboardButton("📋 Search History")
    )
    keyboard.add(KeyboardButton("ℹ️ Help"))
    return keyboard

def create_search_keyboard(query: str, page: int, total_pages: int, total_results: int):
    """Create enhanced search navigation keyboard"""
    keyboard = InlineKeyboardMarkup(row_width=3)
    
    # Pagination buttons
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"prev_{query}_{page-1}"))
    
    buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"next_{query}_{page+1}"))
    
    if buttons:
        keyboard.row(*buttons)
    
    # Action buttons
    action_buttons = []
    action_buttons.append(InlineKeyboardButton("🔄 New Search", callback_data="new_search"))
    action_buttons.append(InlineKeyboardButton("📊 Search Stats", callback_data=f"search_stats_{query}"))
    
    keyboard.row(*action_buttons)
    
    return keyboard

def format_book_info(book: Dict, index: int = None) -> str:
    """Enhanced book information formatting"""
    title = book.get('title', 'Unknown Title')
    author = book.get('author', 'Unknown Author')
    publisher = book.get('publisher', 'Unknown Publisher')
    extension = book.get('extension', 'Unknown')
    year = book.get('year', '')
    filesize = book.get('filesize', '')
    
    # Status indicators
    download_status = book.get('download_status', 'unknown')
    has_drive_link = bool(book.get('files_url_drive'))
    
    status_icon = {
        'done': '✅',
        'pending': '⏳',
        'in_progress': '🔄',
        'failed': '❌'
    }.get(download_status, '❓')
    
    drive_icon = '💾' if has_drive_link else '🔗'
    
    # Format message
    msg = f"{index}. <b>{title}</b>\n"
    msg += f"👤 <i>{author}</i>\n"
    msg += f"🏢 {publisher}"
    
    if year:
        msg += f" ({year})"
    
    msg += f"\n📄 {extension.upper()}"
    
    if filesize:
        msg += f" • {filesize}"
    
    msg += f"\n{status_icon} Status: {download_status.title()}"
    
    if has_drive_link:
        msg += f"\n{drive_icon} Available for download"
    
    return msg

@bot.message_handler(commands=['start', 'help'])
@error_handler
@rate_limited
def send_welcome(message):
    """Enhanced welcome message with user onboarding"""
    user = message.from_user
    session = get_user_session(user.id)
    
    welcome_msg = f"""
🎉 <b>Welcome to Book Search Bot!</b>

Hello {user.first_name}! I can help you find and download books from our extensive library.

📚 <b>What can I do?</b>
• Search books by title, author, or publisher
• Browse your search history
• Manage bookmarks
• Get download links
• View library statistics

🔍 <b>How to search:</b>
Just type what you're looking for, or use:
<code>/search [your query]</code>

📖 <b>Quick Commands:</b>
/search - Search for books
/bookmarks - View your favorites
/stats - Database statistics
/history - Your search history
/help - Show this help

Let's start exploring! What book are you looking for? 📖
"""
    
    keyboard = create_main_keyboard()
    bot.send_message(message.chat.id, welcome_msg, reply_markup=keyboard)
    
    logger.info(f"New user welcomed: {user.id} ({user.first_name})")

@bot.message_handler(commands=['search'])
@error_handler
@rate_limited
def handle_search_cmd(message):
    """Enhanced search command with validation"""
    query = message.text[len('/search'):].strip()
    
    if not query:
        bot.reply_to(message, """
🔍 <b>Search Books</b>

Please provide a search term after the command:
<code>/search [your query]</code>

<b>Examples:</b>
• <code>/search sapiens</code>
• <code>/search python programming</code>
• <code>/search harry potter</code>

Or simply type your search term without the command! 📚
""")
        return
    
    if len(query) < 2:
        bot.reply_to(message, "❌ Search query too short. Please use at least 2 characters.")
        return
    
    if len(query) > 100:
        bot.reply_to(message, "❌ Search query too long. Please use less than 100 characters.")
        return
    
    show_search_results(message, query, page=1)

@bot.message_handler(commands=['bookmarks'])
@error_handler
@rate_limited
def handle_bookmark(message):
    """Enhanced bookmark management"""
    user_id = message.from_user.id
    session = get_user_session(user_id)
    
    # Fetch bookmarks from API
    api_response = make_api_request(API_BOOKMARK_URL, {'user_id': str(user_id)})
    
    if not api_response:
        bot.reply_to(message, "❌ Failed to fetch bookmarks. Please try again later.")
        return
    
    bookmarks = api_response.get('results', [])
    
    if not bookmarks:
        msg = """
📚 <b>Your Bookmarks</b>

You don't have any bookmarks yet! 

<b>How to add bookmarks:</b>
1. Search for books
2. Use the ⭐ button on search results
3. Or reply to search results with <code>/fav [numbers]</code>

Start searching to build your collection! 🔍
"""
        bot.send_message(message.chat.id, msg)
        return
    
    msg = f"📚 <b>Your Bookmarks ({len(bookmarks)} books)</b>\n\n"
    
    for idx, book in enumerate(bookmarks[:10], 1):  # Limit to 10 for readability
        msg += format_book_info(book, idx) + "\n\n"
    
    if len(bookmarks) > 10:
        msg += f"... and {len(bookmarks) - 10} more books"
    
    # Create inline keyboard for bookmark actions
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("🗑️ Clear All", callback_data="clear_bookmarks"),
        InlineKeyboardButton("📤 Export", callback_data="export_bookmarks")
    )
    
    bot.send_message(message.chat.id, msg, reply_markup=keyboard, disable_web_page_preview=True)

@bot.message_handler(commands=['stats'])
@error_handler
@rate_limited
def handle_stats(message):
    """Enhanced statistics with bot metrics"""
    stats = fetch_stats()
    session = get_user_session(message.from_user.id)
    
    if not stats:
        bot.reply_to(message, "❌ Statistics temporarily unavailable. Please try again later.")
        return
    
    # Bot runtime
    runtime = datetime.now() - bot_stats['start_time']
    runtime_str = f"{runtime.days}d {runtime.seconds//3600}h {(runtime.seconds%3600)//60}m"
    
    msg = f"""
📊 <b>Library Statistics</b>

📚 <b>Database:</b>
• Total Books: <b>{stats.get('total', 0):,}</b>
• Downloaded: <b>{stats.get('downloaded', 0):,}</b> ({stats.get('download_rate', 0):.1f}%)
• Uploaded: <b>{stats.get('uploaded', 0):,}</b> ({stats.get('upload_rate', 0):.1f}%)
• With Covers: <b>{stats.get('cover', 0):,}</b>
• Failed: <b>{stats.get('failed', 0):,}</b>
• Pending: <b>{stats.get('pending', 0):,}</b>

🤖 <b>Bot Statistics:</b>
• Total Users: <b>{bot_stats['total_users']}</b>
• Total Searches: <b>{bot_stats['total_searches']}</b>
• Total Downloads: <b>{bot_stats['total_downloads']}</b>
• Runtime: <b>{runtime_str}</b>

👤 <b>Your Activity:</b>
• Searches: <b>{session.search_count}</b>
• Downloads: <b>{session.download_count}</b>
• Bookmarks: <b>{len(session.bookmarks)}</b>

📈 Last updated: {datetime.now().strftime('%H:%M:%S')}
"""
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats"),
        InlineKeyboardButton("📈 Detailed", callback_data="detailed_stats")
    )
    
    bot.send_message(message.chat.id, msg, reply_markup=keyboard)

@bot.message_handler(commands=['history'])
@error_handler
@rate_limited
def handle_search_history(message):
    """Show user's search history"""
    session = get_user_session(message.from_user.id)
    
    if not session.search_history:
        bot.reply_to(message, """
📋 <b>Search History</b>

You haven't made any searches yet!

Start searching to see your history here. 🔍
""")
        return
    
    msg = f"📋 <b>Your Search History</b>\n\n"
    
    for idx, search in enumerate(reversed(session.search_history[-10:]), 1):
        timestamp = datetime.fromisoformat(search['timestamp']).strftime('%m/%d %H:%M')
        msg += f"{idx}. <code>{search['query']}</code>\n"
        msg += f"   📊 {search['results']} results • {timestamp}\n\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("🗑️ Clear History", callback_data="clear_history"),
        InlineKeyboardButton("📊 Search Stats", callback_data="search_statistics")
    )
    
    bot.send_message(message.chat.id, msg, reply_markup=keyboard)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith('/fav'))
@error_handler
@rate_limited
def handle_fav(message):
    """Enhanced bookmark adding functionality"""
    user_id = message.from_user.id
    session = get_user_session(user_id)
    
    # /fav 1,2,3
    choices = message.text[len('/fav'):].replace(' ', '').split(',')
    
    added_count = 0
    for c in choices:
        try:
            idx = int(c) - 1
            if 0 <= idx < len(session.last_results):
                row = session.last_results[idx]
                if row not in session.bookmarks:
                    session.bookmarks.append(row)
                    added_count += 1
        except Exception:
            continue
    
    if added_count > 0:
        bot.reply_to(message, f"✅ Added {added_count} book(s) to your bookmarks.")
        with stats_lock:
            bot_stats['total_downloads'] += added_count
        session.download_count += added_count
    else:
        bot.reply_to(message, "❌ No valid book numbers found in your message.")

@bot.message_handler(func=lambda m: True)
@error_handler
@rate_limited
def handle_text(message):
    """Enhanced text message handler for search"""
    user_id = message.from_user.id
    session = get_user_session(user_id)
    
    # If user reply with a number, process choice
    if message.text.isdigit() or ',' in message.text:
        handle_choice(message)
        return
    
    # If not, assume it's a new query
    show_search_results(message, message.text.strip(), page=1)

def show_search_results(message, query, page=1):
    """Enhanced search results display with pagination"""
    results, total, all_results = fetch_books(query, page)
    
    if not results:
        bot.reply_to(message, "❌ No results found for your search.")
        return
    
    session = get_user_session(message.from_user.id)
    session.last_query = query
    session.last_results = results
    session.current_page = page
    
    # Update search count
    with stats_lock:
        bot_stats['total_searches'] += 1
    session.add_search(query, total)
    
    for idx, row in enumerate(results, 1):
        msg = (
            f"{idx}. <b>{row['title']}</b> - {row['author']} - {row['publisher']} [{row['extension']}]"
        )
        keyboard = telebot.types.InlineKeyboardMarkup()
        if row.get('files_url_drive'):
            keyboard.add(telebot.types.InlineKeyboardButton(
                "Download", callback_data=f"download_{row['id']}"
            ))
        # Pagination tombol Next/Prev hanya di hasil terakhir
        if idx == len(results):
            total_pages = (total + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
            keyboard = create_search_keyboard(query, page, total_pages, total)
        bot.send_message(message.chat.id, msg, parse_mode='HTML', reply_markup=keyboard, disable_web_page_preview=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('next_') or call.data.startswith('prev_'))
@error_handler
@rate_limited
def handle_pagination(call):
    """Enhanced pagination handler"""
    _, query, page = call.data.split('_', 2)
    show_search_results(call.message, query, int(page))
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('download_'))
@error_handler
@rate_limited
def handle_download(call):
    """Enhanced download handler"""
    book_id = call.data.split('_', 1)[1]
    resp = requests.get(f"{API_DIRECT_LINK_URL}/{book_id}")
    if resp.status_code == 200:
        data = resp.json()
        link = data.get('direct_link')
        if link:
            bot.send_message(call.message.chat.id, f"🔗 <a href=\"{link}\">Download File</a>", parse_mode='HTML')
            with stats_lock:
                bot_stats['total_downloads'] += 1
            get_user_session(call.message.from_user.id).download_count += 1
        else:
            bot.send_message(call.message.chat.id, "Link download tidak tersedia.")
    else:
        bot.send_message(call.message.chat.id, "File tidak ditemukan.")
    bot.answer_callback_query(call.id)

def handle_choice(message):
    """Enhanced choice processing for bookmarking"""
    user_id = message.from_user.id
    session = get_user_session(user_id)
    
    if not session.last_results:
        bot.reply_to(message, "❌ No search results to choose from. Please perform a search first.")
        return
    
    choices = message.text.replace(' ', '').split(',')
    reply = ""
    for c in choices:
        try:
            idx = int(c) - 1
            if 0 <= idx < len(session.last_results):
                row = session.last_results[idx]
                status = "✅ Sudah di GDrive" if row.get('files_url_drive') else "❌ Belum di GDrive"
                reply += (
                    f"📚 <b>{row['title']}</b>\n"
                    f"👤 {row['author']}\n"
                    f"🏢 {row['publisher']}\n"
                    f"🔗 <a href=\"{row['book_url']}\">Link Buku</a>\n"
                    f"{status}\n"
                )
                if row.get('files_url_drive'):
                    reply += f"🔗 <code>{row['files_url_drive']}</code>\n"
                reply += "\n"
        except Exception:
            continue
    if reply:
        bot.send_message(message.chat.id, reply, parse_mode='HTML', disable_web_page_preview=False)
    else:
        bot.reply_to(message, "❌ Invalid number. Please reply with numbers from the search results.")

@bot.callback_query_handler(func=lambda call: call.data == "new_search")
@error_handler
@rate_limited
def handle_new_search(call):
    """Handler for new search button"""
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="🔍 <b>Search Books</b>\n\nPlease provide a search term after the command:",
        reply_markup=None
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('search_stats_'))
@error_handler
@rate_limited
def handle_search_stats(call):
    """Handler for search stats button"""
    query = call.data.split('_', 1)[1]
    show_search_results(call.message, query, page=1)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "refresh_stats")
@error_handler
@rate_limited
def handle_refresh_stats(call):
    """Handler for refresh stats button"""
    handle_stats(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "detailed_stats")
@error_handler
@rate_limited
def handle_detailed_stats(call):
    """Handler for detailed stats button"""
    stats = fetch_stats()
    if not stats:
        bot.send_message(call.message.chat.id, "❌ Statistics temporarily unavailable.")
        bot.answer_callback_query(call.id)
        return
    
    msg = f"""
📊 <b>Detailed Statistics</b>

📚 <b>Database:</b>
• Total Books: <b>{stats.get('total', 0):,}</b>
• Downloaded: <b>{stats.get('downloaded', 0):,}</b> ({stats.get('download_rate', 0):.1f}%)
• Uploaded: <b>{stats.get('uploaded', 0):,}</b> ({stats.get('upload_rate', 0):.1f}%)
• With Covers: <b>{stats.get('cover', 0):,}</b>
• Failed: <b>{stats.get('failed', 0):,}</b>
• Pending: <b>{stats.get('pending', 0):,}</b>

🤖 <b>Bot Statistics:</b>
• Total Users: <b>{bot_stats['total_users']}</b>
• Total Searches: <b>{bot_stats['total_searches']}</b>
• Total Downloads: <b>{bot_stats['total_downloads']}</b>
• Runtime: <b>{datetime.now() - bot_stats['start_time']}</b>

📈 Last updated: {datetime.now().strftime('%H:%M:%S')}
"""
    bot.send_message(call.message.chat.id, msg, parse_mode='HTML')
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "clear_bookmarks")
@error_handler
@rate_limited
def handle_clear_bookmarks(call):
    """Handler for clear all bookmarks button"""
    user_id = call.from_user.id
    session = get_user_session(user_id)
    
    if not session.bookmarks:
        bot.send_message(call.message.chat.id, "❌ You have no bookmarks to clear.")
        bot.answer_callback_query(call.id)
        return
    
    confirm_msg = "⚠️ Are you sure you want to clear all your bookmarks? This action cannot be undone."
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ Yes", callback_data=f"confirm_clear_bookmarks_{user_id}"))
    keyboard.add(InlineKeyboardButton("❌ No", callback_data="noop"))
    
    bot.send_message(call.message.chat.id, confirm_msg, reply_markup=keyboard)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_clear_bookmarks_'))
@error_handler
@rate_limited
def handle_confirm_clear_bookmarks(call):
    """Handler for confirmation to clear bookmarks"""
    user_id = int(call.data.split('_', 1)[1])
    session = get_user_session(user_id)
    
    # Clear bookmarks in API
    api_response = make_api_request(API_BOOKMARK_URL, {'user_id': str(user_id)})
    if api_response and api_response.get('success'):
        session.bookmarks = []
        bot.send_message(call.message.chat.id, "✅ All your bookmarks have been cleared.")
        with stats_lock:
            bot_stats['total_downloads'] -= len(session.bookmarks) # Adjust total downloads
        session.download_count = 0
    else:
        bot.send_message(call.message.chat.id, "❌ Failed to clear bookmarks. Please try again later.")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "export_bookmarks")
@error_handler
@rate_limited
def handle_export_bookmarks(call):
    """Handler for export bookmarks button"""
    user_id = call.from_user.id
    session = get_user_session(user_id)
    
    if not session.bookmarks:
        bot.send_message(call.message.chat.id, "❌ You have no bookmarks to export.")
        bot.answer_callback_query(call.id)
        return
    
    # Create a zip file of bookmarks
    try:
        import zipfile
        import io
        from datetime import datetime
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for idx, book in enumerate(session.bookmarks, 1):
                title = re.sub(r'[\\/*?:"<>|]', '', book['title']) # Sanitize filename
                filename = f"{idx}_{title}.pdf" # Assuming PDF for now, adjust extension as needed
                zipf.writestr(filename, requests.get(book['book_url']).content)
        
        zip_buffer.seek(0)
        bot.send_document(call.message.chat.id, zip_buffer, caption="Your Bookmarks Export")
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error exporting bookmarks: {e}", exc_info=True)
        bot.send_message(call.message.chat.id, f"❌ Failed to export bookmarks: {e}")
        bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "clear_history")
@error_handler
@rate_limited
def handle_clear_history(call):
    """Handler for clear history button"""
    user_id = call.from_user.id
    session = get_user_session(user_id)
    
    if not session.search_history:
        bot.send_message(call.message.chat.id, "❌ Your search history is already empty.")
        bot.answer_callback_query(call.id)
        return
    
    confirm_msg = "⚠️ Are you sure you want to clear all your search history? This action cannot be undone."
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ Yes", callback_data=f"confirm_clear_history_{user_id}"))
    keyboard.add(InlineKeyboardButton("❌ No", callback_data="noop"))
    
    bot.send_message(call.message.chat.id, confirm_msg, reply_markup=keyboard)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_clear_history_'))
@error_handler
@rate_limited
def handle_confirm_clear_history(call):
    """Handler for confirmation to clear history"""
    user_id = int(call.data.split('_', 1)[1])
    session = get_user_session(user_id)
    
    # Clear search history in API
    api_response = make_api_request(API_BOOK_DETAIL_URL, {'user_id': str(user_id)})
    if api_response and api_response.get('success'):
        session.search_history = []
        bot.send_message(call.message.chat.id, "✅ All your search history has been cleared.")
    else:
        bot.send_message(call.message.chat.id, "❌ Failed to clear search history. Please try again later.")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "search_statistics")
@error_handler
@rate_limited
def handle_search_statistics(call):
    """Handler for search stats button in history"""
    query = call.message.text.split('\n')[1].split('•')[1].strip() # Extract query from history message
    show_search_results(call.message, query, page=1)
    bot.answer_callback_query(call.id)

if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling() 
