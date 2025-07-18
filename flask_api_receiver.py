from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from sqlalchemy import or_
import json
BOOKMARK_DB_PATH = 'bookmark_db.json'

def load_bookmarks():
    if not os.path.exists(BOOKMARK_DB_PATH):
        return {}
    with open(BOOKMARK_DB_PATH, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def save_bookmarks(data):
    with open(BOOKMARK_DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

app = Flask(__name__)

# Gunakan DATABASE_URL dari Railway (via ENV)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class BookData(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    title = db.Column(db.String(255))
    author = db.Column(db.String(255))
    year = db.Column(db.String(16))
    publisher = db.Column(db.String(255))
    language = db.Column(db.String(64))
    extension = db.Column(db.String(16))
    filesize = db.Column(db.String(32))
    book_url = db.Column(db.String(512))
    cover_image_url = db.Column(db.String(512))
    source_type = db.Column(db.String(64))
    cover_url_final = db.Column(db.String(512))
    files_url_drive = db.Column(db.String(512))
    download_status = db.Column(db.String(32), default='pending')
    claimed_by = db.Column(db.String(64), nullable=True)

@app.route('/upload_data', methods=['POST'])
def upload_data():
    """Insert/update book data (batch or single)."""
    data = request.get_json()
    results = []
    if isinstance(data, list):
        for item in data:
            if not item or not item.get('id'):
                results.append({'status': 'error', 'message': 'Missing ID'})
                continue
            try:
                book = BookData.query.get(item['id'])
                if book:
                    for k, v in item.items():
                        setattr(book, k, v)
                    db.session.commit()
                    results.append({'status': 'updated'})
                else:
                    book = BookData(**item)
                    db.session.add(book)
                    db.session.commit()
                    results.append({'status': 'inserted'})
            except Exception as e:
                db.session.rollback()
                results.append({'status': 'error', 'message': str(e)})
        return jsonify(results)
    else:
        if not data or not data.get('id'):
            return jsonify({'status': 'error', 'message': 'Missing ID'}), 400
        try:
            book = BookData.query.get(data['id'])
            if book:
                for k, v in data.items():
                    setattr(book, k, v)
                db.session.commit()
                return jsonify({'status': 'updated'})
            else:
                book = BookData(**data)
                db.session.add(book)
                db.session.commit()
                return jsonify({'status': 'inserted'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/claim_books', methods=['POST'])
def claim_books():
    """Claim batch buku untuk download (atomic)."""
    req_json = request.get_json() or {}
    batch_size = int(req_json.get('batch_size', 5))
    instance_id = req_json.get('instance_id', 'instance')
    with db.session.begin_nested():
        books = BookData.query.filter_by(download_status='pending').limit(batch_size).with_for_update().all()
        for book in books:
            book.download_status = 'in_progress'
            book.claimed_by = instance_id
        db.session.commit()
    return jsonify([{
        'id': b.id,
        'title': b.title,
        'author': b.author,
        'publisher': b.publisher,
        'book_url': b.book_url,
        'extension': b.extension,
        'files_url_drive': b.files_url_drive,
    } for b in books])

@app.route('/reset_inprogress', methods=['POST'])
def reset_inprogress():
    """Reset status in_progress/failed ke pending."""
    data = request.get_json() or {}
    instance_id = data.get('instance_id')
    reset_failed = data.get('reset_failed', False)
    query = BookData.query
    if instance_id:
        query = query.filter_by(claimed_by=instance_id)
    if reset_failed:
        books = query.filter(BookData.download_status.in_(['in_progress', 'failed'])).all()
    else:
        books = query.filter_by(download_status='in_progress').all()
    count = 0
    for book in books:
        book.download_status = 'pending'
        book.claimed_by = None
        count += 1
    db.session.commit()
    return jsonify({'status': 'success', 'reset_count': count})

@app.route('/get_ready_for_upload', methods=['GET'])
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
def claim_upload_batch():
    """Claim batch buku siap upload (atomic)."""
    data = request.get_json() or {}
    batch_size = int(data.get('batch_size', 10))
    instance_id = data.get('instance_id', 'uploader')
    with db.session.begin_nested():
        books = BookData.query.filter(
            BookData.download_status == 'done',
            (BookData.files_url_drive == None) | (BookData.files_url_drive == ''),
            (BookData.claimed_by == None) | (BookData.claimed_by == '')
        ).limit(batch_size).with_for_update().all()
        for book in books:
            book.claimed_by = instance_id
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

@app.route('/search_books', methods=['GET'])
def search_books():
    """Search buku by judul/author/publisher (max 50)."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    books = BookData.query.filter(
        or_(
            BookData.title.ilike(f"%{query}%"),
            BookData.author.ilike(f"%{query}%"),
            BookData.publisher.ilike(f"%{query}%")
        )
    ).limit(50).all()
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
        })
    return jsonify(result)

@app.route('/stats', methods=['GET'])
def stats():
    """Statistik buku (total, uploaded, cover, downloaded, failed)."""
    total = BookData.query.count()
    uploaded = BookData.query.filter(BookData.files_url_drive != None, BookData.files_url_drive != '').count()
    cover = BookData.query.filter(BookData.cover_url_final != None, BookData.cover_url_final != '').count()
    downloaded = BookData.query.filter(BookData.download_status == 'done').count()
    failed = BookData.query.filter(BookData.download_status == 'failed').count()
    return jsonify({
        'total': total,
        'uploaded': uploaded,
        'cover': cover,
        'downloaded': downloaded,
        'failed': failed
    })

@app.route('/get_direct_link/<book_id>', methods=['GET'])
def get_direct_link(book_id):
    """Ambil direct link download file dari files_url_drive."""
    book = BookData.query.get(book_id)
    if not book or not book.files_url_drive:
        return jsonify({'status': 'error', 'message': 'File tidak ditemukan'}), 404
    # Asumsi files_url_drive adalah link direct download Google Drive
    return jsonify({'status': 'ok', 'direct_link': book.files_url_drive})

@app.route('/book_detail/<book_id>', methods=['GET'])
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
def bookmark():
    """Ambil/tambah bookmark per user (user_id Telegram)."""
    if request.method == 'POST':
        data = request.get_json() or {}
        user_id = str(data.get('user_id'))
        book_ids = data.get('book_ids', [])
        if not user_id or not book_ids:
            return jsonify({'status': 'error', 'message': 'user_id dan book_ids wajib'}), 400
        bookmarks = load_bookmarks()
        bookmarks[user_id] = list(set(bookmarks.get(user_id, []) + book_ids))
        save_bookmarks(bookmarks)
        return jsonify({'status': 'ok', 'bookmarks': bookmarks[user_id]})
    else:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id wajib'}), 400
        bookmarks = load_bookmarks().get(str(user_id), [])
        # Ambil detail buku
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
            })
        return jsonify(result)

@app.route('/')
def home():
    return "✅ API Receiver is running."

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("[INFO] BookData table checked/created.")
    app.run(host='0.0.0.0', port=8080)