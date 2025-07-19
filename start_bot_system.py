#!/usr/bin/env python3
"""
Bot System Startup Script
Launches all components: Database, User Bot, Admin Panel, and Admin Bot
"""

import os
import sys
import threading
import time
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def start_user_bot():
    """Start the user book bot"""
    try:
        logger.info("Starting User Book Bot...")
        from user_book_bot import main as user_bot_main
        user_bot_main()
    except Exception as e:
        logger.error(f"Failed to start User Bot: {e}")

def start_admin_panel():
    """Start the admin panel web interface"""
    try:
        logger.info("Starting Admin Panel Web Interface...")
        from admin_panel import main as admin_panel_main
        admin_panel_main()
    except Exception as e:
        logger.error(f"Failed to start Admin Panel: {e}")

def start_admin_bot():
    """Start the admin Telegram bot"""
    try:
        logger.info("Starting Admin Telegram Bot...")
        from admin_panel import start_admin_bot
        start_admin_bot()
    except Exception as e:
        logger.error(f"Failed to start Admin Bot: {e}")

def initialize_database():
    """Initialize the database with sample data"""
    try:
        logger.info("Initializing database...")
        from admin_database import get_admin_db
        
        # Create database instance
        admin_db = get_admin_db()
        
        # Check if we need to create sample data
        books = admin_db.get_all_books()
        if len(books) == 0:
            logger.info("No books found, creating sample data...")
            from test_all_bot_functions import create_sample_book_data
            create_sample_book_data()
            
            # Reload database
            admin_db.load_books_from_csv()
            logger.info("Sample data created and loaded")
        else:
            logger.info(f"Database already contains {len(books)} books")
            
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def check_environment():
    """Check if environment is properly configured"""
    logger.info("Checking environment configuration...")
    
    # Check required directories
    required_dirs = ['logs', 'data']
    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            logger.info(f"Created directory: {dir_name}")
    
    # Check environment variables
    env_vars = {
        'USER_BOT_TOKEN': '7825591642:AAGh4zVMhLdOSnW-FV-FPaq5f5OVxiia3xw',
        'ADMIN_BOT_TOKEN': '7825591642:AAGh4zVMhLdOSnW-FV-FPaq5f5OVxiia3xw',
        'ADMIN_CHAT_ID': '085799520350'
    }
    
    for var, default in env_vars.items():
        if not os.getenv(var):
            os.environ[var] = default
            logger.info(f"Set environment variable {var} to default")
    
    logger.info("Environment check completed")

def display_startup_info():
    """Display startup information"""
    print("\n" + "="*60)
    print("📚 BOOK REQUEST BOT SYSTEM")
    print("="*60)
    print("🚀 Starting all components...")
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📋 Components:")
    print("  ✓ Admin Database")
    print("  ✓ User Book Bot (Telegram)")
    print("  ✓ Admin Panel (Web + Telegram)")
    print("  ✓ WhatsApp Notifications")
    print("\n📱 Features:")
    print("  🔍 Book Search")
    print("  📝 Add to List/Cart")
    print("  📤 Submit Requests")
    print("  🤖 Admin Automation")
    print("  📊 CSV Database Export")
    print("\n📞 Admin Contact: 085799520350")
    print("="*60)

def display_system_status():
    """Display system status"""
    try:
        from admin_database import get_admin_db
        admin_db = get_admin_db()
        
        # Get stats
        books_count = len(admin_db.get_all_books())
        requests_count = len(admin_db.get_all_requests())
        pending_count = len(admin_db.get_pending_requests())
        
        print("\n📊 SYSTEM STATUS")
        print("-" * 30)
        print(f"📚 Books in database: {books_count}")
        print(f"📋 Total requests: {requests_count}")
        print(f"⏳ Pending requests: {pending_count}")
        print("-" * 30)
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")

def main():
    """Main startup function"""
    display_startup_info()
    
    # Check environment
    check_environment()
    
    # Initialize database
    if not initialize_database():
        logger.error("Database initialization failed, exiting...")
        sys.exit(1)
    
    # Display system status
    display_system_status()
    
    print("\n🔧 Starting services...")
    
    # Start components in separate threads
    components = []
    
    try:
        # Start User Bot
        user_bot_thread = threading.Thread(target=start_user_bot, daemon=True)
        user_bot_thread.start()
        components.append(("User Bot", user_bot_thread))
        time.sleep(2)  # Give it time to start
        
        # Start Admin Panel Web Interface
        admin_panel_thread = threading.Thread(target=start_admin_panel, daemon=True)
        admin_panel_thread.start()
        components.append(("Admin Panel", admin_panel_thread))
        time.sleep(2)
        
        # Start Admin Bot
        admin_bot_thread = threading.Thread(target=start_admin_bot, daemon=True)
        admin_bot_thread.start()
        components.append(("Admin Bot", admin_bot_thread))
        time.sleep(2)
        
        print("\n✅ All components started successfully!")
        print("\n📡 Service URLs:")
        print("  🌐 Admin Panel: http://localhost:5000")
        print("  🤖 User Bot: Available on Telegram")
        print("  👨‍💼 Admin Bot: Available on Telegram")
        
        print("\n💡 How to use:")
        print("  1. Users search and add books via Telegram bot")
        print("  2. Requests are sent to admin via WhatsApp")
        print("  3. Admin can manage requests via web panel or Telegram")
        print("  4. CSV database exports available in data/ folder")
        
        print("\n🔄 System is running... Press Ctrl+C to stop")
        
        # Keep main thread alive
        while True:
            time.sleep(10)
            
            # Check if any thread died
            for name, thread in components:
                if not thread.is_alive():
                    logger.warning(f"{name} thread stopped unexpectedly")
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down bot system...")
        logger.info("Received shutdown signal")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        print(f"\n❌ Startup failed: {e}")
        
    finally:
        print("👋 Bot system stopped")

if __name__ == "__main__":
    main()