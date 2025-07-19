#!/usr/bin/env python3
"""
Admin Database System for Book Request Management
Handles user book requests and admin notifications via WhatsApp
"""

import os
import json
import csv
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import threading
import hashlib
# import pandas as pd  # Removed to use only built-in modules

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/admin_database.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AdminDatabase:
    """Enhanced admin database for book request management"""
    
    def __init__(self, db_path='admin_database.db', csv_path='data/books_database.csv'):
        self.db_path = db_path
        self.csv_path = csv_path
        self.admin_phone = "085799520350"
        self.lock = threading.Lock()
        self.init_database()
        self.load_books_from_csv()
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Books table (cache from CSV)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS books (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        author TEXT,
                        publisher TEXT,
                        year TEXT,
                        language TEXT,
                        extension TEXT,
                        filesize TEXT,
                        book_url TEXT,
                        cover_image_url TEXT,
                        source_type TEXT,
                        cover_url_final TEXT,
                        files_url_drive TEXT,
                        download_status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # User requests table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        user_name TEXT,
                        user_phone TEXT,
                        user_email TEXT,
                        session_id TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        admin_notes TEXT
                    )
                ''')
                
                # Request items table (books in user's list)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS request_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id INTEGER NOT NULL,
                        book_id TEXT NOT NULL,
                        book_title TEXT NOT NULL,
                        book_author TEXT,
                        book_publisher TEXT,
                        priority INTEGER DEFAULT 1,
                        status TEXT DEFAULT 'pending',
                        download_link TEXT,
                        admin_notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (request_id) REFERENCES user_requests (id),
                        FOREIGN KEY (book_id) REFERENCES books (id)
                    )
                ''')
                
                # Admin actions log
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS admin_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        admin_id TEXT DEFAULT 'system',
                        action_type TEXT NOT NULL,
                        target_type TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        description TEXT,
                        data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books (title)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_author ON books (author)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_publisher ON books (publisher)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_requests_user_id ON user_requests (user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_request_items_request_id ON request_items (request_id)')
                
                conn.commit()
                logger.info("✅ Admin database initialized successfully")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise
    
    def load_books_from_csv(self):
        """Load books from CSV into database"""
        if not os.path.exists(self.csv_path):
            logger.warning(f"CSV file not found: {self.csv_path}")
            return
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Clear existing books
                    cursor.execute('DELETE FROM books')
                    
                    # Insert books from CSV
                    books_inserted = 0
                    for row in reader:
                        try:
                            book_data = {
                                'id': str(row.get('id', '')).strip(),
                                'title': str(row.get('title', '')).strip(),
                                'author': str(row.get('author', '')).strip(),
                                'publisher': str(row.get('publisher', '')).strip(),
                                'year': str(row.get('year', '')).strip(),
                                'language': str(row.get('language', '')).strip(),
                                'extension': str(row.get('extension', '')).strip(),
                                'filesize': str(row.get('filesize', '')).strip(),
                                'book_url': str(row.get('book_url', '')).strip(),
                                'cover_image_url': str(row.get('cover_image_url', '')).strip(),
                                'source_type': str(row.get('source_type', '')).strip(),
                                'cover_url_final': str(row.get('cover_url_final', '')).strip(),
                                'files_url_drive': str(row.get('files_url_drive', '')).strip(),
                                'download_status': str(row.get('download_status', 'pending')).strip()
                            }
                            
                            if not book_data['id']:
                                continue
                            
                            cursor.execute('''
                                INSERT OR REPLACE INTO books 
                                (id, title, author, publisher, year, language, extension, filesize,
                                 book_url, cover_image_url, source_type, cover_url_final, 
                                 files_url_drive, download_status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', tuple(book_data.values()))
                            
                            books_inserted += 1
                        
                        except Exception as e:
                            logger.error(f"Error inserting book {row.get('id')}: {e}")
                            continue
                
                conn.commit()
                logger.info(f"✅ Loaded {books_inserted} books from CSV into database")
                
        except Exception as e:
            logger.error(f"❌ Failed to load books from CSV: {e}")
    
    def search_books(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Search books in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                search_query = f"%{query.lower()}%"
                cursor.execute('''
                    SELECT id, title, author, publisher, year, extension, filesize,
                           cover_image_url, files_url_drive, download_status
                    FROM books
                    WHERE LOWER(title) LIKE ? 
                       OR LOWER(author) LIKE ? 
                       OR LOWER(publisher) LIKE ?
                    ORDER BY 
                        CASE WHEN LOWER(title) LIKE ? THEN 1 ELSE 2 END,
                        title
                    LIMIT ? OFFSET ?
                ''', (search_query, search_query, search_query, search_query, limit, offset))
                
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    book = dict(zip(columns, row))
                    book['available'] = bool(book.get('files_url_drive'))
                    results.append(book)
                
                logger.info(f"📚 Search '{query}' returned {len(results)} results")
                return results
                
        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            return []
    
    def get_book_details(self, book_id: str) -> Optional[Dict]:
        """Get detailed book information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM books WHERE id = ?', (book_id,))
                
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    book = dict(zip(columns, row))
                    book['available'] = bool(book.get('files_url_drive'))
                    return book
                
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting book details: {e}")
            return None
    
    def create_user_request(self, user_id: str, user_name: str = None, 
                          user_phone: str = None, user_email: str = None) -> str:
        """Create new user request session"""
        try:
            session_id = hashlib.md5(f"{user_id}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO user_requests (user_id, user_name, user_phone, user_email, session_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, user_name, user_phone, user_email, session_id))
                
                request_id = cursor.lastrowid
                conn.commit()
                
                # Log admin action
                self.log_admin_action('system', 'create', 'user_request', str(request_id), 
                                    f"New request session created for user {user_id}")
                
                logger.info(f"✅ Created request session {session_id} for user {user_id}")
                return session_id
                
        except Exception as e:
            logger.error(f"❌ Error creating user request: {e}")
            raise
    
    def add_book_to_request(self, session_id: str, book_id: str, priority: int = 1) -> bool:
        """Add book to user's request list"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get request ID
                cursor.execute('SELECT id FROM user_requests WHERE session_id = ?', (session_id,))
                request_row = cursor.fetchone()
                if not request_row:
                    logger.error(f"Request session {session_id} not found")
                    return False
                
                request_id = request_row[0]
                
                # Get book details
                book = self.get_book_details(book_id)
                if not book:
                    logger.error(f"Book {book_id} not found")
                    return False
                
                # Check if book already in request
                cursor.execute('''
                    SELECT id FROM request_items 
                    WHERE request_id = ? AND book_id = ?
                ''', (request_id, book_id))
                
                if cursor.fetchone():
                    logger.info(f"Book {book_id} already in request {session_id}")
                    return True
                
                # Add book to request
                cursor.execute('''
                    INSERT INTO request_items (request_id, book_id, book_title, book_author, 
                                             book_publisher, priority)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (request_id, book_id, book['title'], book['author'], 
                      book['publisher'], priority))
                
                conn.commit()
                
                # Log admin action
                self.log_admin_action('system', 'add', 'request_item', book_id,
                                    f"Book added to request {session_id}")
                
                logger.info(f"✅ Added book {book_id} to request {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error adding book to request: {e}")
            return False
    
    def remove_book_from_request(self, session_id: str, book_id: str) -> bool:
        """Remove book from user's request list"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get request ID
                cursor.execute('SELECT id FROM user_requests WHERE session_id = ?', (session_id,))
                request_row = cursor.fetchone()
                if not request_row:
                    return False
                
                request_id = request_row[0]
                
                # Remove book from request
                cursor.execute('''
                    DELETE FROM request_items 
                    WHERE request_id = ? AND book_id = ?
                ''', (request_id, book_id))
                
                conn.commit()
                
                # Log admin action
                self.log_admin_action('system', 'remove', 'request_item', book_id,
                                    f"Book removed from request {session_id}")
                
                logger.info(f"✅ Removed book {book_id} from request {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error removing book from request: {e}")
            return False
    
    def get_user_request_list(self, session_id: str) -> List[Dict]:
        """Get user's current request list"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT ri.book_id, ri.book_title, ri.book_author, ri.book_publisher,
                           ri.priority, ri.status, ri.download_link, ri.created_at,
                           b.extension, b.filesize, b.available
                    FROM request_items ri
                    JOIN user_requests ur ON ri.request_id = ur.id
                    LEFT JOIN (
                        SELECT id, extension, filesize, 
                               CASE WHEN files_url_drive IS NOT NULL AND files_url_drive != '' 
                                    THEN 1 ELSE 0 END as available
                        FROM books
                    ) b ON ri.book_id = b.id
                    WHERE ur.session_id = ?
                    ORDER BY ri.priority, ri.created_at
                ''', (session_id,))
                
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    item = dict(zip(columns, row))
                    results.append(item)
                
                logger.info(f"📋 Retrieved {len(results)} items for request {session_id}")
                return results
                
        except Exception as e:
            logger.error(f"❌ Error getting request list: {e}")
            return []
    
    def submit_user_request(self, session_id: str) -> bool:
        """Submit user request and notify admin via WhatsApp"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get request details
                cursor.execute('''
                    SELECT ur.id, ur.user_id, ur.user_name, ur.user_phone, ur.user_email,
                           COUNT(ri.id) as item_count
                    FROM user_requests ur
                    LEFT JOIN request_items ri ON ur.id = ri.request_id
                    WHERE ur.session_id = ?
                    GROUP BY ur.id
                ''', (session_id,))
                
                request_row = cursor.fetchone()
                if not request_row:
                    logger.error(f"Request {session_id} not found")
                    return False
                
                request_id, user_id, user_name, user_phone, user_email, item_count = request_row
                
                if item_count == 0:
                    logger.error(f"Request {session_id} has no items")
                    return False
                
                # Update request status
                cursor.execute('''
                    UPDATE user_requests 
                    SET status = 'submitted', updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                ''', (session_id,))
                
                # Get request items
                request_items = self.get_user_request_list(session_id)
                
                conn.commit()
                
                # Send WhatsApp notification to admin
                self.send_admin_notification(session_id, user_id, user_name, 
                                           user_phone, user_email, request_items)
                
                # Log admin action
                self.log_admin_action('system', 'submit', 'user_request', str(request_id),
                                    f"Request submitted with {item_count} items")
                
                logger.info(f"✅ Submitted request {session_id} with {item_count} items")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error submitting request: {e}")
            return False
    
    def send_admin_notification(self, session_id: str, user_id: str, user_name: str,
                              user_phone: str, user_email: str, request_items: List[Dict]):
        """Send WhatsApp notification to admin"""
        try:
            # Format message for admin
            message_lines = [
                "🆕 *NEW BOOK REQUEST*",
                "=" * 30,
                f"📋 Session ID: `{session_id}`",
                f"👤 User ID: `{user_id}`"
            ]
            
            if user_name:
                message_lines.append(f"📝 Name: {user_name}")
            if user_phone:
                message_lines.append(f"📞 Phone: {user_phone}")
            if user_email:
                message_lines.append(f"📧 Email: {user_email}")
            
            message_lines.extend([
                f"📚 Total Books: {len(request_items)}",
                f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "📖 *REQUESTED BOOKS:*"
            ])
            
            for i, item in enumerate(request_items[:10], 1):  # Limit to 10 books
                book_info = f"{i}. *{item['book_title']}*"
                if item['book_author']:
                    book_info += f"\n   👤 {item['book_author']}"
                if item['book_publisher']:
                    book_info += f"\n   🏢 {item['book_publisher']}"
                if item['extension']:
                    book_info += f"\n   📄 {item['extension'].upper()}"
                
                availability = "✅ Available" if item.get('available') else "❌ Not Available"
                book_info += f"\n   {availability}"
                
                message_lines.append(book_info)
            
            if len(request_items) > 10:
                message_lines.append(f"\n... and {len(request_items) - 10} more books")
            
            message_lines.extend([
                "",
                "🔧 *ADMIN ACTIONS:*",
                f"• Reply with: `/approve {session_id}` to approve",
                f"• Reply with: `/reject {session_id}` to reject",
                f"• Reply with: `/details {session_id}` for full details"
            ])
            
            message = "\n".join(message_lines)
            
            # Send via WhatsApp API (you'll need to implement this)
            success = self.send_whatsapp_message(self.admin_phone, message)
            
            if success:
                logger.info(f"✅ Admin notification sent for request {session_id}")
            else:
                logger.error(f"❌ Failed to send admin notification for request {session_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"❌ Error sending admin notification: {e}")
            return False
    
    def send_whatsapp_message(self, phone: str, message: str) -> bool:
        """Send WhatsApp message using API (implement your preferred service)"""
        try:
            # Option 1: Using WhatsApp Business API
            # Option 2: Using third-party service like Fonnte, Wablas, etc.
            # Option 3: Using WhatsApp Web automation
            
            # For now, we'll log the message (replace with actual WhatsApp API)
            logger.info(f"📱 WhatsApp message to {phone}:")
            logger.info(f"Message: {message}")
            
            # Example implementation with Fonnte API (uncomment and configure)
            """
            import requests
            
            url = "https://api.fonnte.com/send"
            headers = {
                'Authorization': 'YOUR_FONNTE_TOKEN_HERE'
            }
            data = {
                'target': phone,
                'message': message,
                'countryCode': '62'  # Indonesia
            }
            
            response = requests.post(url, headers=headers, data=data)
            return response.status_code == 200
            """
            
            # For demo purposes, return True
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending WhatsApp message: {e}")
            return False
    
    def log_admin_action(self, admin_id: str, action_type: str, target_type: str, 
                        target_id: str, description: str, data: str = None):
        """Log admin actions for auditing"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO admin_actions (admin_id, action_type, target_type, 
                                             target_id, description, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (admin_id, action_type, target_type, target_id, description, data))
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Error logging admin action: {e}")
    
    def get_pending_requests(self, limit: int = 50) -> List[Dict]:
        """Get pending requests for admin review"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT ur.id, ur.user_id, ur.user_name, ur.user_phone, ur.user_email,
                           ur.session_id, ur.status, ur.created_at,
                           COUNT(ri.id) as item_count
                    FROM user_requests ur
                    LEFT JOIN request_items ri ON ur.id = ri.request_id
                    WHERE ur.status IN ('pending', 'submitted')
                    GROUP BY ur.id
                    ORDER BY ur.created_at DESC
                    LIMIT ?
                ''', (limit,))
                
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    request = dict(zip(columns, row))
                    results.append(request)
                
                return results
                
        except Exception as e:
            logger.error(f"❌ Error getting pending requests: {e}")
            return []
    
    def approve_request(self, session_id: str, admin_id: str = 'admin') -> bool:
        """Approve user request"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE user_requests 
                    SET status = 'approved', updated_at = CURRENT_TIMESTAMP,
                        admin_notes = ?
                    WHERE session_id = ?
                ''', (f"Approved by {admin_id}", session_id))
                
                conn.commit()
                
                # Log admin action
                self.log_admin_action(admin_id, 'approve', 'user_request', session_id,
                                    f"Request approved by {admin_id}")
                
                logger.info(f"✅ Request {session_id} approved by {admin_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error approving request: {e}")
            return False
    
    def reject_request(self, session_id: str, admin_id: str = 'admin', reason: str = None) -> bool:
        """Reject user request"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                admin_notes = f"Rejected by {admin_id}"
                if reason:
                    admin_notes += f": {reason}"
                
                cursor.execute('''
                    UPDATE user_requests 
                    SET status = 'rejected', updated_at = CURRENT_TIMESTAMP,
                        admin_notes = ?
                    WHERE session_id = ?
                ''', (admin_notes, session_id))
                
                conn.commit()
                
                # Log admin action
                self.log_admin_action(admin_id, 'reject', 'user_request', session_id,
                                    f"Request rejected by {admin_id}: {reason or 'No reason'}")
                
                logger.info(f"✅ Request {session_id} rejected by {admin_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error rejecting request: {e}")
            return False
    
    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Books statistics
                cursor.execute('SELECT COUNT(*) FROM books')
                stats['total_books'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM books WHERE files_url_drive IS NOT NULL AND files_url_drive != ""')
                stats['available_books'] = cursor.fetchone()[0]
                
                # Requests statistics
                cursor.execute('SELECT COUNT(*) FROM user_requests')
                stats['total_requests'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT status, COUNT(*) FROM user_requests GROUP BY status')
                stats['requests_by_status'] = dict(cursor.fetchall())
                
                # Request items statistics
                cursor.execute('SELECT COUNT(*) FROM request_items')
                stats['total_request_items'] = cursor.fetchone()[0]
                
                # Recent activity
                cursor.execute('''
                    SELECT COUNT(*) FROM user_requests 
                    WHERE created_at >= datetime('now', '-24 hours')
                ''')
                stats['requests_last_24h'] = cursor.fetchone()[0]
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Error getting database stats: {e}")
            return {}

    # Alias methods for compatibility with test scripts
    def create_user_session(self, user_id: str) -> str:
        """Create user session - alias for create_user_request"""
        return self.create_user_request(user_id)
    
    def get_all_books(self) -> List[Dict]:
        """Get all books from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM books')
                rows = cursor.fetchall()
                
                books = []
                for row in rows:
                    book = {
                        'id': row[0],
                        'title': row[1],
                        'author': row[2],
                        'publisher': row[3],
                        'year': row[4],
                        'language': row[5],
                        'extension': row[6],
                        'filesize': row[7],
                        'book_url': row[8],
                        'cover_image_url': row[9],
                        'source_type': row[10],
                        'cover_url_final': row[11],
                        'files_url_drive': row[12],
                        'download_status': row[13]
                    }
                    books.append(book)
                
                return books
        except Exception as e:
            logger.error(f"Error getting all books: {e}")
            return []
    
    def get_all_requests(self) -> List[Dict]:
        """Get all user requests"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM user_requests')
                rows = cursor.fetchall()
                
                requests = []
                for row in rows:
                    request = {
                        'id': row[0],
                        'user_id': row[1],
                        'user_name': row[2],
                        'phone': row[3],
                        'email': row[4],
                        'request_date': row[5],
                        'status': row[6],
                        'admin_notes': row[7],
                        'last_updated': row[8]
                    }
                    requests.append(request)
                
                return requests
        except Exception as e:
            logger.error(f"Error getting all requests: {e}")
            return []
    
    def send_whatsapp_notification(self, message: str) -> bool:
        """Send WhatsApp notification - alias for send_whatsapp_message"""
        return self.send_whatsapp_message(self.admin_phone, message)
    
    def add_book_to_request(self, session_id: str, book_id: str) -> bool:
        """Add book to request - alias for existing method"""
        # Call the original method with same name but different signature
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if book exists
                cursor.execute('SELECT id FROM books WHERE id = ?', (book_id,))
                if not cursor.fetchone():
                    logger.error(f"Book {book_id} not found")
                    return False
                
                # Check if session exists
                cursor.execute('SELECT id FROM user_requests WHERE id = ?', (session_id,))
                if not cursor.fetchone():
                    logger.error(f"Session {session_id} not found")
                    return False
                
                # Check if book already in request
                cursor.execute('SELECT id FROM request_items WHERE session_id = ? AND book_id = ?', 
                             (session_id, book_id))
                if cursor.fetchone():
                    logger.info(f"Book {book_id} already in request {session_id}")
                    return True
                
                # Add book to request
                cursor.execute('''
                    INSERT INTO request_items (session_id, book_id, priority, added_date)
                    VALUES (?, ?, ?, ?)
                ''', (session_id, book_id, 1, datetime.now().isoformat()))
                
                conn.commit()
                logger.info(f"✅ Added book {book_id} to request {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error adding book to request: {e}")
            return False
    
    def get_request_summary(self, session_id: str) -> List[Dict]:
        """Get request summary - alias for get_user_request_list"""
        return self.get_user_request_list(session_id)
    
    def submit_request(self, session_id: str) -> str:
        """Submit request and return request ID"""
        success = self.submit_user_request(session_id)
        if success:
            return session_id  # Return session_id as request_id
        return None
    
    def clear_request(self, session_id: str) -> bool:
        """Clear user request list"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM request_items WHERE session_id = ?', (session_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error clearing request {session_id}: {e}")
            return False
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Get user statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Count total requests
                cursor.execute('SELECT COUNT(*) FROM user_requests WHERE user_id = ?', (user_id,))
                total_requests = cursor.fetchone()[0]
                
                # Count pending requests
                cursor.execute('SELECT COUNT(*) FROM user_requests WHERE user_id = ? AND status = ?', 
                             (user_id, 'pending'))
                pending_requests = cursor.fetchone()[0]
                
                # Count approved requests
                cursor.execute('SELECT COUNT(*) FROM user_requests WHERE user_id = ? AND status = ?', 
                             (user_id, 'approved'))
                approved_requests = cursor.fetchone()[0]
                
                return {
                    'total_requests': total_requests,
                    'pending_requests': pending_requests,
                    'approved_requests': approved_requests,
                    'user_id': user_id
                }
        except Exception as e:
            logger.error(f"Error getting user stats for {user_id}: {e}")
            return {'total_requests': 0, 'pending_requests': 0, 'approved_requests': 0, 'user_id': user_id}
    
    def approve_request(self, request_id: str, message: str = "Request approved") -> bool:
        """Approve request - alias for existing method"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update request status
                cursor.execute('''
                    UPDATE user_requests 
                    SET status = ?, admin_notes = ?, last_updated = ?
                    WHERE id = ? AND status = ?
                ''', ('approved', message, datetime.now().isoformat(), request_id, 'pending'))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"✅ Approved request {request_id}")
                    return True
                else:
                    logger.warning(f"Request {request_id} not found or not pending")
                    return False
                    
        except Exception as e:
            logger.error(f"Error approving request {request_id}: {e}")
            return False
    
    def get_request_details(self, request_id: str) -> List[Dict]:
        """Get request details - alias for get_user_request_list"""
        return self.get_user_request_list(request_id)

# Initialize global admin database instance
admin_db = AdminDatabase()

def get_admin_db() -> AdminDatabase:
    """Get admin database instance"""
    return admin_db