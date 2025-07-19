#!/usr/bin/env python3
"""
Admin Panel for Book Request Management
Provides admin interface for managing user requests and automating responses
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
from admin_database import get_admin_db

# Try to import Flask for web interface
try:
    from flask import Flask, render_template_string, request, jsonify, redirect, url_for
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    logging.warning("Flask not available for web interface")

# Try to import Telegram bot libraries for admin bot
try:
    import telebot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logging.warning("Telegram libraries not available")

# Admin configuration
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN', '7825591642:AAGh4zVMhLdOSnW-FV-FPaq5f5OVxiia3xw')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '085799520350')
ADMIN_PHONE = "085799520350"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/admin_panel.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AdminPanel:
    """Enhanced admin panel for book request management"""
    
    def __init__(self):
        self.admin_db = get_admin_db()
        self.auto_approve_available = True  # Auto-approve books that are available
        self.auto_notifications = True
        
        # Initialize Flask web interface
        if FLASK_AVAILABLE:
            self.app = Flask(__name__)
            self.setup_flask_routes()
            logger.info("✅ Flask web interface initialized")
        
        # Initialize Telegram admin bot
        if TELEGRAM_AVAILABLE:
            self.admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN, parse_mode='HTML')
            self.setup_admin_bot_handlers()
            logger.info("✅ Admin Telegram bot initialized")
    
    def setup_flask_routes(self):
        """Setup Flask web interface routes"""
        if not FLASK_AVAILABLE:
            return
        
        @self.app.route('/')
        def dashboard():
            return self.render_dashboard()
        
        @self.app.route('/api/stats')
        def api_stats():
            return jsonify(self.get_admin_stats())
        
        @self.app.route('/api/requests')
        def api_requests():
            return jsonify(self.get_pending_requests())
        
        @self.app.route('/api/approve/<session_id>', methods=['POST'])
        def api_approve(session_id):
            success = self.approve_request(session_id)
            return jsonify({'success': success})
        
        @self.app.route('/api/reject/<session_id>', methods=['POST'])
        def api_reject(session_id):
            reason = request.json.get('reason', '') if request.json else ''
            success = self.reject_request(session_id, reason)
            return jsonify({'success': success})
        
        @self.app.route('/api/auto-process', methods=['POST'])
        def api_auto_process():
            processed = self.auto_process_requests()
            return jsonify({'processed': processed})
    
    def setup_admin_bot_handlers(self):
        """Setup Telegram admin bot handlers"""
        if not TELEGRAM_AVAILABLE:
            return
        
        @self.admin_bot.message_handler(commands=['start'])
        def admin_start(message):
            self.admin_cmd_start(message)
        
        @self.admin_bot.message_handler(commands=['dashboard', 'stats'])
        def admin_dashboard(message):
            self.admin_cmd_dashboard(message)
        
        @self.admin_bot.message_handler(commands=['requests', 'pending'])
        def admin_requests(message):
            self.admin_cmd_requests(message)
        
        @self.admin_bot.message_handler(commands=['approve'])
        def admin_approve(message):
            self.admin_cmd_approve(message)
        
        @self.admin_bot.message_handler(commands=['reject'])
        def admin_reject(message):
            self.admin_cmd_reject(message)
        
        @self.admin_bot.message_handler(commands=['details'])
        def admin_details(message):
            self.admin_cmd_details(message)
        
        @self.admin_bot.message_handler(commands=['auto'])
        def admin_auto(message):
            self.admin_cmd_auto_process(message)
        
        @self.admin_bot.message_handler(commands=['help'])
        def admin_help(message):
            self.admin_cmd_help(message)
        
        @self.admin_bot.callback_query_handler(func=lambda call: True)
        def admin_callback(call):
            self.handle_admin_callback(call)
    
    def render_dashboard(self) -> str:
        """Render admin dashboard HTML"""
        stats = self.get_admin_stats()
        requests = self.get_pending_requests()
        
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Book Request Admin Panel</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .stat-item { text-align: center; padding: 15px; background: #ecf0f1; border-radius: 8px; }
        .stat-number { font-size: 2em; font-weight: bold; color: #3498db; }
        .stat-label { color: #7f8c8d; margin-top: 5px; }
        .request-item { border-left: 4px solid #3498db; padding: 15px; margin: 10px 0; background: #f8f9fa; }
        .btn { padding: 8px 16px; margin: 5px; border: none; border-radius: 4px; cursor: pointer; }
        .btn-success { background: #27ae60; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-info { background: #3498db; color: white; }
        .btn:hover { opacity: 0.8; }
        .status-pending { color: #f39c12; }
        .status-approved { color: #27ae60; }
        .status-rejected { color: #e74c3c; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #34495e; color: white; }
        .auto-controls { background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 20px 0; }
    </style>
    <script>
        function approveRequest(sessionId) {
            fetch(`/api/approve/${sessionId}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Request approved successfully!');
                        location.reload();
                    } else {
                        alert('Failed to approve request');
                    }
                });
        }
        
        function rejectRequest(sessionId) {
            const reason = prompt('Reason for rejection (optional):');
            fetch(`/api/reject/${sessionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason: reason || '' })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Request rejected successfully!');
                    location.reload();
                } else {
                    alert('Failed to reject request');
                }
            });
        }
        
        function autoProcess() {
            if (confirm('Auto-process all available book requests?')) {
                fetch('/api/auto-process', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        alert(`Auto-processed ${data.processed} requests`);
                        location.reload();
                    });
            }
        }
        
        // Auto-refresh every 30 seconds
        setInterval(() => location.reload(), 30000);
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📚 Book Request Admin Panel</h1>
            <p>Manage user book requests • Auto-refresh every 30 seconds</p>
        </div>
        
        <div class="card">
            <h2>📊 Dashboard Statistics</h2>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-number">{{ stats.total_books }}</div>
                    <div class="stat-label">Total Books</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{{ stats.available_books }}</div>
                    <div class="stat-label">Available Books</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{{ stats.total_requests }}</div>
                    <div class="stat-label">Total Requests</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{{ stats.pending_requests }}</div>
                    <div class="stat-label">Pending Requests</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{{ stats.requests_today }}</div>
                    <div class="stat-label">Requests Today</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{{ stats.availability_rate }}%</div>
                    <div class="stat-label">Availability Rate</div>
                </div>
            </div>
        </div>
        
        <div class="auto-controls">
            <h3>🤖 Automation Controls</h3>
            <button class="btn btn-success" onclick="autoProcess()">⚡ Auto-Process Available Books</button>
            <p><small>This will automatically approve requests for books that are available for download.</small></p>
        </div>
        
        <div class="card">
            <h2>📋 Pending Requests ({{ requests|length }})</h2>
            {% if requests %}
            <table>
                <thead>
                    <tr>
                        <th>Session ID</th>
                        <th>User</th>
                        <th>Books</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for req in requests %}
                    <tr>
                        <td><code>{{ req.session_id }}</code></td>
                        <td>
                            ID: {{ req.user_id }}<br>
                            {% if req.user_name %}<strong>{{ req.user_name }}</strong><br>{% endif %}
                            {% if req.user_phone %}📱 {{ req.user_phone }}<br>{% endif %}
                            {% if req.user_email %}📧 {{ req.user_email }}{% endif %}
                        </td>
                        <td><strong>{{ req.item_count }}</strong> books</td>
                        <td>{{ req.created_at }}</td>
                        <td>
                            <button class="btn btn-success" onclick="approveRequest('{{ req.session_id }}')">✅ Approve</button>
                            <button class="btn btn-danger" onclick="rejectRequest('{{ req.session_id }}')">❌ Reject</button>
                            <a href="/details/{{ req.session_id }}" class="btn btn-info">📖 Details</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p>No pending requests at the moment.</p>
            {% endif %}
        </div>
        
        <div class="card">
            <h2>📱 Admin Contact Info</h2>
            <p><strong>WhatsApp:</strong> +62 {{ ADMIN_PHONE }}</p>
            <p><strong>Telegram:</strong> Use admin bot for faster management</p>
            <p><strong>Last Updated:</strong> {{ datetime.now().strftime('%Y-%m-%d %H:%M:%S') }}</p>
        </div>
    </div>
</body>
</html>
        """
        
        from jinja2 import Template
        template = Template(html_template)
        return template.render(
            stats=stats,
            requests=requests,
            ADMIN_PHONE=ADMIN_PHONE,
            datetime=datetime
        )
    
    def get_admin_stats(self) -> Dict:
        """Get admin dashboard statistics"""
        try:
            db_stats = self.admin_db.get_database_stats()
            pending_requests = len(self.admin_db.get_pending_requests())
            
            return {
                'total_books': db_stats.get('total_books', 0),
                'available_books': db_stats.get('available_books', 0),
                'total_requests': db_stats.get('total_requests', 0),
                'pending_requests': pending_requests,
                'requests_today': db_stats.get('requests_last_24h', 0),
                'availability_rate': round((db_stats.get('available_books', 0) / max(db_stats.get('total_books', 1), 1)) * 100, 1)
            }
        except Exception as e:
            logger.error(f"Error getting admin stats: {e}")
            return {}
    
    def get_pending_requests(self) -> List[Dict]:
        """Get pending requests for admin review"""
        return self.admin_db.get_pending_requests()
    
    def approve_request(self, session_id: str, admin_id: str = 'admin') -> bool:
        """Approve a user request"""
        try:
            success = self.admin_db.approve_request(session_id, admin_id)
            
            if success:
                # Send approval notification to user
                self.send_approval_notification(session_id)
                logger.info(f"Request {session_id} approved by {admin_id}")
            
            return success
        except Exception as e:
            logger.error(f"Error approving request {session_id}: {e}")
            return False
    
    def reject_request(self, session_id: str, reason: str = '', admin_id: str = 'admin') -> bool:
        """Reject a user request"""
        try:
            success = self.admin_db.reject_request(session_id, admin_id, reason)
            
            if success:
                # Send rejection notification to user
                self.send_rejection_notification(session_id, reason)
                logger.info(f"Request {session_id} rejected by {admin_id}: {reason}")
            
            return success
        except Exception as e:
            logger.error(f"Error rejecting request {session_id}: {e}")
            return False
    
    def auto_process_requests(self) -> int:
        """Auto-process requests for available books"""
        try:
            processed_count = 0
            pending_requests = self.admin_db.get_pending_requests()
            
            for request in pending_requests:
                session_id = request['session_id']
                
                # Get request items
                request_items = self.admin_db.get_user_request_list(session_id)
                
                # Check if all books are available
                all_available = all(item.get('available', False) for item in request_items)
                
                if all_available and len(request_items) > 0:
                    # Auto-approve request
                    if self.approve_request(session_id, 'auto-system'):
                        processed_count += 1
                        logger.info(f"Auto-approved request {session_id} with {len(request_items)} available books")
            
            if processed_count > 0:
                # Send admin notification about auto-processing
                self.send_admin_auto_process_notification(processed_count)
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Error in auto-processing: {e}")
            return 0
    
    def send_approval_notification(self, session_id: str):
        """Send approval notification to user"""
        try:
            # Get request details
            request_items = self.admin_db.get_user_request_list(session_id)
            
            if request_items:
                # Format download links message
                message_lines = [
                    "✅ *REQUEST APPROVED*",
                    "=" * 30,
                    f"📋 Session ID: `{session_id}`",
                    f"📚 Total Books: {len(request_items)}",
                    f"⏰ Approved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "",
                    "📥 *DOWNLOAD LINKS:*"
                ]
                
                available_count = 0
                for i, item in enumerate(request_items, 1):
                    if item.get('available'):
                        available_count += 1
                        message_lines.append(f"{i}. *{item['book_title']}*")
                        message_lines.append(f"   📄 {item.get('extension', 'PDF').upper()}")
                        message_lines.append(f"   🔗 [Download Link - Contact Admin]")
                        message_lines.append("")
                
                if available_count == 0:
                    message_lines.extend([
                        "⚠️ *Note:* Books are being processed",
                        "📱 You'll receive download links via WhatsApp shortly"
                    ])
                
                message_lines.extend([
                    "",
                    "📱 *Admin Contact:* +62 857-9952-0350",
                    "💡 *Include your Session ID when contacting*"
                ])
                
                message = "\n".join(message_lines)
                
                # Send via WhatsApp (implement actual API call here)
                logger.info(f"📱 Approval notification sent for {session_id}")
                
        except Exception as e:
            logger.error(f"Error sending approval notification: {e}")
    
    def send_rejection_notification(self, session_id: str, reason: str):
        """Send rejection notification to user"""
        try:
            message_lines = [
                "❌ *REQUEST REJECTED*",
                "=" * 30,
                f"📋 Session ID: `{session_id}`",
                f"⏰ Rejected: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ]
            
            if reason:
                message_lines.extend([
                    "",
                    f"📝 *Reason:* {reason}"
                ])
            
            message_lines.extend([
                "",
                "💡 *You can submit a new request anytime*",
                "📱 *Admin Contact:* +62 857-9952-0350"
            ])
            
            message = "\n".join(message_lines)
            
            # Send via WhatsApp (implement actual API call here)
            logger.info(f"📱 Rejection notification sent for {session_id}")
            
        except Exception as e:
            logger.error(f"Error sending rejection notification: {e}")
    
    def send_admin_auto_process_notification(self, count: int):
        """Send notification to admin about auto-processing"""
        try:
            message = f"""
🤖 *AUTO-PROCESSING COMPLETE*

✅ Auto-approved: *{count} requests*
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

All approved requests had books that are available for download.
"""
            
            # Send to admin WhatsApp (implement actual API call here)
            logger.info(f"📱 Auto-process notification sent to admin: {count} requests")
            
        except Exception as e:
            logger.error(f"Error sending auto-process notification: {e}")
    
    # Admin Telegram Bot Commands
    def admin_cmd_start(self, message):
        """Admin bot start command"""
        welcome_msg = """
🔧 <b>Book Request Admin Bot</b>

Welcome! This bot helps you manage book requests efficiently.

<b>📋 Available Commands:</b>
• /dashboard - View statistics
• /requests - View pending requests
• /approve [session_id] - Approve request
• /reject [session_id] - Reject request
• /details [session_id] - View request details
• /auto - Auto-process available books
• /help - Show this help

<b>🤖 Automation Features:</b>
• Auto-approve requests with available books
• WhatsApp notifications for users
• Real-time request monitoring

Let's get started! 🚀
"""
        
        if TELEGRAM_AVAILABLE:
            self.admin_bot.send_message(message.chat.id, welcome_msg)
    
    def admin_cmd_dashboard(self, message):
        """Admin dashboard command"""
        try:
            stats = self.get_admin_stats()
            
            dashboard_msg = f"""
📊 <b>Admin Dashboard</b>

📚 <b>Library Stats:</b>
• Total Books: <b>{stats['total_books']:,}</b>
• Available Books: <b>{stats['available_books']:,}</b>
• Availability Rate: <b>{stats['availability_rate']}%</b>

📋 <b>Request Stats:</b>
• Total Requests: <b>{stats['total_requests']:,}</b>
• Pending Requests: <b>{stats['pending_requests']}</b>
• Requests Today: <b>{stats['requests_today']}</b>

⏰ <b>Updated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("📋 View Requests", callback_data="view_requests"),
                InlineKeyboardButton("🤖 Auto-Process", callback_data="auto_process")
            )
            keyboard.add(InlineKeyboardButton("🔄 Refresh", callback_data="refresh_dashboard"))
            
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, dashboard_msg, reply_markup=keyboard)
                
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, "❌ Error loading dashboard")
    
    def admin_cmd_requests(self, message):
        """Admin view requests command"""
        try:
            pending_requests = self.get_pending_requests()
            
            if not pending_requests:
                if TELEGRAM_AVAILABLE:
                    self.admin_bot.send_message(message.chat.id, "✅ No pending requests at the moment!")
                return
            
            msg = f"📋 <b>Pending Requests ({len(pending_requests)})</b>\n\n"
            
            for req in pending_requests[:10]:  # Limit to 10 for readability
                msg += f"🆔 <code>{req['session_id']}</code>\n"
                msg += f"👤 User: {req['user_id']}"
                if req['user_name']:
                    msg += f" ({req['user_name']})"
                msg += f"\n📚 Books: <b>{req['item_count']}</b>\n"
                msg += f"⏰ {req['created_at']}\n\n"
            
            if len(pending_requests) > 10:
                msg += f"... and {len(pending_requests) - 10} more requests"
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🤖 Auto-Process All", callback_data="auto_process"))
            
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, msg, reply_markup=keyboard)
                
        except Exception as e:
            logger.error(f"Requests error: {e}")
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, "❌ Error loading requests")
    
    def admin_cmd_approve(self, message):
        """Admin approve command"""
        try:
            parts = message.text.split()
            if len(parts) < 2:
                if TELEGRAM_AVAILABLE:
                    self.admin_bot.send_message(message.chat.id, "Usage: /approve [session_id]")
                return
            
            session_id = parts[1]
            success = self.approve_request(session_id, 'telegram-admin')
            
            if success:
                msg = f"✅ Request {session_id} approved successfully!"
            else:
                msg = f"❌ Failed to approve request {session_id}"
            
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, msg)
                
        except Exception as e:
            logger.error(f"Approve error: {e}")
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, "❌ Error approving request")
    
    def admin_cmd_reject(self, message):
        """Admin reject command"""
        try:
            parts = message.text.split(None, 2)
            if len(parts) < 2:
                if TELEGRAM_AVAILABLE:
                    self.admin_bot.send_message(message.chat.id, "Usage: /reject [session_id] [reason]")
                return
            
            session_id = parts[1]
            reason = parts[2] if len(parts) > 2 else ''
            
            success = self.reject_request(session_id, reason, 'telegram-admin')
            
            if success:
                msg = f"❌ Request {session_id} rejected successfully!"
            else:
                msg = f"❌ Failed to reject request {session_id}"
            
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, msg)
                
        except Exception as e:
            logger.error(f"Reject error: {e}")
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, "❌ Error rejecting request")
    
    def admin_cmd_details(self, message):
        """Admin view details command"""
        try:
            parts = message.text.split()
            if len(parts) < 2:
                if TELEGRAM_AVAILABLE:
                    self.admin_bot.send_message(message.chat.id, "Usage: /details [session_id]")
                return
            
            session_id = parts[1]
            request_items = self.admin_db.get_user_request_list(session_id)
            
            if not request_items:
                if TELEGRAM_AVAILABLE:
                    self.admin_bot.send_message(message.chat.id, f"❌ Request {session_id} not found")
                return
            
            msg = f"📖 <b>Request Details: {session_id}</b>\n\n"
            msg += f"📚 <b>Total Books: {len(request_items)}</b>\n\n"
            
            available_count = 0
            for i, item in enumerate(request_items, 1):
                msg += f"{i}. <b>{item['book_title']}</b>\n"
                if item['book_author']:
                    msg += f"   👤 {item['book_author']}\n"
                if item['book_publisher']:
                    msg += f"   🏢 {item['book_publisher']}\n"
                
                if item.get('available'):
                    msg += "   ✅ Available\n"
                    available_count += 1
                else:
                    msg += "   ❌ Not available\n"
                msg += "\n"
            
            msg += f"📊 <b>Available: {available_count}/{len(request_items)}</b>"
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{session_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{session_id}")
            )
            
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, msg, reply_markup=keyboard)
                
        except Exception as e:
            logger.error(f"Details error: {e}")
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, "❌ Error loading details")
    
    def admin_cmd_auto_process(self, message):
        """Admin auto-process command"""
        try:
            processed = self.auto_process_requests()
            
            if processed > 0:
                msg = f"🤖 Auto-processed <b>{processed}</b> requests with available books!"
            else:
                msg = "ℹ️ No requests with fully available books to auto-process."
            
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, msg)
                
        except Exception as e:
            logger.error(f"Auto-process error: {e}")
            if TELEGRAM_AVAILABLE:
                self.admin_bot.send_message(message.chat.id, "❌ Error in auto-processing")
    
    def admin_cmd_help(self, message):
        """Admin help command"""
        help_msg = """
🔧 <b>Admin Bot Help</b>

<b>📊 Dashboard Commands:</b>
• /dashboard - View statistics
• /requests - View pending requests

<b>🔧 Management Commands:</b>
• /approve [session_id] - Approve request
• /reject [session_id] [reason] - Reject request
• /details [session_id] - View request details

<b>🤖 Automation Commands:</b>
• /auto - Auto-process available books

<b>💡 Tips:</b>
• Session IDs are shown in notifications
• Auto-processing approves requests with available books
• Users receive WhatsApp notifications automatically

<b>📱 Admin WhatsApp:</b> +62 857-9952-0350
"""
        
        if TELEGRAM_AVAILABLE:
            self.admin_bot.send_message(message.chat.id, help_msg)
    
    def handle_admin_callback(self, call):
        """Handle admin bot callbacks"""
        try:
            data = call.data
            
            if data == "view_requests":
                self.admin_cmd_requests(call.message)
            elif data == "auto_process":
                self.admin_cmd_auto_process(call.message)
            elif data == "refresh_dashboard":
                self.admin_cmd_dashboard(call.message)
            elif data.startswith("approve_"):
                session_id = data[8:]
                success = self.approve_request(session_id, 'telegram-admin')
                msg = f"✅ Approved {session_id}" if success else f"❌ Failed to approve {session_id}"
                if TELEGRAM_AVAILABLE:
                    self.admin_bot.edit_message_text(msg, call.message.chat.id, call.message.message_id)
            elif data.startswith("reject_"):
                session_id = data[7:]
                success = self.reject_request(session_id, 'Manual rejection', 'telegram-admin')
                msg = f"❌ Rejected {session_id}" if success else f"❌ Failed to reject {session_id}"
                if TELEGRAM_AVAILABLE:
                    self.admin_bot.edit_message_text(msg, call.message.chat.id, call.message.message_id)
            
            if TELEGRAM_AVAILABLE:
                self.admin_bot.answer_callback_query(call.id)
                
        except Exception as e:
            logger.error(f"Admin callback error: {e}")
            if TELEGRAM_AVAILABLE:
                self.admin_bot.answer_callback_query(call.id, "❌ Error processing request")
    
    def get_dashboard_stats(self) -> Dict:
        """Get dashboard statistics"""
        try:
            stats = self.admin_db.get_database_stats()
            
            # Add additional stats
            pending_requests = self.admin_db.get_pending_requests()
            stats['pending_requests_count'] = len(pending_requests)
            
            # Recent activity
            all_requests = self.admin_db.get_all_requests()
            stats['total_requests'] = len(all_requests)
            
            return stats
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {}
    
    def auto_process_requests(self) -> int:
        """Auto-process requests where all books are available"""
        if not self.auto_approve_available:
            return 0
        
        try:
            pending_requests = self.admin_db.get_pending_requests()
            processed_count = 0
            
            for request in pending_requests:
                request_items = self.admin_db.get_request_details(request['id'])
                all_available = True
                
                for item in request_items:
                    book = self.admin_db.get_book_details(item['book_id'])
                    if book and book.get('download_status') != 'done':
                        all_available = False
                        break
                
                if all_available and request_items:
                    success = self.admin_db.approve_request(request['id'], 'auto-admin')
                    if success:
                        processed_count += 1
                        logger.info(f"Auto-approved request {request['id']}")
            
            return processed_count
        except Exception as e:
            logger.error(f"Error auto-processing requests: {e}")
            return 0
    
    def run_web_interface(self, host='0.0.0.0', port=5000):
        """Run Flask web interface"""
        if not FLASK_AVAILABLE:
            logger.error("❌ Flask not available for web interface")
            return
        
        logger.info(f"🌐 Starting admin web interface on http://{host}:{port}")
        self.app.run(host=host, port=port, debug=False)
    
    def run_admin_bot(self):
        """Run Telegram admin bot"""
        if not TELEGRAM_AVAILABLE:
            logger.error("❌ Telegram libraries not available for admin bot")
            return
        
        logger.info("🤖 Starting admin Telegram bot...")
        
        try:
            self.admin_bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            logger.error(f"❌ Admin bot error: {e}")
        finally:
            logger.info("👋 Admin bot stopped")

def main():
    """Main function"""
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Initialize admin panel
    admin_panel = AdminPanel()
    
    # Choice of interface
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == 'web':
            admin_panel.run_web_interface()
        elif sys.argv[1] == 'bot':
            admin_panel.run_admin_bot()
        else:
            print("Usage: python admin_panel.py [web|bot]")
    else:
        print("📋 Admin Panel Options:")
        print("  python admin_panel.py web  - Start web interface")
        print("  python admin_panel.py bot  - Start Telegram bot")

def start_admin_bot():
    """Function to start admin bot - for use by startup script"""
    admin_panel = AdminPanel()
    admin_panel.run_admin_bot()

if __name__ == "__main__":
    main()