from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
import os
from sqlalchemy import or_, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
import json
import logging
import time
from datetime import datetime, timedelta
import redis
from functools import wraps
import hashlib
import threading

# Enhanced Configuration
BOOKMARK_DB_PATH = 'bookmark_db.json'
CACHE_REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
RATE_LIMIT_STORAGE_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/1')

# Setup enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/flask_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Thread-safe bookmark operations
bookmark_lock = threading.Lock()

def load_bookmarks():
    """Thread-safe bookmark loading with error handling"""
    with bookmark_lock:
        if not os.path.exists(BOOKMARK_DB_PATH):
            return {}
        try:
            with open(BOOKMARK_DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading bookmarks: {e}")
            return {}

def save_bookmarks(data):
    """Thread-safe bookmark saving with backup"""
    with bookmark_lock:
        try:
            # Create backup first
            if os.path.exists(BOOKMARK_DB_PATH):
                backup_path = f"{BOOKMARK_DB_PATH}.backup"
                with open(BOOKMARK_DB_PATH, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
            
            # Save new data
            with open(BOOKMARK_DB_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Bookmarks saved successfully: {len(data)} users")
        except Exception as e:
            logger.error(f"Error saving bookmarks: {e}")
            raise

app = Flask(__name__)

# Enhanced Flask Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'poolclass': QueuePool,
    'pool_size': 20,
    'max_overflow': 30,
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'connect_args': {
        'connect_timeout': 10,
        'application_name': 'flask_api_receiver'
    }
}

# Cache Configuration
cache_config = {
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': CACHE_REDIS_URL,
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'flask_api:'
}

try:
    cache = Cache(app, config=cache_config)
    logger.info("Redis cache initialized successfully")
except Exception as e:
    logger.warning(f"Redis cache failed, using simple cache: {e}")
    cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Rate Limiting
try:
    limiter = Limiter(
        app,
        key_func=get_remote_address,
        storage_uri=RATE_LIMIT_STORAGE_URL,
        default_limits=["1000 per hour", "100 per minute"]
    )
    logger.info("Rate limiter initialized successfully")
except Exception as e:
    logger.warning(f"Rate limiter failed to initialize: {e}")
    limiter = None

db = SQLAlchemy(app)

# Database connection monitoring
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if 'sqlite' in str(dbapi_connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

# Enhanced BookData Model
class BookData(db.Model):
    __tablename__ = 'book_data'
    
    id = db.Column(db.String(64), primary_key=True)
    title = db.Column(db.String(255), index=True)
    author = db.Column(db.String(255), index=True)
    year = db.Column(db.String(16))
    publisher = db.Column(db.String(255), index=True)
    language = db.Column(db.String(64))
    extension = db.Column(db.String(16))
    filesize = db.Column(db.String(32))
    book_url = db.Column(db.String(512))
    cover_image_url = db.Column(db.String(512))
    source_type = db.Column(db.String(64))
    cover_url_final = db.Column(db.String(512))
    files_url_drive = db.Column(db.String(512))
    download_status = db.Column(db.String(32), default='pending', index=True)
    claimed_by = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'year': self.year,
            'publisher': self.publisher,
            'language': self.language,
            'extension': self.extension,
            'filesize': self.filesize,
            'book_url': self.book_url,
            'cover_image_url': self.cover_image_url,
            'source_type': self.source_type,
            'cover_url_final': self.cover_url_final,
            'files_url_drive': self.files_url_drive,
            'download_status': self.download_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# Enhanced Error Handling
def handle_errors(f):
    """Decorator for enhanced error handling"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            start_time = time.time()
            result = f(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"{f.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)
            db.session.rollback()
            return jsonify({
                'status': 'error', 
                'message': 'Internal server error',
                'error_id': hashlib.md5(str(e).encode()).hexdigest()[:8]
            }), 500
    return decorated_function

# Rate limiting decorator
def rate_limit(limit_string):
    """Custom rate limiting decorator"""
    def decorator(f):
        if limiter:
            return limiter.limit(limit_string)(f)
        return f
    return decorator

@app.route('/upload_data', methods=['POST'])
@handle_errors
@rate_limit("50 per minute")
def upload_data():
    """Enhanced insert/update book data with batch processing and validation."""
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400
    
    results = []
    
    # Handle batch data
    if isinstance(data, list):
        if len(data) > 100:  # Limit batch size
            return jsonify({'status': 'error', 'message': 'Batch size too large (max 100)'}), 400
            
        batch_start_time = time.time()
        
        for item in data:
            if not item or not item.get('id'):
                results.append({'status': 'error', 'message': 'Missing ID'})
                continue
                
            try:
                book = BookData.query.get(item['id'])
                if book:
                    # Update existing
                    for k, v in item.items():
                        if hasattr(book, k) and k != 'id':
                            setattr(book, k, v)
                    book.updated_at = datetime.utcnow()
                    results.append({'id': item['id'], 'status': 'updated'})
                else:
                    # Insert new
                    book = BookData(**item)
                    db.session.add(book)
                    results.append({'id': item['id'], 'status': 'inserted'})
                    
            except Exception as e:
                logger.error(f"Error processing item {item.get('id')}: {e}")
                results.append({'id': item.get('id'), 'status': 'error', 'message': str(e)})
        
        try:
            db.session.commit()
            batch_duration = time.time() - batch_start_time
            logger.info(f"Batch upload completed: {len(data)} items in {batch_duration:.3f}s")
            
            # Invalidate relevant caches
            cache.delete('stats')
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Batch commit failed: {e}")
            return jsonify({'status': 'error', 'message': 'Batch commit failed'}), 500
            
        return jsonify(results)
    
    else:
        # Handle single item
        if not data.get('id'):
            return jsonify({'status': 'error', 'message': 'Missing ID'}), 400
            
        try:
            book = BookData.query.get(data['id'])
            if book:
                for k, v in data.items():
                    if hasattr(book, k) and k != 'id':
                        setattr(book, k, v)
                book.updated_at = datetime.utcnow()
                db.session.commit()
                cache.delete('stats')  # Invalidate stats cache
                return jsonify({'status': 'updated'})
            else:
                book = BookData(**data)
                db.session.add(book)
                db.session.commit()
                cache.delete('stats')
                return jsonify({'status': 'inserted'})
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in single upload: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/claim_books', methods=['POST'])
@handle_errors
@rate_limit("30 per minute")
def claim_books():
    """Enhanced atomic book claiming with better error handling."""
    req_json = request.get_json() or {}
    batch_size = min(int(req_json.get('batch_size', 5)), 20)  # Limit max batch size
    instance_id = req_json.get('instance_id', 'instance')
    
    if not instance_id or len(instance_id) > 64:
        return jsonify({'status': 'error', 'message': 'Invalid instance_id'}), 400
    
    try:
        with db.session.begin_nested():
            books = (BookData.query
                    .filter_by(download_status='pending')
                    .with_for_update(skip_locked=True)  # Skip locked rows
                    .limit(batch_size)
                    .all())
            
            claimed_books = []
            for book in books:
                book.download_status = 'in_progress'
                book.claimed_by = instance_id
                book.updated_at = datetime.utcnow()
                claimed_books.append(book.to_dict())
            
            db.session.commit()
            
        logger.info(f"Claimed {len(claimed_books)} books for instance {instance_id}")
        return jsonify(claimed_books)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error claiming books: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to claim books'}), 500

@app.route('/reset_inprogress', methods=['POST'])
@handle_errors
@rate_limit("10 per minute")
def reset_inprogress():
    """Enhanced reset with better filtering and logging."""
    data = request.get_json() or {}
    instance_id = data.get('instance_id')
    reset_failed = data.get('reset_failed', False)
    max_age_hours = data.get('max_age_hours', 24)  # Reset items older than X hours
    
    try:
        query = BookData.query
        
        if instance_id:
            query = query.filter_by(claimed_by=instance_id)
        
        # Add age filter for stuck processes
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        query = query.filter(BookData.updated_at < cutoff_time)
        
        if reset_failed:
            books = query.filter(BookData.download_status.in_(['in_progress', 'failed'])).all()
        else:
            books = query.filter_by(download_status='in_progress').all()
        
        count = 0
        for book in books:
            book.download_status = 'pending'
            book.claimed_by = None
            book.updated_at = datetime.utcnow()
            count += 1
        
        db.session.commit()
        logger.info(f"Reset {count} books (instance: {instance_id}, failed: {reset_failed})")
        
        return jsonify({'status': 'success', 'reset_count': count})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting books: {e}")
        return jsonify({'status': 'error', 'message': 'Reset failed'}), 500

@app.route('/get_ready_for_upload', methods=['GET'])
@handle_errors
@rate_limit("50 per minute")
def get_ready_for_upload():
    """Ambil buku yang siap diupload (download_status=done, belum ada files_url_drive)."""
    books = BookData.query.filter(
        BookData.download_status == 'done',
        (BookData.files_url_drive == None) | (BookData.files_url_drive == '')
    ).all()
    result = []
    for b in books:
        result.append({
            'id': b.id,
            'title': b.title,
            'author': b.author,
            'year': b.year,
            'publisher': b.publisher,
            'language': b.language,
            'extension': b.extension,
            'filesize': b.filesize,
            'book_url': b.book_url,
            'cover_image_url': b.cover_image_url,
            'source_type': b.source_type,
            'cover_url_final': b.cover_url_final,
            'files_url_drive': b.files_url_drive
        })
    return jsonify(result)

@app.route('/claim_upload_batch', methods=['POST'])
@handle_errors
@rate_limit("30 per minute")
def claim_upload_batch():
    """Enhanced atomic claim for upload batch."""
    data = request.get_json() or {}
    batch_size = min(int(data.get('batch_size', 10)), 20) # Limit max batch size
    instance_id = data.get('instance_id', 'uploader')
    
    if not instance_id or len(instance_id) > 64:
        return jsonify({'status': 'error', 'message': 'Invalid instance_id'}), 400
    
    try:
        with db.session.begin_nested():
            books = (BookData.query
                    .filter(
                        BookData.download_status == 'done',
                        (BookData.files_url_drive == None) | (BookData.files_url_drive == ''),
                        (BookData.claimed_by == None) | (BookData.claimed_by == '')
                    )
                    .with_for_update(skip_locked=True) # Skip locked rows
                    .limit(batch_size)
                    .all())
            
            for book in books:
                book.claimed_by = instance_id
                book.updated_at = datetime.utcnow()
            
            db.session.commit()
            
        result = []
        for b in books:
            result.append({
                'id': b.id,
                'title': b.title,
                'author': b.author,
                'year': b.year,
                'publisher': b.publisher,
                'language': b.language,
                'extension': b.extension,
                'filesize': b.filesize,
                'book_url': b.book_url,
                'cover_image_url': b.cover_image_url,
                'source_type': b.source_type,
                'cover_url_final': b.cover_url_final,
                'files_url_drive': b.files_url_drive
            })
        return jsonify(result)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error claiming upload batch: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to claim upload batch'}), 500

@app.route('/search_books', methods=['GET'])
@handle_errors
@rate_limit("100 per minute")
def search_books():
    """Enhanced search with caching and pagination."""
    query = request.args.get('q', '').strip()
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, max(1, int(request.args.get('per_page', 20))))
    
    if not query or len(query) < 2:
        return jsonify({'results': [], 'total': 0, 'page': page, 'per_page': per_page})
    
    # Create cache key
    cache_key = f"search:{hashlib.md5(query.encode()).hexdigest()}:{page}:{per_page}"
    
    # Try cache first
    cached_result = cache.get(cache_key)
    if cached_result:
        logger.info(f"Search cache hit for: {query}")
        return jsonify(cached_result)
    
    try:
        # Search with pagination
        search_query = BookData.query.filter(
            or_(
                BookData.title.ilike(f"%{query}%"),
                BookData.author.ilike(f"%{query}%"),
                BookData.publisher.ilike(f"%{query}%")
            )
        ).order_by(BookData.updated_at.desc())
        
        total = search_query.count()
        books = search_query.offset((page-1) * per_page).limit(per_page).all()
        
        results = [book.to_dict() for book in books]
        
        result_data = {
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, result_data, timeout=300)
        
        logger.info(f"Search completed: '{query}' - {len(results)} results (page {page})")
        return jsonify(result_data)
        
    except Exception as e:
        logger.error(f"Search error for '{query}': {e}")
        return jsonify({'status': 'error', 'message': 'Search failed'}), 500

@app.route('/stats', methods=['GET'])
@handle_errors
@rate_limit("20 per minute")
def stats():
    """Enhanced statistics with caching and additional metrics."""
    
    # Try cache first
    cached_stats = cache.get('stats')
    if cached_stats:
        return jsonify(cached_stats)
    
    try:
        # Use raw SQL for better performance
        stats_query = text("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN files_url_drive IS NOT NULL AND files_url_drive != '' THEN 1 END) as uploaded,
                COUNT(CASE WHEN cover_url_final IS NOT NULL AND cover_url_final != '' THEN 1 END) as cover,
                COUNT(CASE WHEN download_status = 'done' THEN 1 END) as downloaded,
                COUNT(CASE WHEN download_status = 'failed' THEN 1 END) as failed,
                COUNT(CASE WHEN download_status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN download_status = 'in_progress' THEN 1 END) as in_progress
            FROM book_data
        """)
        
        result = db.session.execute(stats_query).fetchone()
        
        stats_data = {
            'total': result.total,
            'uploaded': result.uploaded,
            'cover': result.cover,
            'downloaded': result.downloaded,
            'failed': result.failed,
            'pending': result.pending,
            'in_progress': result.in_progress,
            'upload_rate': round((result.uploaded / max(result.total, 1)) * 100, 2),
            'download_rate': round((result.downloaded / max(result.total, 1)) * 100, 2),
            'last_updated': datetime.utcnow().isoformat()
        }
        
        # Cache for 1 minute
        cache.set('stats', stats_data, timeout=60)
        
        return jsonify(stats_data)
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'status': 'error', 'message': 'Stats unavailable'}), 500

