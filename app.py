import os
import uuid
import boto3
from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from datetime import timedelta
from botocore.client import Config
from werkzeug.utils import secure_filename

# ── App Setup ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR)

app.config['SQLALCHEMY_DATABASE_URI']    = os.environ.get('DATABASE_URL', 'sqlite:///bookvault.db').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY']             = os.environ.get('JWT_SECRET', 'change-me-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES']   = timedelta(days=7)
app.config['MAX_CONTENT_LENGTH']         = 200 * 1024 * 1024  # 200 MB upload limit

db     = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt    = JWTManager(app)

# ── Backblaze B2 (S3-compatible) ───────────────────────────
B2_KEY_ID      = os.environ.get('B2_KEY_ID', '')
B2_APP_KEY     = os.environ.get('B2_APP_KEY', '')
B2_BUCKET_NAME = os.environ.get('B2_BUCKET_NAME', '')
B2_ENDPOINT    = os.environ.get('B2_ENDPOINT', '')

def get_b2_client():
    return boto3.client(
        's3',
        endpoint_url=B2_ENDPOINT,
        aws_access_key_id=B2_KEY_ID,
        aws_secret_access_key=B2_APP_KEY,
        config=Config(signature_version='s3v4'),
    )

# ── Models ─────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'users'
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(120), nullable=False)
    email    = db.Column(db.String(200), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    tier     = db.Column(db.Integer, default=0)   # 0=free, 1=Reader $10, 2=Scholar $20
    is_admin = db.Column(db.Boolean, default=False)

class Book(db.Model):
    __tablename__ = 'books'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(300), nullable=False)
    author      = db.Column(db.String(200), nullable=False)
    genre       = db.Column(db.String(100))
    year        = db.Column(db.Integer)
    color       = db.Column(db.String(20), default='#1a3a5c')
    description = db.Column(db.Text)
    file_key    = db.Column(db.String(500))
    file_name   = db.Column(db.String(300))

# ── DB Init + seed ─────────────────────────────────────────
def init_db():
    db.create_all()
    if not User.query.filter_by(email='admin@bookvault.com').first():
        admin = User(
            name='Admin',
            email='admin@bookvault.com',
            password=bcrypt.generate_password_hash('admin1').decode(),
            tier=0,
            is_admin=True
        )
        db.session.add(admin)

    if Book.query.count() == 0:
        seeds = [
            Book(title='The Great Gatsby',  author='F. Scott Fitzgerald', genre='Classic Literature', year=1925, color='#1a3a5c', description='A story of wealth, obsession, and the American Dream in the 1920s.'),
            Book(title='1984',              author='George Orwell',       genre='Science Fiction',    year=1949, color='#2a2a2a', description='A chilling dystopia where Big Brother watches your every move.'),
            Book(title='Dune',              author='Frank Herbert',       genre='Science Fiction',    year=1965, color='#7a4a00', description='Epic science fiction set on a desert planet.'),
            Book(title='Pride & Prejudice', author='Jane Austen',         genre='Classic Literature', year=1813, color='#5c1a1a', description='A timeless tale of love, manners, and marriage in Georgian England.'),
            Book(title='The Alchemist',     author='Paulo Coelho',        genre='Philosophy',         year=1988, color='#1a5c2a', description='A mystical journey of self-discovery.'),
            Book(title='Sapiens',           author='Yuval Noah Harari',   genre='History',            year=2011, color='#3a3a3a', description='A brief history of humankind.'),
            Book(title='The Hobbit',        author='J.R.R. Tolkien',      genre='Fantasy',            year=1937, color='#2a5c1a', description='A humble hobbit swept into an unexpected journey.'),
            Book(title='Gone Girl',         author='Gillian Flynn',       genre='Thriller',           year=2012, color='#1a0a0a', description='A twisting psychological thriller about marriage and deception.'),
            Book(title='Atomic Habits',     author='James Clear',         genre='Self-Help',          year=2018, color='#1a3a5c', description='Proven strategies for building good habits.'),
            Book(title='Moby Dick',         author='Herman Melville',     genre='Classic Literature', year=1851, color='#001a3a', description="Captain Ahab's obsessive quest to hunt the great white whale."),
            Book(title='The Road',          author='Cormac McCarthy',     genre='Thriller',           year=2006, color='#1a1a1a', description='A harrowing post-apocalyptic journey.'),
            Book(title='Educated',          author='Tara Westover',       genre='Biography',          year=2018, color='#3a1a5c', description='A remarkable memoir about escaping a survivalist family.'),
        ]
        db.session.add_all(seeds)

    db.session.commit()

with app.app_context():
    init_db()

# ── Helper ─────────────────────────────────────────────────
ALLOWED_EXT = {'pdf', 'epub', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

# ── Serve Frontend ─────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

# ══════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════

@app.route('/api/auth/login', methods=['POST'])
def login():
    data     = request.get_json()
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '')

    if username == 'admin' and password == 'admin1':
        admin = User.query.filter_by(is_admin=True).first()
        if admin:
            token = create_access_token(identity=str(admin.id))
            return jsonify({'token': token, 'name': admin.name, 'tier': admin.tier, 'is_admin': True})

    user = User.query.filter_by(email=username).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({'token': token, 'name': user.name, 'tier': user.tier, 'is_admin': user.is_admin})


