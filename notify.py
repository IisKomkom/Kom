import os
import requests
import time
import logging
from threading import Lock, Thread
from queue import Queue, Empty
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import json
import hashlib
from functools import wraps
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

# Enhanced Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'xxxx')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', 'yyyy')
TELEGRAM_THREAD_ID = os.getenv('TELEGRAM_THREAD_ID')  # For forum groups
BACKUP_CHAT_ID = os.getenv('BACKUP_TELEGRAM_CHAT_ID')  # Backup notification channel

# Email Configuration (backup notification)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_TO = os.getenv('EMAIL_TO')

# Enhanced Settings
MAX_RETRY_ATTEMPTS = 3
QUEUE_TIMEOUT = 10
MESSAGE_RATE_LIMIT = 30  # Messages per minute
BATCH_PROCESSING_SIZE = 5
LOG_FILE = 'logs/notifications.log'

# Setup enhanced logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Thread-safe data structures
_last_sent = {}
_message_queue = Queue()
_processing_thread = None
_lock = Lock()
_stats = {
    'sent': 0,
    'failed': 0,
    'queued': 0,
    'rate_limited': 0
}

class NotificationManager:
    """Enhanced notification management system"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 30
        self.start_processing_thread()
        
    def start_processing_thread(self):
        """Start background thread for processing notification queue"""
        global _processing_thread
        if _processing_thread is None or not _processing_thread.is_alive():
            _processing_thread = Thread(target=self._process_queue, daemon=True)
            _processing_thread.start()
            logger.info("✅ Notification processing thread started")
    
    def _process_queue(self):
        """Background queue processing with rate limiting"""
        last_send_time = 0
        min_interval = 60 / MESSAGE_RATE_LIMIT  # Seconds between messages
        
        while True:
            try:
                # Rate limiting
                current_time = time.time()
                if current_time - last_send_time < min_interval:
                    time.sleep(min_interval - (current_time - last_send_time))
                
                # Get message from queue
                try:
                    message_data = _message_queue.get(timeout=QUEUE_TIMEOUT)
                except Empty:
                    continue
                
                # Process message
                success = self._send_message_internal(message_data)
                
                if success:
                    with _lock:
                        _stats['sent'] += 1
                else:
                    with _lock:
                        _stats['failed'] += 1
                
                last_send_time = time.time()
                
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                time.sleep(5)
    
    def _send_message_internal(self, message_data: Dict) -> bool:
        """Internal message sending with retry logic"""
        message = message_data['message']
        channels = message_data.get('channels', ['telegram'])
        priority = message_data.get('priority', 'normal')
        
        success = False
        
        # Try primary channels first
        for channel in channels:
            if channel == 'telegram':
                if self._send_telegram_message(message, priority):
                    success = True
                    break
            elif channel == 'email':
                if self._send_email_message(message, priority):
                    success = True
                    break
        
        # If primary channels fail and it's high priority, try backup
        if not success and priority == 'high':
            if BACKUP_CHAT_ID and self._send_telegram_backup(message):
                success = True
        
        return success
    
    def _send_telegram_message(self, message: str, priority: str = 'normal') -> bool:
        """Enhanced Telegram message sending"""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("Telegram credentials not configured")
            return False
        
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        
        # Enhanced message formatting
        if priority == 'high':
            message = f"🚨 <b>HIGH PRIORITY</b>\n{message}"
        elif priority == 'low':
            message = f"ℹ️ {message}"
        
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        # Add thread support for forum groups
        if TELEGRAM_THREAD_ID:
            payload['message_thread_id'] = TELEGRAM_THREAD_ID
        
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                resp = self.session.post(url, data=payload)
                
                if resp.status_code == 200:
                    logger.info(f"✅ Telegram message sent successfully (attempt {attempt + 1})")
                    return True
                elif resp.status_code == 429:  # Rate limited
                    retry_after = int(resp.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    with _lock:
                        _stats['rate_limited'] += 1
                else:
                    logger.error(f"Telegram error: {resp.status_code} - {resp.text}")
                    
            except Exception as e:
                logger.error(f"Telegram exception (attempt {attempt + 1}): {e}")
                
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return False
    
    def _send_telegram_backup(self, message: str) -> bool:
        """Send to backup Telegram channel"""
        if not BACKUP_CHAT_ID:
            return False
        
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        payload = {
            'chat_id': BACKUP_CHAT_ID,
            'text': f"🔄 <b>BACKUP NOTIFICATION</b>\n{message}",
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        try:
            resp = self.session.post(url, data=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Backup Telegram failed: {e}")
            return False
    
    def _send_email_message(self, message: str, priority: str = 'normal') -> bool:
        """Send email notification as backup"""
        if not all([EMAIL_USER, EMAIL_PASS, EMAIL_TO, SMTP_SERVER]):
            logger.warning("Email credentials not configured")
            return False
        
        try:
            msg = MimeMultipart()
            msg['From'] = EMAIL_USER
            msg['To'] = EMAIL_TO
            msg['Subject'] = f"[{priority.upper()}] Download Bot Notification"
            
            # Convert HTML to plain text for email
            plain_message = message.replace('<b>', '').replace('</b>', '')
            plain_message = plain_message.replace('<code>', '').replace('</code>', '')
            msg.attach(MimeText(plain_message, 'plain'))
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PASS)
                server.send_message(msg)
            
            logger.info("✅ Email notification sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False

# Initialize notification manager
notification_manager = NotificationManager()

def rate_limit_check(tag: str, min_interval: int) -> bool:
    """Enhanced rate limiting with tag-based tracking"""
    if not tag:
        return True
    
    now = time.time()
    with _lock:
        last_time = _last_sent.get(tag, 0)
        if now - last_time < min_interval:
            logger.debug(f"Rate limit hit for tag: {tag}")
            with _lock:
                _stats['rate_limited'] += 1
            return False
        _last_sent[tag] = now
    return True

def queue_notification(message: str, tag: Optional[str] = None, 
                      min_interval: int = 300, priority: str = 'normal',
                      channels: List[str] = None) -> bool:
    """Enhanced notification queuing with multiple channels"""
    
    # Rate limiting check
    if tag and not rate_limit_check(tag, min_interval):
        return False
    
    # Default channels
    if channels is None:
        channels = ['telegram']
    
    # Prepare message data
    message_data = {
        'message': message,
        'tag': tag,
        'priority': priority,
        'channels': channels,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        _message_queue.put(message_data, timeout=5)
        with _lock:
            _stats['queued'] += 1
        logger.info(f"📩 Message queued: {tag or 'no-tag'} [{priority}]")
        return True
    except Exception as e:
        logger.error(f"Failed to queue message: {e}")
        return False

# Legacy compatibility functions (enhanced)
def send_telegram(message: str, tag: Optional[str] = None, min_interval: int = 300,
                 priority: str = 'normal', channels: List[str] = None):
    """Enhanced Telegram sender with backward compatibility"""
    return queue_notification(message, tag, min_interval, priority, channels)

# Enhanced notification templates
def send_batch_summary(success: int, failed: int, batch_type: str = 'Download', 
                      extra: str = '', details: Dict = None):
    """Enhanced batch summary with detailed metrics"""
    
    # Calculate metrics
    total = success + failed
    success_rate = (success / max(total, 1)) * 100
    
    # Priority based on success rate
    if success_rate < 50:
        priority = 'high'
        icon = '🔴'
    elif success_rate < 80:
        priority = 'normal'
        icon = '🟡'
    else:
        priority = 'low'
        icon = '🟢'
    
    msg = f"{icon} <b>{batch_type} Batch Completed</b>\n"
    msg += f"✅ Success: <b>{success}</b>\n"
    msg += f"❌ Failed: <b>{failed}</b>\n"
    msg += f"📊 Success Rate: <b>{success_rate:.1f}%</b>"
    
    if extra:
        msg += f"\n💡 {extra}"
    
    # Add detailed metrics if provided
    if details:
        msg += f"\n\n📈 <b>Details:</b>"
        for key, value in details.items():
            msg += f"\n• {key}: {value}"
    
    msg += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
    
    return queue_notification(
        msg, 
        tag=f'batch_{batch_type.lower()}',
        priority=priority,
        min_interval=180  # 3 minutes for batch summaries
    )

def send_fatal_error(error_msg: str, context: str = '', trace: str = None):
    """Enhanced fatal error notification with context"""
    
    # Create error hash for deduplication
    error_hash = hashlib.md5(f"{error_msg}{context}".encode()).hexdigest()[:8]
    
    msg = f"🔥 <b>Fatal Error</b>"
    if context:
        msg += f" in <code>{context}</code>"
    
    msg += f"\n🆔 Error ID: <code>{error_hash}</code>"
    msg += f"\n⚠️ <code>{error_msg}</code>"
    
    if trace:
        # Truncate long traces
        if len(trace) > 500:
            trace = trace[:500] + "..."
        msg += f"\n\n🔍 <b>Trace:</b>\n<code>{trace}</code>"
    
    msg += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return queue_notification(
        msg, 
        tag=f'fatal_error_{error_hash}',
        priority='high',
        min_interval=600,  # 10 minutes for fatal errors
        channels=['telegram', 'email']  # Use multiple channels for critical errors
    )

def send_login_failed(email: str, reason: str = None, retry_count: int = 0):
    """Enhanced login failure notification"""
    
    # Priority based on retry count
    if retry_count >= 3:
        priority = 'high'
        icon = '🚨'
    else:
        priority = 'normal'
        icon = '⚠️'
    
    msg = f"{icon} <b>Login Failed</b>\n"
    msg += f"👤 Account: <b>{email}</b>"
    
    if reason:
        msg += f"\n📝 Reason: {reason}"
    
    if retry_count > 0:
        msg += f"\n🔄 Retry #{retry_count}"
    
    msg += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
    
    return queue_notification(
        msg,
        tag=f'login_failed_{email}',
        priority=priority,
        min_interval=900  # 15 minutes per account
    )

def send_limit_hit(email: str, limit_type: str = 'download', reset_time: str = None):
    """Enhanced limit notification with reset information"""
    
    msg = f"🚫 <b>Account Limit Reached</b>\n"
    msg += f"👤 Account: <b>{email}</b>\n"
    msg += f"📋 Type: {limit_type.title()} limit"
    
    if reset_time:
        msg += f"\n🔄 Reset: {reset_time}"
    else:
        msg += f"\n🔄 Reset: Tomorrow"
    
    msg += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
    
    return queue_notification(
        msg,
        tag=f'limit_{email}',
        priority='normal',
        min_interval=900  # 15 minutes per account
    )

def send_system_status(status: Dict, component: str = 'system'):
    """Send system status notification"""
    
    health_indicators = {
        'healthy': '🟢',
        'warning': '🟡', 
        'critical': '🔴',
        'unknown': '⚫'
    }
    
    overall_status = status.get('status', 'unknown')
    icon = health_indicators.get(overall_status, '⚫')
    
    msg = f"{icon} <b>System Status: {component.title()}</b>\n"
    msg += f"Status: <b>{overall_status.title()}</b>\n"
    
    # Add metrics if available
    if 'metrics' in status:
        msg += "\n📊 <b>Metrics:</b>"
        for key, value in status['metrics'].items():
            msg += f"\n• {key}: {value}"
    
    msg += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
    
    priority = 'high' if overall_status == 'critical' else 'normal'
    
    return queue_notification(
        msg,
        tag=f'status_{component}',
        priority=priority,
        min_interval=300  # 5 minutes for status updates
    )

def send_download_progress(downloaded: int, total: int, current_book: str = None):
    """Send download progress updates (for long-running processes)"""
    
    progress_percent = (downloaded / max(total, 1)) * 100
    progress_bar = create_progress_bar(progress_percent)
    
    msg = f"📥 <b>Download Progress</b>\n"
    msg += f"{progress_bar} {progress_percent:.1f}%\n"
    msg += f"✅ Completed: <b>{downloaded}</b>/<b>{total}</b>"
    
    if current_book:
        msg += f"\n📖 Current: {current_book[:50]}..."
    
    # Only send every 10% or for milestone numbers
    milestone = downloaded in [10, 25, 50, 100, 250, 500, 1000] or downloaded % 100 == 0
    should_send = progress_percent % 10 == 0 or milestone
    
    if should_send:
        return queue_notification(
            msg,
            tag='download_progress',
            priority='low',
            min_interval=300  # Max once per 5 minutes
        )
    
    return False

def create_progress_bar(percent: float, length: int = 10) -> str:
    """Create visual progress bar"""
    filled = int(length * percent / 100)
    bar = '█' * filled + '░' * (length - filled)
    return f"[{bar}]"

def get_notification_stats() -> Dict:
    """Get notification system statistics"""
    with _lock:
        stats = _stats.copy()
    
    stats['queue_size'] = _message_queue.qsize()
    stats['thread_alive'] = _processing_thread.is_alive() if _processing_thread else False
    stats['last_sent_count'] = len(_last_sent)
    
    return stats

def reset_notification_stats():
    """Reset notification statistics"""
    global _stats
    with _lock:
        _stats = {
            'sent': 0,
            'failed': 0,
            'queued': 0,
            'rate_limited': 0
        }
    logger.info("📊 Notification stats reset")

# Health check for notification system
def health_check() -> Dict:
    """Check notification system health"""
    health = {
        'status': 'healthy',
        'telegram_configured': bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        'email_configured': bool(EMAIL_USER and EMAIL_PASS and EMAIL_TO),
        'queue_size': _message_queue.qsize(),
        'thread_running': _processing_thread.is_alive() if _processing_thread else False,
        'stats': get_notification_stats()
    }
    
    # Determine overall health
    if not health['thread_running']:
        health['status'] = 'critical'
    elif health['queue_size'] > 50:
        health['status'] = 'warning'
    
    return health

# Initialize notification system on import
logger.info("🚀 Enhanced notification system initialized")
logger.info(f"📱 Telegram: {'✅' if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID else '❌'}")
logger.info(f"📧 Email: {'✅' if EMAIL_USER and EMAIL_PASS and EMAIL_TO else '❌'}")
logger.info(f"🔄 Backup Channel: {'✅' if BACKUP_CHAT_ID else '❌'}") 