@app.route('/get_direct_link/<book_id>', methods=['GET'])
@handle_errors
@rate_limit("50 per minute")
def get_direct_link(book_id):
    """Ambil direct link download file dari files_url_drive."""
    book = BookData.query.get(book_id)
    if not book or not book.files_url_drive:
        return jsonify({'status': 'error', 'message': 'File tidak ditemukan'}), 404
    # Asumsi files_url_drive adalah link direct download Google Drive
    return jsonify({'status': 'ok', 'direct_link': book.files_url_drive})

@app.route('/book_detail/<book_id>', methods=['GET'])
@handle_errors
@rate_limit("50 per minute")
def book_detail(book_id):
    """Ambil detail lengkap buku."""
    book = BookData.query.get(book_id)
    if not book:
        return jsonify({'status': 'error', 'message': 'Buku tidak ditemukan'}), 404
    return jsonify({
        'id': book.id,
        'title': book.title,
        'author': book.author,
        'publisher': book.publisher,
        'year': book.year,
        'language': book.language,
        'extension': book.extension,
        'filesize': book.filesize,
        'book_url': book.book_url,
        'cover_image_url': book.cover_image_url,
        'source_type': book.source_type,
        'cover_url_final': book.cover_url_final,
        'files_url_drive': book.files_url_drive,
        'download_status': book.download_status,
    })

