import os
import sqlite3
import json
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- CONFIGURATION ---
UPLOAD_FOLDER = 'uploads'
DATABASE = 'data.db'
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv'}
ADMIN_PASSWORD = "admin786"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- DATABASE LOGIC ---
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        # Table for Categories
        conn.execute('CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)')
        # Table for Videos with views and category
        conn.execute('''CREATE TABLE IF NOT EXISTS videos 
                        (id TEXT PRIMARY KEY, filename TEXT, title TEXT, category_id INTEGER, views INTEGER DEFAULT 0)''')
        # Table for Likes
        conn.execute('CREATE TABLE IF NOT EXISTS likes (video_id TEXT, user_id TEXT, UNIQUE(video_id, user_id))')
        conn.commit()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- HTML COMPONENTS (CSS & NAV) ---

COMMON_STYLE = """
<style>
    body, html { margin: 0; padding: 0; background: #000; color: white; font-family: -apple-system, sans-serif; height: 100%; overflow-x: hidden; }
    .nav-bar { position: fixed; bottom: 0; width: 100%; background: rgba(0,0,0,0.9); display: flex; justify-content: space-around; align-items: center; height: 65px; border-top: 0.5px solid #333; z-index: 1000; backdrop-filter: blur(10px); }
    .nav-item { color: #888; text-decoration: none; display: flex; flex-direction: column; align-items: center; font-size: 10px; gap: 4px; }
    .nav-item.active { color: white; }
    .nav-icon { font-size: 24px; }
    .user-logo { width: 30px; height: 30px; border-radius: 50%; background: #ff3b30; color: white; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px; text-transform: uppercase; }
    .container { padding: 15px; padding-bottom: 80px; }
    .video-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }
    .video-item { background: #111; border-radius: 10px; overflow: hidden; position: relative; aspect-ratio: 9/16; }
    .video-item video { width: 100%; height: 100%; object-fit: cover; }
    .video-stats { position: absolute; bottom: 5px; left: 8px; font-size: 11px; text-shadow: 1px 1px 2px #000; }
    .category-bar { display: flex; overflow-x: auto; gap: 10px; padding: 10px 0; scrollbar-width: none; }
    .category-bar::-webkit-scrollbar { display: none; }
    .cat-pill { padding: 6px 15px; background: #222; border-radius: 20px; font-size: 13px; white-space: nowrap; text-decoration: none; color: #aaa; }
    .cat-pill.active { background: #fff; color: #000; }
    .hot-section { margin-bottom: 25px; }
    .hot-scroll { display: flex; overflow-x: auto; gap: 15px; scrollbar-width: none; }
    .hot-item { min-width: 140px; aspect-ratio: 9/16; background: #222; border-radius: 12px; overflow: hidden; position: relative; border: 1px solid #ff3b30; }
    .hot-item video { width: 100%; height: 100%; object-fit: cover; }
    .section-title { font-size: 18px; font-weight: bold; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
    .admin-btn { position: fixed; top: 20px; right: 20px; background: rgba(255,255,255,0.1); padding: 8px; border-radius: 8px; z-index: 1001; text-decoration: none; color: white; font-size: 20px; }
</style>
"""

NAV_HTML = """
<div class="nav-bar">
    <a href="/" class="nav-item {{ 'active' if page == 'home' else '' }}">
        <span class="nav-icon">🏠</span>
        <span>Home</span>
    </a>
    <a href="/reels" class="nav-item {{ 'active' if page == 'reels' else '' }}">
        <span class="nav-icon">🎬</span>
        <span>Clips</span>
    </a>
    <div class="nav-item">
        <div class="user-logo" id="userInitial">?</div>
        <span>Profile</span>
    </div>
</div>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>
    const tg = window.Telegram.WebApp;
    tg.ready();
    const firstName = tg.initDataUnsafe?.user?.first_name || "Guest";
    document.getElementById('userInitial').innerText = firstName[0];
</script>
"""

# --- ROUTES ---

