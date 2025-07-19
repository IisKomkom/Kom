#!/usr/bin/env python3
"""
User Book Request Bot
Allows users to search books and add them to request lists
Sends notifications to admin via WhatsApp
"""

import os
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
import threading
from admin_database import get_admin_db

# Try to import Telegram bot libraries
try:
    import telebot
    from telebot.types import (
        InlineKeyboardMarkup, InlineKeyboardButton,
        ReplyKeyboardMarkup, KeyboardButton, Message
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logging.warning("Telegram libraries not available")
    
    # Create dummy classes for testing
    class Message:
        def __init__(self):
            self.chat = type('obj', (object,), {'id': 0})()
            self.from_user = type('obj', (object,), {'id': 0, 'first_name': 'Test'})()
            self.text = ""
    
    class InlineKeyboardMarkup:
        def __init__(self, *args, **kwargs):
            pass
    
    class InlineKeyboardButton:
        def __init__(self, *args, **kwargs):
            pass

# Bot configuration
BOT_TOKEN = os.getenv('USER_BOT_TOKEN', '7825591642:AAGh4zVMhLdOSnW-FV-FPaq5f5OVxiia3xw')
ADMIN_PHONE = "085799520350"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/user_book_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class UserBookBot:
    """Enhanced user book request bot"""
    
    def __init__(self):
        self.admin_db = get_admin_db()
        self.user_sessions = {}  # user_id -> session_data
        self.session_lock = threading.Lock()
        
        if TELEGRAM_AVAILABLE:
            self.bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
            self.setup_handlers()
            logger.info("✅ Telegram bot initialized")
        else:
            logger.warning("⚠️ Telegram bot not available")
    
    def setup_handlers(self):
        """Setup Telegram bot handlers"""
        if not TELEGRAM_AVAILABLE:
            return
        
        @self.bot.message_handler(commands=['start'])
        def handle_start(message):
            self.cmd_start(message)
        
        @self.bot.message_handler(commands=['help'])
        def handle_help(message):
            self.cmd_help(message)
        
        @self.bot.message_handler(commands=['search'])
        def handle_search(message):
            self.cmd_search(message)
        
        @self.bot.message_handler(commands=['list', 'cart', 'mylist'])
        def handle_list(message):
            self.cmd_view_list(message)
        
        @self.bot.message_handler(commands=['submit'])
        def handle_submit(message):
            self.cmd_submit_request(message)
        
        @self.bot.message_handler(commands=['clear'])
        def handle_clear(message):
            self.cmd_clear_list(message)
        
        @self.bot.message_handler(commands=['stats'])
        def handle_stats(message):
            self.cmd_stats(message)
        
        @self.bot.message_handler(func=lambda message: True)
        def handle_text(message):
            self.handle_text_message(message)
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            self.handle_callback_query(call)
    
    def get_user_session(self, user_id: int) -> Dict:
        """Get or create user session"""
        with self.session_lock:
            if user_id not in self.user_sessions:
                session_id = self.admin_db.create_user_request(str(user_id))
                self.user_sessions[user_id] = {
                    'session_id': session_id,
                    'last_activity': datetime.now(),
                    'search_results': [],
                    'current_page': 1,
                    'last_query': ''
                }
            
            # Update last activity
            self.user_sessions[user_id]['last_activity'] = datetime.now()
            return self.user_sessions[user_id]
    
    def create_main_keyboard(self):
        """Create main menu keyboard"""
        keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        keyboard.add(
            KeyboardButton("🔍 Search Books"),
            KeyboardButton("📚 My List")
        )
        keyboard.add(
            KeyboardButton("📤 Submit Request"),
            KeyboardButton("🗑️ Clear List")
        )
        keyboard.add(KeyboardButton("ℹ️ Help"))
        return keyboard
    
    def cmd_start(self, message: Message):
        """Handle /start command"""
        user = message.from_user
        session = self.get_user_session(user.id)
        
        welcome_msg = f"""
🎉 <b>Welcome to Book Request Bot!</b>

Hello {user.first_name}! I can help you find and request books from our extensive library.

📚 <b>How it works:</b>
1. 🔍 Search for books you want
2. ➕ Add books to your request list
3. 📤 Submit your request to admin
4. ⏳ Wait for admin approval
5. 📥 Receive download links via WhatsApp

🆔 <b>Your Session ID:</b> <code>{session['session_id']}</code>

<b>Quick Commands:</b>
• /search [query] - Search for books
• /list - View your current list
• /submit - Submit request to admin
• /clear - Clear your list
• /help - Show help

Start by searching for books! 📖
"""
        
        keyboard = self.create_main_keyboard()
        self.bot.send_message(message.chat.id, welcome_msg, reply_markup=keyboard)
        
        logger.info(f"User {user.id} ({user.first_name}) started bot with session {session['session_id']}")
    
    def cmd_help(self, message: Message):
        """Handle /help command"""
        help_msg = """
📖 <b>Book Request Bot Help</b>

<b>🔍 Searching Books:</b>
• Type any book title, author, or publisher
• Use /search [query] command
• Example: <code>/search python programming</code>

<b>➕ Adding Books to List:</b>
• Click ➕ button next to search results
• Books are automatically added to your list
• You can add multiple books

<b>📚 Managing Your List:</b>
• /list - View current books in your list
• Remove books using ❌ button
• /clear - Clear entire list

<b>📤 Submitting Requests:</b>
• /submit - Send your list to admin
• Admin will receive WhatsApp notification
• Wait for approval and download links

<b>📱 Contact Info:</b>
• Admin WhatsApp: +62 857-9952-0350
• Include your Session ID in messages

<b>💡 Tips:</b>
• Search is case-insensitive
• Try different keywords if no results
• Books marked ✅ are immediately available
• Books marked ❌ may take longer to process

Need help? Contact the admin! 📞
"""
        
        self.bot.send_message(message.chat.id, help_msg)
    
    def cmd_search(self, message: Message):
        """Handle /search command"""
        query = message.text[len('/search'):].strip()
        
        if not query:
            self.bot.reply_to(message, """
🔍 <b>Search Books</b>

Please provide a search term:
<code>/search [your query]</code>

<b>Examples:</b>
• <code>/search python programming</code>
• <code>/search stephen king</code>
• <code>/search database design</code>

Or simply type your search term without the command! 📚
""")
            return
        
        self.perform_search(message, query)
    
    def perform_search(self, message: Message, query: str, page: int = 1):
        """Perform book search and display results"""
        try:
            user_id = message.from_user.id
            session = self.get_user_session(user_id)
            
            # Update session
            session['last_query'] = query
            session['current_page'] = page
            
            # Search books
            offset = (page - 1) * 10
            results = self.admin_db.search_books(query, limit=10, offset=offset)
            
            if not results:
                self.bot.send_message(message.chat.id, f"❌ No books found for '{query}'. Try different keywords.")
                return
            
            # Store results in session
            session['search_results'] = results
            
            # Send search results
            self.send_search_results(message, query, results, page)
            
            logger.info(f"User {user_id} searched '{query}' - {len(results)} results")
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            self.bot.send_message(message.chat.id, "❌ Search error. Please try again.")
    
    def send_search_results(self, message: Message, query: str, results: List[Dict], page: int):
        """Send formatted search results"""
        header_msg = f"🔍 <b>Search Results for:</b> '{query}'\n📄 Page {page} • {len(results)} books found\n"
        self.bot.send_message(message.chat.id, header_msg)
        
        for i, book in enumerate(results, 1):
            # Format book info
            book_msg = f"📚 <b>{book['title']}</b>\n"
            
            if book['author']:
                book_msg += f"👤 <i>{book['author']}</i>\n"
            
            if book['publisher']:
                book_msg += f"🏢 {book['publisher']}"
                if book['year']:
                    book_msg += f" ({book['year']})"
                book_msg += "\n"
            
            if book['extension']:
                book_msg += f"📄 {book['extension'].upper()}"
                if book['filesize']:
                    book_msg += f" • {book['filesize']}"
                book_msg += "\n"
            
            # Availability status
            if book['available']:
                book_msg += "✅ <b>Available for download</b>"
            else:
                book_msg += "❌ <b>Not yet available</b>"
            
            # Create inline keyboard
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("➕ Add to List", callback_data=f"add_{book['id']}"),
                InlineKeyboardButton("📖 Details", callback_data=f"details_{book['id']}")
            )
            
            self.bot.send_message(message.chat.id, book_msg, reply_markup=keyboard)
        
        # Pagination
        if len(results) == 10:  # Might have more results
            nav_keyboard = InlineKeyboardMarkup()
            buttons = []
            
            if page > 1:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"search_page_{query}_{page-1}"))
            
            buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"search_page_{query}_{page+1}"))
            
            if buttons:
                nav_keyboard.row(*buttons)
                self.bot.send_message(message.chat.id, "📄 Navigation:", reply_markup=nav_keyboard)
    
    def cmd_view_list(self, message: Message):
        """Handle /list command"""
        user_id = message.from_user.id
        session = self.get_user_session(user_id)
        
        # Get user's current list
        request_items = self.admin_db.get_user_request_list(session['session_id'])
        
        if not request_items:
            self.bot.send_message(message.chat.id, """
📚 <b>Your Book List is Empty</b>

You haven't added any books to your list yet.

<b>How to add books:</b>
1. Search for books using /search or type book name
2. Click ➕ button next to search results
3. Books will be added to this list

Start searching for books! 🔍
""")
            return
        
        # Send list header
        list_msg = f"📚 <b>Your Book Request List</b>\n"
        list_msg += f"📋 Session ID: <code>{session['session_id']}</code>\n"
        list_msg += f"📖 Total Books: <b>{len(request_items)}</b>\n\n"
        
        self.bot.send_message(message.chat.id, list_msg)
        
        # Send each book
        for i, item in enumerate(request_items, 1):
            book_msg = f"{i}. <b>{item['book_title']}</b>\n"
            
            if item['book_author']:
                book_msg += f"👤 <i>{item['book_author']}</i>\n"
            
            if item['book_publisher']:
                book_msg += f"🏢 {item['book_publisher']}\n"
            
            if item['extension']:
                book_msg += f"📄 {item['extension'].upper()}"
                if item['filesize']:
                    book_msg += f" • {item['filesize']}"
                book_msg += "\n"
            
            # Status
            if item.get('available'):
                book_msg += "✅ <b>Available</b>"
            else:
                book_msg += "❌ <b>Not available</b>"
            
            # Action buttons
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("❌ Remove", callback_data=f"remove_{item['book_id']}"))
            
            self.bot.send_message(message.chat.id, book_msg, reply_markup=keyboard)
        
        # List actions
        if request_items:
            action_keyboard = InlineKeyboardMarkup()
            action_keyboard.add(
                InlineKeyboardButton("📤 Submit Request", callback_data="submit_request"),
                InlineKeyboardButton("🗑️ Clear All", callback_data="clear_all")
            )
            
            self.bot.send_message(message.chat.id, "🔧 <b>List Actions:</b>", reply_markup=action_keyboard)
    
    def cmd_submit_request(self, message: Message):
        """Handle /submit command"""
        user_id = message.from_user.id
        session = self.get_user_session(user_id)
        
        # Get user's current list
        request_items = self.admin_db.get_user_request_list(session['session_id'])
        
        if not request_items:
            self.bot.send_message(message.chat.id, "❌ Your list is empty. Add some books first!")
            return
        
        # Confirm submission
        confirm_msg = f"""
📤 <b>Submit Book Request</b>

You are about to submit a request for <b>{len(request_items)} books</b>.

📋 <b>Session ID:</b> <code>{session['session_id']}</code>
👤 <b>User ID:</b> <code>{user_id}</code>
⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<b>What happens next:</b>
1. Admin will receive WhatsApp notification
2. Admin will review your request
3. You'll be contacted via Telegram/WhatsApp
4. Download links will be provided

<b>Admin Contact:</b> +62 857-9952-0350

Proceed with submission?
"""
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("✅ Yes, Submit", callback_data="confirm_submit"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_submit")
        )
        
        self.bot.send_message(message.chat.id, confirm_msg, reply_markup=keyboard)
    
    def cmd_clear_list(self, message: Message):
        """Handle /clear command"""
        user_id = message.from_user.id
        session = self.get_user_session(user_id)
        
        # Get current list count
        request_items = self.admin_db.get_user_request_list(session['session_id'])
        
        if not request_items:
            self.bot.send_message(message.chat.id, "📚 Your list is already empty!")
            return
        
        confirm_msg = f"""
🗑️ <b>Clear Book List</b>

Are you sure you want to clear all <b>{len(request_items)} books</b> from your list?

⚠️ <b>Warning:</b> This action cannot be undone!
"""
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("✅ Yes, Clear All", callback_data="confirm_clear"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_clear")
        )
        
        self.bot.send_message(message.chat.id, confirm_msg, reply_markup=keyboard)
    
    def cmd_stats(self, message: Message):
        """Handle /stats command"""
        try:
            stats = self.admin_db.get_database_stats()
            user_id = message.from_user.id
            session = self.get_user_session(user_id)
            
            # Get user's current list
            request_items = self.admin_db.get_user_request_list(session['session_id'])
            
            stats_msg = f"""
📊 <b>Book Database Statistics</b>

📚 <b>Library:</b>
• Total Books: <b>{stats.get('total_books', 0):,}</b>
• Available for Download: <b>{stats.get('available_books', 0):,}</b>
• Availability Rate: <b>{(stats.get('available_books', 0) / max(stats.get('total_books', 1), 1) * 100):.1f}%</b>

📋 <b>Requests:</b>
• Total Requests: <b>{stats.get('total_requests', 0):,}</b>
• Requests Today: <b>{stats.get('requests_last_24h', 0)}</b>
• Total Requested Books: <b>{stats.get('total_request_items', 0):,}</b>

👤 <b>Your Session:</b>
• Session ID: <code>{session['session_id']}</code>
• Books in List: <b>{len(request_items)}</b>
• Last Activity: {session['last_activity'].strftime('%H:%M:%S')}

📱 <b>Admin Contact:</b> +62 857-9952-0350

📈 Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            self.bot.send_message(message.chat.id, stats_msg)
            
        except Exception as e:
            logger.error(f"Stats error: {e}")
            self.bot.send_message(message.chat.id, "❌ Error getting statistics.")
    
    def handle_text_message(self, message: Message):
        """Handle regular text messages (search queries)"""
        text = message.text.strip()
        
        # Handle main menu buttons
        if text == "🔍 Search Books":
            self.bot.send_message(message.chat.id, "🔍 Type your search query (book title, author, or publisher):")
            return
        elif text == "📚 My List":
            self.cmd_view_list(message)
            return
        elif text == "📤 Submit Request":
            self.cmd_submit_request(message)
            return
        elif text == "🗑️ Clear List":
            self.cmd_clear_list(message)
            return
        elif text == "ℹ️ Help":
            self.cmd_help(message)
            return
        
        # Treat as search query
        if len(text) >= 2:
            self.perform_search(message, text)
        else:
            self.bot.send_message(message.chat.id, "❌ Search query too short. Please use at least 2 characters.")
    
    def handle_callback_query(self, call):
        """Handle inline keyboard callbacks"""
        try:
            data = call.data
            user_id = call.from_user.id
            session = self.get_user_session(user_id)
            
            if data.startswith('add_'):
                book_id = data[4:]
                self.add_book_to_list(call, book_id, session)
            
            elif data.startswith('remove_'):
                book_id = data[7:]
                self.remove_book_from_list(call, book_id, session)
            
            elif data.startswith('details_'):
                book_id = data[8:]
                self.show_book_details(call, book_id)
            
            elif data.startswith('search_page_'):
                parts = data.split('_', 3)
                query = parts[2]
                page = int(parts[3])
                self.perform_search(call.message, query, page)
            
            elif data == 'submit_request':
                self.cmd_submit_request(call.message)
            
            elif data == 'confirm_submit':
                self.confirm_submit_request(call, session)
            
            elif data == 'cancel_submit':
                self.bot.edit_message_text("❌ Submission cancelled.", call.message.chat.id, call.message.message_id)
            
            elif data == 'clear_all':
                self.cmd_clear_list(call.message)
            
            elif data == 'confirm_clear':
                self.confirm_clear_list(call, session)
            
            elif data == 'cancel_clear':
                self.bot.edit_message_text("❌ Clear cancelled.", call.message.chat.id, call.message.message_id)
            
            self.bot.answer_callback_query(call.id)
            
        except Exception as e:
            logger.error(f"Callback error: {e}")
            self.bot.answer_callback_query(call.id, "❌ Error processing request")
    
    def add_book_to_list(self, call, book_id: str, session: Dict):
        """Add book to user's request list"""
        try:
            success = self.admin_db.add_book_to_request(session['session_id'], book_id)
            
            if success:
                book = self.admin_db.get_book_details(book_id)
                msg = f"✅ <b>Added to your list:</b>\n📚 {book['title']}"
                
                # Show quick actions
                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton("📚 View List", callback_data="view_list"),
                    InlineKeyboardButton("🔍 Continue Search", callback_data="continue_search")
                )
                
                self.bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
                
                logger.info(f"User {call.from_user.id} added book {book_id} to list")
            else:
                self.bot.answer_callback_query(call.id, "❌ Failed to add book")
                
        except Exception as e:
            logger.error(f"Add book error: {e}")
            self.bot.answer_callback_query(call.id, "❌ Error adding book")
    
    def remove_book_from_list(self, call, book_id: str, session: Dict):
        """Remove book from user's request list"""
        try:
            success = self.admin_db.remove_book_from_request(session['session_id'], book_id)
            
            if success:
                self.bot.edit_message_text("✅ Book removed from your list", call.message.chat.id, call.message.message_id)
                logger.info(f"User {call.from_user.id} removed book {book_id} from list")
            else:
                self.bot.answer_callback_query(call.id, "❌ Failed to remove book")
                
        except Exception as e:
            logger.error(f"Remove book error: {e}")
            self.bot.answer_callback_query(call.id, "❌ Error removing book")
    
    def show_book_details(self, call, book_id: str):
        """Show detailed book information"""
        try:
            book = self.admin_db.get_book_details(book_id)
            if not book:
                self.bot.answer_callback_query(call.id, "❌ Book not found")
                return
            
            details_msg = f"📚 <b>{book['title']}</b>\n\n"
            
            if book['author']:
                details_msg += f"👤 <b>Author:</b> {book['author']}\n"
            
            if book['publisher']:
                details_msg += f"🏢 <b>Publisher:</b> {book['publisher']}\n"
            
            if book['year']:
                details_msg += f"📅 <b>Year:</b> {book['year']}\n"
            
            if book['language']:
                details_msg += f"🌐 <b>Language:</b> {book['language']}\n"
            
            if book['extension']:
                details_msg += f"📄 <b>Format:</b> {book['extension'].upper()}\n"
            
            if book['filesize']:
                details_msg += f"💾 <b>Size:</b> {book['filesize']}\n"
            
            # Availability
            details_msg += f"\n📊 <b>Status:</b> "
            if book['available']:
                details_msg += "✅ Available for download"
            else:
                details_msg += "❌ Not yet available"
            
            details_msg += f"\n🆔 <b>Book ID:</b> <code>{book['id']}</code>"
            
            # Action buttons
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("➕ Add to List", callback_data=f"add_{book['id']}"))
            
            self.bot.edit_message_text(details_msg, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            
        except Exception as e:
            logger.error(f"Show details error: {e}")
            self.bot.answer_callback_query(call.id, "❌ Error showing details")
    
    def confirm_submit_request(self, call, session: Dict):
        """Confirm and submit user request"""
        try:
            success = self.admin_db.submit_user_request(session['session_id'])
            
            if success:
                msg = f"""
✅ <b>Request Submitted Successfully!</b>

📋 <b>Session ID:</b> <code>{session['session_id']}</code>
📱 <b>Admin will be notified via WhatsApp</b>

<b>What's Next:</b>
1. Admin will review your request
2. You'll be contacted for confirmation
3. Download links will be provided

<b>Admin Contact:</b> +62 857-9952-0350

Thank you for using our service! 🙏
"""
                
                self.bot.edit_message_text(msg, call.message.chat.id, call.message.message_id)
                
                # Create new session for future requests
                new_session_id = self.admin_db.create_user_request(str(call.from_user.id))
                session['session_id'] = new_session_id
                
                logger.info(f"User {call.from_user.id} submitted request {session['session_id']}")
            else:
                self.bot.edit_message_text("❌ Failed to submit request. Please try again.", 
                                         call.message.chat.id, call.message.message_id)
                
        except Exception as e:
            logger.error(f"Submit request error: {e}")
            self.bot.edit_message_text("❌ Error submitting request.", call.message.chat.id, call.message.message_id)
    
    def confirm_clear_list(self, call, session: Dict):
        """Confirm and clear user's list"""
        try:
            # Create new session (this effectively clears the list)
            new_session_id = self.admin_db.create_user_request(str(call.from_user.id))
            session['session_id'] = new_session_id
            
            self.bot.edit_message_text("✅ Your book list has been cleared!", call.message.chat.id, call.message.message_id)
            
            logger.info(f"User {call.from_user.id} cleared their list")
            
        except Exception as e:
            logger.error(f"Clear list error: {e}")
            self.bot.edit_message_text("❌ Error clearing list.", call.message.chat.id, call.message.message_id)
    
    def get_or_create_session(self, user_id: str) -> str:
        """Get or create user session"""
        with self.session_lock:
            if user_id in self.user_sessions:
                return self.user_sessions[user_id]['session_id']
            else:
                # Create new session
                session_id = self.admin_db.create_user_request(user_id)
                self.user_sessions[user_id] = {
                    'session_id': session_id,
                    'created_at': time.time()
                }
                return session_id
    
    def run(self):
        """Start the bot"""
        if not TELEGRAM_AVAILABLE:
            logger.error("❌ Telegram libraries not available. Cannot start bot.")
            return
        
        logger.info("🚀 Starting User Book Request Bot...")
        
        try:
            self.bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")
        finally:
            logger.info("👋 Bot stopped")

def main():
    """Main function"""
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Create sample CSV data if not exists
    create_sample_data()
    
    # Initialize and run bot
    bot = UserBookBot()
    bot.run()

def create_sample_data():
    """Create sample book data for testing"""
    csv_path = 'data/books_database.csv'
    
    # Create data directory
    os.makedirs('data', exist_ok=True)
    
    if not os.path.exists(csv_path):
        sample_books = [
            {
                'id': 'book001',
                'title': 'Python Programming for Beginners',
                'author': 'John Smith',
                'publisher': 'Tech Books',
                'year': '2023',
                'language': 'English',
                'extension': 'pdf',
                'filesize': '5.2 MB',
                'book_url': 'https://example.com/book001',
                'cover_image_url': '',
                'source_type': 'library',
                'cover_url_final': '',
                'files_url_drive': 'https://drive.google.com/file/d/abc123',
                'download_status': 'done'
            },
            {
                'id': 'book002', 
                'title': 'Advanced Database Design',
                'author': 'Jane Doe',
                'publisher': 'Data Science Press',
                'year': '2023',
                'language': 'English',
                'extension': 'pdf',
                'filesize': '8.7 MB',
                'book_url': 'https://example.com/book002',
                'cover_image_url': '',
                'source_type': 'library',
                'cover_url_final': '',
                'files_url_drive': '',
                'download_status': 'pending'
            },
            {
                'id': 'book003',
                'title': 'Machine Learning Fundamentals', 
                'author': 'Dr. AI Expert',
                'publisher': 'ML Publications',
                'year': '2024',
                'language': 'English',
                'extension': 'pdf',
                'filesize': '12.3 MB',
                'book_url': 'https://example.com/book003',
                'cover_image_url': '',
                'source_type': 'library',
                'cover_url_final': '',
                'files_url_drive': 'https://drive.google.com/file/d/xyz789',
                'download_status': 'done'
            }
        ]
        
        # Write sample data to CSV
        import csv
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            if sample_books:
                fieldnames = sample_books[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(sample_books)
        logger.info(f"✅ Created sample data: {csv_path}")

if __name__ == "__main__":
    main()