@app.route('/bookmark', methods=['GET', 'POST'])
@handle_errors
@rate_limit("100 per minute")
def bookmark():
    """Enhanced bookmark management with validation and caching."""
    if request.method == 'POST':
        data = request.get_json() or {}
        user_id = str(data.get('user_id', '')).strip()
        book_ids = data.get('book_ids', [])
        
        # Enhanced validation
        if not user_id or len(user_id) > 20:
            return jsonify({'status': 'error', 'message': 'Invalid user_id'}), 400
        if not book_ids or len(book_ids) > 100:  # Limit bookmark batch size
            return jsonify({'status': 'error', 'message': 'Invalid book_ids'}), 400
        
        try:
            bookmarks = load_bookmarks()
            current_bookmarks = bookmarks.get(user_id, [])
            
            # Validate book_ids exist in database
            valid_books = BookData.query.filter(BookData.id.in_(book_ids)).all()
            valid_book_ids = [book.id for book in valid_books]
            
            # Update bookmarks with only valid book IDs
            updated_bookmarks = list(set(current_bookmarks + valid_book_ids))
            bookmarks[user_id] = updated_bookmarks
            
            save_bookmarks(bookmarks)
            
            # Invalidate cache
            cache.delete(f"bookmarks:{user_id}")
            
            logger.info(f"Updated bookmarks for user {user_id}: {len(updated_bookmarks)} books")
            
            return jsonify({
                'status': 'ok', 
                'bookmarks': updated_bookmarks,
                'added': len(valid_book_ids),
                'invalid': len(book_ids) - len(valid_book_ids)
            })
            
        except Exception as e:
            logger.error(f"Bookmark save error for user {user_id}: {e}")
            return jsonify({'status': 'error', 'message': 'Failed to save bookmarks'}), 500
    
    else:
        # GET bookmarks
        user_id = request.args.get('user_id', '').strip()
        if not user_id or len(user_id) > 20:
            return jsonify({'status': 'error', 'message': 'Invalid user_id'}), 400
        
        # Try cache first
        cache_key = f"bookmarks:{user_id}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return jsonify(cached_result)
        
        try:
            bookmarks = load_bookmarks().get(user_id, [])
            
            if not bookmarks:
                return jsonify({'results': [], 'total': 0})
            
            # Get book details
            books = BookData.query.filter(BookData.id.in_(bookmarks)).all()
            
            result = []
            for b in books:
                result.append({
                    'id': b.id,
                    'title': b.title,
                    'author': b.author,
                    'publisher': b.publisher,
                    'book_url': b.book_url,
                    'extension': b.extension,
                    'files_url_drive': b.files_url_drive,
                    'download_status': b.download_status
                })
            
            response_data = {'results': result, 'total': len(result)}
            
            # Cache for 5 minutes
            cache.set(cache_key, response_data, timeout=300)
            
            return jsonify(response_data)
            
        except Exception as e:
            logger.error(f"Bookmark load error for user {user_id}: {e}")
            return jsonify({'status': 'error', 'message': 'Failed to load bookmarks'}), 500