@app.route('/')
def home():
    cat_id = request.args.get('cat', type=int)
    with get_db() as conn:
        categories = conn.execute('SELECT * FROM categories').fetchall()
        
        # Hot Clips (Order by views + likes)
        hot_clips = conn.execute('''SELECT v.*, (SELECT COUNT(*) FROM likes WHERE video_id = v.id) as likes 
                                    FROM videos v ORDER BY (views + likes) DESC LIMIT 5''').fetchall()
        
        # Main Feed
        query = 'SELECT v.*, (SELECT COUNT(*) FROM likes WHERE video_id = v.id) as likes FROM videos v'
        params = []
        if cat_id:
            query += ' WHERE category_id = ?'
            params.append(cat_id)
        query += ' ORDER BY id DESC'
        videos = conn.execute(query, params).fetchall()

    return render_template_string(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Home</title>
            {COMMON_STYLE}
        </head>
        <body>
            <a href="/settings" class="admin-btn">⚙️</a>
            <div class="container">
                <div class="section-title">🔥 Hot Clips</div>
                <div class="hot-scroll">
                    {% for v in hot_clips %}
                    <a href="/reels?start={{ v.id }}" class="hot-item">
                        <video src="/uploads/{{ v.filename }}" muted></video>
                        <div class="video-stats">👁️ {{ v.views }}</div>
                    </a>
                    {% endfor %}
                </div>

                <div class="category-bar">
                    <a href="/" class="cat-pill {{ 'active' if not selected_cat else '' }}">All</a>
                    {% for cat in categories %}
                    <a href="/?cat={{ cat.id }}" class="cat-pill {{ 'active' if selected_cat == cat.id else '' }}">{{ cat.name }}</a>
                    {% endfor %}
                </div>

                <div class="video-grid">
                    {% for v in videos %}
                    <a href="/reels?start={{ v.id }}" class="video-item">
                        <video src="/uploads/{{ v.filename }}" muted></video>
                        <div class="video-stats">👁️ {{ v.views }} • ❤️ {{ v.likes }}</div>
                    </a>
                    {% endfor %}
                </div>
            </div>
            {{ nav | safe }}
        </body>
        </html>
    """, hot_clips=hot_clips, categories=categories, videos=videos, selected_cat=cat_id, nav=render_template_string(NAV_HTML, page='home'))

@app.route('/reels')
def reels():
    start_id = request.args.get('start')
    with get_db() as conn:
        videos = conn.execute('SELECT v.*, (SELECT COUNT(*) FROM likes WHERE video_id = v.id) as likes FROM videos v ORDER BY id DESC').fetchall()
    
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
            {style}
            <style>
                .reels-container { height: 100vh; overflow-y: scroll; scroll-snap-type: y mandatory; }
                .reel-card { height: 100vh; scroll-snap-align: start; position: relative; }
                video { width: 100%; height: 100%; object-fit: cover; }
                .reel-info { position: absolute; bottom: 100px; left: 20px; z-index: 10; pointer-events: none; }
            </style>
        </head>
        <body>
            <div class="reels-container">
                {% for v in videos %}
                <div class="reel-card" data-id="{{ v.id }}">
                    <video loop playsinline onclick="togglePlay(this)">
                        <source src="/uploads/{{ v.filename }}" type="video/mp4">
                    </video>
                    <div class="reel-info">
                        <h3>@Admin</h3>
                        <p>{{ v.title }}</p>
                        <small>👁️ {{ v.views }} views</small>
                    </div>
                </div>
                {% endfor %}
            </div>
            {{ nav | safe }}
            <script>
                function togglePlay(v) { v.paused ? v.play() : v.pause(); }
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            const v = entry.target.querySelector('video');
                            v.play();
                            // Increment View
                            fetch('/api/view/' + entry.target.dataset.id, {method:'POST'});
                        } else {
                            entry.target.querySelector('video').pause();
                        }
                    });
                }, { threshold: 0.7 });
                document.querySelectorAll('.reel-card').forEach(c => observer.observe(c));
            </script>
        </body>
        </html>
    """.format(style=COMMON_STYLE, nav=render_template_string(NAV_HTML, page='reels')), videos=videos)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    # Simple Admin Check
    error = None
    if request.method == 'POST':
        pw = request.form.get('password')
        if pw != ADMIN_PASSWORD:
            error = "Wrong Password"
        else:
            action = request.form.get('action')
            if action == 'add_cat':
                name = request.form.get('name')
                with get_db() as conn:
                    conn.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (name,))
                    conn.commit()
            return redirect('/settings')
            
    with get_db() as conn:
        categories = conn.execute('SELECT * FROM categories').fetchall()
    
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1.0">{style}</head>
        <body style="padding: 20px;">
            <h2>⚙️ Admin Settings</h2>
            <form method="POST">
                <input type="password" name="password" placeholder="Admin Password" required style="width:100%; padding:10px; margin-bottom:10px; background:#222; color:#fff; border:none;">
                <input type="hidden" name="action" value="add_cat">
                <input type="text" name="name" placeholder="New Category Name" required style="width:100%; padding:10px; background:#222; color:#fff; border:none;">
                <button type="submit" style="width:100%; padding:10px; background:#0088cc; color:#fff; border:none; margin-top:10px;">Add Category</button>
            </form>
            <hr>
            <a href="/upload" style="display:block; padding:15px; background:#222; color:#fff; text-decoration:none; text-align:center; border-radius:10px;">⬆️ Upload Video</a>
            <br>
            <a href="/" style="color:#aaa;">← Back to App</a>
        </body>
        </html>
    """.format(style=COMMON_STYLE), categories=categories)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                vid_id = str(hash(filename))
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                with get_db() as conn:
                    conn.execute('INSERT INTO videos (id, filename, title, category_id) VALUES (?, ?, ?, ?)',
                                (vid_id, filename, filename, request.form.get('category')))
                    conn.commit()
                return redirect('/')
    
    with get_db() as conn:
        categories = conn.execute('SELECT * FROM categories').fetchall()
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1.0">{style}</head>
        <body style="padding: 20px;">
            <h2>Upload Video</h2>
            <form method="POST" enctype="multipart/form-data">
                <input type="password" name="password" placeholder="Admin Password" required style="width:100%; padding:10px; margin-bottom:10px; background:#222; color:#fff; border:none;">
                <select name="category" style="width:100%; padding:10px; margin-bottom:10px; background:#222; color:#fff; border:none;">
                    {% for cat in categories %}
                    <option value="{{ cat.id }}">{{ cat.name }}</option>
                    {% endfor %}
                </select>
                <input type="file" name="file" required style="margin-bottom:20px;">
                <button type="submit" style="width:100%; padding:10px; background:#0088cc; color:#fff; border:none;">Upload</button>
            </form>
        </body>
        </html>
    """.format(style=COMMON_STYLE), categories=categories)

@app.route('/api/view/<vid>', methods=['POST'])
def add_view(vid):
    with get_db() as conn:
        conn.execute('UPDATE videos SET views = views + 1 WHERE id = ?', (vid,))
        conn.commit()
    return jsonify({"status": "ok"})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860, debug=True)