@app.route('/api/auth/register', methods=['POST'])
def register():
    data  = request.get_json()
    name  = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    pw    = (data.get('password') or '')
    tier  = int(data.get('tier', 1))

    if not name or not email or len(pw) < 4:
        return jsonify({'error': 'Name, email and password (min 4 chars) required'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    user = User(name=name, email=email, password=bcrypt.generate_password_hash(pw).decode(), tier=tier)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({'token': token, 'name': user.name, 'tier': user.tier, 'is_admin': False}), 201


@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def me():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'name': user.name, 'tier': user.tier, 'is_admin': user.is_admin})

# ══════════════════════════════════════════════════════════
#  BOOK ROUTES
# ══════════════════════════════════════════════════════════

@app.route('/api/books', methods=['GET'])
def list_books():
    books = Book.query.order_by(Book.id.asc()).all()
    return jsonify([{
        'id': b.id, 'title': b.title, 'author': b.author,
        'genre': b.genre, 'year': b.year, 'color': b.color,
        'description': b.description, 'has_file': bool(b.file_key)
    } for b in books])


@app.route('/api/books/<int:book_id>/read', methods=['GET'])
@jwt_required()
def read_book(book_id):
    user = User.query.get(int(get_jwt_identity()))
    if not user or user.tier < 1:
        return jsonify({'error': 'Subscription required'}), 403
    book = Book.query.get_or_404(book_id)
    return jsonify({
        'id': book.id, 'title': book.title, 'author': book.author,
        'genre': book.genre, 'year': book.year,
        'description': book.description, 'has_file': bool(book.file_key)
    })


@app.route('/api/books/<int:book_id>/download', methods=['GET'])
@jwt_required()
def download_book(book_id):
    user = User.query.get(int(get_jwt_identity()))
    if not user or user.tier < 2:
        return jsonify({'error': 'Scholar plan required to download'}), 403
    book = Book.query.get_or_404(book_id)
    if not book.file_key:
        return jsonify({'error': 'No file uploaded for this book'}), 404
    try:
        b2  = get_b2_client()
        url = b2.generate_presigned_url(
            'get_object',
            Params={'Bucket': B2_BUCKET_NAME, 'Key': book.file_key,
                    'ResponseContentDisposition': f'attachment; filename="{book.file_name}"'},
            ExpiresIn=300
        )
        return jsonify({'url': url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ══════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ══════════════════════════════════════════════════════════

def require_admin():
    user = User.query.get(int(get_jwt_identity()))
    if not user or not user.is_admin:
        return None, (jsonify({'error': 'Admin only'}), 403)
    return user, None


@app.route('/api/admin/books', methods=['POST'])
@jwt_required()
def admin_upload_book():
    _, err = require_admin()
    if err: return err

    title  = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    if not title or not author:
        return jsonify({'error': 'Title and author required'}), 400

    genre     = request.form.get('genre', '')
    year      = request.form.get('year', '')
    color     = request.form.get('color', '#1a3a5c')
    desc      = request.form.get('description', '')
    file_key  = None
    file_name = None

    if 'file' in request.files:
        f = request.files['file']
        if f and f.filename and allowed_file(f.filename):
            original  = secure_filename(f.filename)
            file_key  = f'books/{uuid.uuid4().hex}/{original}'
            file_name = original
            try:
                b2 = get_b2_client()
                b2.upload_fileobj(f, B2_BUCKET_NAME, file_key)
            except Exception as e:
                return jsonify({'error': f'B2 upload failed: {e}'}), 500

    book = Book(
        title=title, author=author, genre=genre,
        year=int(year) if year.isdigit() else None,
        color=color, description=desc,
        file_key=file_key, file_name=file_name
    )
    db.session.add(book)
    db.session.commit()
    return jsonify({'id': book.id, 'title': book.title}), 201


@app.route('/api/admin/books/<int:book_id>', methods=['DELETE'])
@jwt_required()
def admin_delete_book(book_id):
    _, err = require_admin()
    if err: return err

    book = Book.query.get_or_404(book_id)
    if book.file_key:
        try:
            b2 = get_b2_client()
            b2.delete_object(Bucket=B2_BUCKET_NAME, Key=book.file_key)
        except Exception:
            pass

    db.session.delete(book)
    db.session.commit()
    return jsonify({'deleted': book_id})


@app.route('/api/admin/stats', methods=['GET'])
@jwt_required()
def admin_stats():
    _, err = require_admin()
    if err: return err

    tier1   = User.query.filter_by(tier=1).count()
    tier2   = User.query.filter_by(tier=2).count()
    return jsonify({
        'total_books':     Book.query.count(),
        'total_users':     User.query.filter_by(is_admin=False).count(),
        'tier1_users':     tier1,
        'tier2_users':     tier2,
        'monthly_revenue': (tier1 * 10) + (tier2 * 20)
    })


@app.route('/api/admin/users', methods=['GET'])
@jwt_required()
def admin_users():
    _, err = require_admin()
    if err: return err

    users = User.query.filter_by(is_admin=False).order_by(User.id.desc()).all()
    return jsonify([{'id': u.id, 'name': u.name, 'email': u.email, 'tier': u.tier} for u in users])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