# Enhanced Health Check and Metrics Endpoints
@app.route('/')
@handle_errors
def home():
    """Enhanced health check with system status."""
    try:
        # Quick database health check
        db.session.execute(text('SELECT 1')).fetchone()
        db_status = "✅ Connected"
    except Exception as e:
        db_status = f"❌ Error: {str(e)[:50]}"
    
    # Cache health check
    try:
        cache.set('health_check', 'ok', timeout=5)
        cache_status = "✅ Working" if cache.get('health_check') == 'ok' else "❌ Failed"
    except Exception:
        cache_status = "❌ Error"
    
    return jsonify({
        "status": "✅ API Receiver is running",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "cache": cache_status,
        "version": "2.0-Enhanced"
    })

@app.route('/health', methods=['GET'])
@handle_errors
def health_check():
    """Detailed health check for monitoring."""
    try:
        # Database check
        start_time = time.time()
        result = db.session.execute(text('SELECT COUNT(*) FROM book_data')).fetchone()
        db_response_time = time.time() - start_time
        
        # Cache check
        start_time = time.time()
        cache.set('health_test', 'test_value', timeout=5)
        cache_test = cache.get('health_test')
        cache_response_time = time.time() - start_time
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": {
                    "status": "ok",
                    "response_time_ms": round(db_response_time * 1000, 2),
                    "total_books": result[0] if result else 0
                },
                "cache": {
                    "status": "ok" if cache_test == 'test_value' else "error",
                    "response_time_ms": round(cache_response_time * 1000, 2)
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }), 500

@app.route('/metrics', methods=['GET'])
@handle_errors
@rate_limit("10 per minute")
def metrics():
    """System metrics for monitoring."""
    try:
        # Database metrics
        metrics_query = text("""
            SELECT 
                download_status,
                COUNT(*) as count
            FROM book_data 
            GROUP BY download_status
        """)
        
        status_counts = {}
        for row in db.session.execute(metrics_query):
            status_counts[row.download_status] = row.count
        
        return jsonify({
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "status_distribution": status_counts,
                "total_books": sum(status_counts.values())
            },
            "api": {
                "rate_limits_active": limiter is not None,
                "cache_active": cache is not None
            }
        })
        
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        return jsonify({"status": "error", "message": "Metrics unavailable"}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'status': 'error', 'message': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

# Startup initialization
def initialize_app():
    """Initialize application with enhanced setup."""
    os.makedirs('logs', exist_ok=True)
    
    with app.app_context():
        try:
            db.create_all()
            logger.info("✅ Database tables checked/created successfully")
            
            # Test database connection
            db.session.execute(text('SELECT 1')).fetchone()
            logger.info("✅ Database connection verified")
            
            # Test cache
            if cache:
                cache.set('startup_test', 'ok', timeout=5)
                if cache.get('startup_test') == 'ok':
                    logger.info("✅ Cache system verified")
                else:
                    logger.warning("⚠️ Cache test failed")
            
            # Test rate limiter
            if limiter:
                logger.info("✅ Rate limiter active")
            else:
                logger.warning("⚠️ Rate limiter disabled")
                
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            raise

if __name__ == '__main__':
    initialize_app()
    
    # Enhanced server configuration
    app.run(
        host='0.0.0.0', 
        port=int(os.getenv('PORT', 8080)),
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        threaded=True
    )