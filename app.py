# app.py
import os
import sqlite3
import markdown
import json
import re
import uuid
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from dotenv import load_dotenv
import google.generativeai as genai
from flask import make_response

# MoviePy Imports - Including Audio tools
from moviepy.editor import (
    VideoFileClip, 
    AudioFileClip, 
    TextClip, 
    CompositeVideoClip, 
    concatenate_videoclips, 
    concatenate_audioclips
)
from moviepy.config import change_settings

# --- App & Environment Setup ---
app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY", "a_super_secret_default_key")

# --- Configuration ---
# CRITICAL: Use absolute path for uploads
app.config["UPLOAD_FOLDER"] = os.path.abspath("uploads")
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max
app.config['ALLOWED_VIDEO_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv'}
app.config['ALLOWED_AUDIO_EXTENSIONS'] = {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac'}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# --- Optional: ImageMagick Configuration ---
# If TextClip fails on Windows, uncomment and point to your magick.exe
# change_settings({"IMAGEMAGICK_BINARY": r"C:\\Program Files\\ImageMagick-7.1.0-Q16\\magick.exe"})

# --- API Client Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GENAI_AVAILABLE = False

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        GENAI_AVAILABLE = True
        print(f"✅ Gemini Client initialized.")
    except Exception as e:
        print(f"⚠️ ERROR: Failed to configure Gemini: {e}")

# ==========================================
#           DATABASE & AUTH HELPERS
# ==========================================
DATABASE_FILE = "hypeup.db"

def init_db():
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS goals (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            task TEXT NOT NULL, duration TEXT NOT NULL,
                            completed BOOLEAN NOT NULL CHECK (completed IN (0, 1)))''')
        conn.commit()

def create_user_table():
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL)''')
        conn.commit()

def register_user(username, email, password):
    password_hash = generate_password_hash(password)
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            conn.cursor().execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", 
                                (username, email, password_hash))
            conn.commit()
        return True
    except: return False

def validate_user(email, password):
    with sqlite3.connect(DATABASE_FILE) as conn:
        res = conn.cursor().execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()
        if res and check_password_hash(res[0], password): return True
    return False

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session: return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ==========================================
#           FILE & EDITOR HELPERS
# ==========================================

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def generate_unique_filename(original_filename, prefix=''):
    name, ext = os.path.splitext(original_filename)
    clean_name = secure_filename(name)
    unique_id = uuid.uuid4().hex[:8]
    if prefix:
        return f"{prefix}_{clean_name}_{unique_id}{ext}"
    return f"{clean_name}_{unique_id}{ext}"

def safe_float(value, default=0.0):
    try: return float(value)
    except: return default

def get_video_files():
    if not os.path.exists(app.config['UPLOAD_FOLDER']): return []
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    return sorted([f for f in files if allowed_file(f, app.config['ALLOWED_VIDEO_EXTENSIONS'])])

def get_audio_files():
    if not os.path.exists(app.config['UPLOAD_FOLDER']): return []
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    return sorted([f for f in files if allowed_file(f, app.config['ALLOWED_AUDIO_EXTENSIONS'])])

# --- AI Logic Helper ---
def generate_trends_with_gemini(region: str):
    if not GENAI_AVAILABLE: return ["AI Offline"]
    try:
        model = genai.GenerativeModel(DEFAULT_GEMINI_MODEL)
        resp = model.generate_content(f"5 trending search queries for {region}. Plain list.")
        return [l.strip('-• ') for l in resp.text.splitlines() if l.strip()][:5]
    except: return ["Error fetching trends"]

# ==========================================
#               CORE ROUTES
# ==========================================

@app.route("/")
def home(): return redirect(url_for("login"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        if register_user(request.form["username"], request.form["email"], request.form["password"]):
            flash("✅ Account created!", "success")
            return redirect(url_for("login"))
        flash("⚠️ Email taken.", "error")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if validate_user(request.form["email"], request.form["password"]):
            session["user"] = request.form["email"]
            return redirect(url_for("dashboard"))
        flash("❌ Invalid credentials.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Fetch goals
        cursor.execute("SELECT * FROM goals ORDER BY id DESC")
        goals = cursor.fetchall()
        
        # Fetch user info (assuming you want to show their name)
        # We use a safe default "Creator" if session user is missing
        username = session.get("user", "Creator").split('@')[0] 

    # 1. Point to the NEW file (dashboard.html)
    # 2. Pass 'goals' (matches your template) instead of 'reminders'
    return render_template("dashboard.html", goals=goals, username=username)

    

@app.route("/goals", methods=["GET", "POST"])
@login_required
def goals():
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.row_factory = sqlite3.Row
        if request.method == 'POST':
            if request.form.get('task'):
                conn.cursor().execute("INSERT INTO goals (task, duration, completed) VALUES (?, ?, ?)", 
                                    (request.form.get('task'), request.form.get('duration'), 0))
                conn.commit()
            return redirect(url_for('goals'))
        all_goals = conn.cursor().execute("SELECT * FROM goals ORDER BY id DESC").fetchall()
    return render_template("goal.html", goals=all_goals)

@app.route("/delete_goal/<int:goal_id>", methods=["POST"])
@login_required
def delete_goal(goal_id):
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.cursor().execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        conn.commit()
    return redirect(url_for("goals"))

@app.route("/create_post", methods=["GET", "POST"])
@login_required
def create_post():
    ai, html = None, None
    if request.method == "POST" and GENAI_AVAILABLE:
        try:
            model = genai.GenerativeModel(DEFAULT_GEMINI_MODEL)
            resp = model.generate_content(f"Viral {request.form.get('platform')} post about: {request.form.get('content')}")
            ai, html = resp.text, markdown.markdown(resp.text)
        except Exception as e: ai = f"Error: {e}"
    return render_template("create_post.html", ai_generated=html, raw_ai=ai)

# FIXED PROFILE ROUTE - Replace your current /profile route with this

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """User profile and settings page"""
    user_email = session.get("user")  # Session stores email
    
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get user info by EMAIL (not username)
        cursor.execute("SELECT * FROM users WHERE email = ?", (user_email,))
        user = cursor.fetchone()
        
        # Get goals for stats
        cursor.execute("SELECT * FROM goals")
        goals = cursor.fetchall()

    # Handle missing user
    if user is None:
        session.clear()
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("login"))

    # Handle profile updates
    if request.method == "POST":
        new_username = request.form.get("username", "").strip()
        new_email = request.form.get("email", "").strip()
        
        if not new_username or not new_email:
            flash("Username and email are required", "error")
            return redirect(url_for('profile'))
        
        try:
            with sqlite3.connect(DATABASE_FILE) as conn:
                cursor = conn.cursor()
                
                # Check if new email/username is taken by another user
                cursor.execute(
                    "SELECT id FROM users WHERE (username = ? OR email = ?) AND id != ?", 
                    (new_username, new_email, user['id'])
                )
                
                if cursor.fetchone():
                    flash("Username or email already taken", "error")
                else:
                    cursor.execute(
                        "UPDATE users SET username = ?, email = ? WHERE id = ?", 
                        (new_username, new_email, user['id'])
                    )
                    conn.commit()
                    
                    # Update session with new email
                    session["user"] = new_email
                    
                    flash("Profile updated successfully!", "success")
                    return redirect(url_for('profile'))
                    
        except Exception as e:
            flash(f"Error: {str(e)}", "error")

    return render_template("profile.html", user=user, goals=goals)


@app.route("/change_password", methods=["POST"])
@login_required
def change_password():
    """Change user password"""
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    
    if not all([current_password, new_password, confirm_password]):
        flash("All password fields required", "error")
        return redirect(url_for('profile'))
    
    if new_password != confirm_password:
        flash("New passwords do not match", "error")
        return redirect(url_for('profile'))
    
    if len(new_password) < 6:
        flash("Password must be at least 6 characters", "error")
        return redirect(url_for('profile'))
    
    user_email = session.get("user")
    
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE email = ?", (user_email,))
        user_data = cursor.fetchone()
        
        if user_data and check_password_hash(user_data[0], current_password):
            new_hash = generate_password_hash(new_password)
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE email = ?", 
                (new_hash, user_email)
            )
            conn.commit()
            flash("Password changed successfully!", "success")
        else:
            flash("Current password incorrect", "error")
            
    return redirect(url_for('profile'))


@app.route("/delete_account", methods=["POST"])
@login_required  
def delete_account():
    """Delete user account permanently"""
    user_email = session.get("user")
    
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE email = ?", (user_email,))
            conn.commit()
        
        session.clear()
        flash("Your account has been permanently deleted.", "info")
        return redirect(url_for('signup'))
        
    except Exception as e:
        flash(f"Error deleting account: {str(e)}", "error")
        return redirect(url_for('profile'))
@app.route("/export_data")
@login_required
def export_data():
    """Export user data as JSON"""
    user_email = session.get("user")
    
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute("SELECT username, email FROM users WHERE email = ?", (user_email,))
        user = cursor.fetchone()
        
        # Get all goals
        cursor.execute("SELECT task, duration, completed FROM goals")
        goals = [dict(row) for row in cursor.fetchall()]
    
    # Create export data
    from datetime import datetime
    export_data_dict = {
        "exported_at": datetime.now().isoformat(),
        "user": {
            "username": user['username'] if user else "Unknown",
            "email": user['email'] if user else "Unknown"
        },
        "goals": goals,
        "statistics": {
            "total_goals": len(goals),
            "completed_goals": sum(1 for g in goals if g['completed'])
        }
    }
    
    # Create JSON response
    data_json = json.dumps(export_data_dict, indent=2)
    response = make_response(data_json)
    response.headers['Content-Disposition'] = f'attachment; filename=hypeitup_data_{user["username"]}.json'
    response.headers['Content-Type'] = 'application/json'
    
    return response


# @app.route("/meme_templates")
# @login_required
# def meme_templates():
#     memes = []
#     try:
#         r = requests.get("https://api.imgflip.com/get_memes", timeout=5)
#         if r.json().get("success"): memes = r.json()["data"]["memes"][:20]
#     except: pass
#     if not memes: memes = [{"id": "drake", "name": "Drake", "url": "/static/memes/drake.jpg"}]
#     return render_template("meme_templates.html", memes=memes)

# @app.route("/meme_editor/<template_name>")
# @login_required
# def meme_editor(template_name):
#     return render_template("meme_editor.html", meme_name=template_name, meme_url=f"https://i.imgflip.com/{template_name}.jpg")

@app.route("/meme_templates")
@login_required
def meme_templates():
    memes = []

    try:
        response = requests.get("https://api.imgflip.com/get_memes", timeout=5)
        data = response.json()
        if data.get("success"):
            memes = data["data"]["memes"][:20]
    except Exception as e:
        print("⚠️ Could not fetch memes:", e)

    # Local fallback if no internet
    if not memes:
        memes = [
            {"id": "drake", "name": "Drake Hotline Bling", "url": "/static/memes/drake.jpg"},
            {"id": "boyfriend", "name": "Distracted Boyfriend", "url": "/static/memes/distracted_boyfriend.jpg"},
            {"id": "success", "name": "Success Kid", "url": "/static/memes/success_kid.jpg"},
            {"id": "two_buttons", "name": "Two Buttons", "url": "/static/memes/two_buttons.jpg"},
            {"id": "gru_plan", "name": "Gru’s Plan", "url": "/static/memes/gru_plan.jpg"},
            {"id": "shaq", "name": "Sleeping Shaq", "url": "/static/memes/sleeping_shaq.jpg"},
            {"id": "change_mind", "name": "Change My Mind", "url": "/static/memes/change_my_mind.jpg"}
        ]

    return render_template("meme_templates.html", memes=memes)



import requests
@app.route("/meme_editor/<template_name>")
@login_required
def meme_editor(template_name):
    # Try to find the meme by ID from Imgflip API first
    meme_url = None
    meme_name = None

    try:
        response = requests.get("https://api.imgflip.com/get_memes", timeout=5)
        data = response.json()
        if data.get("success"):
            for meme in data["data"]["memes"]:
                if str(meme["id"]) == template_name:
                    meme_url = meme["url"]
                    meme_name = meme["name"]
                    break
    except:
        pass

    # If not found, fallback to local static memes
    local_memes = {
        "drake": "/static/memes/drake.jpg",
        "boyfriend": "/static/memes/distracted_boyfriend.jpg",
        "success": "/static/memes/success_kid.jpg",
        "two_buttons": "/static/memes/two_buttons.jpg",
        "gru_plan": "/static/memes/gru_plan.jpg",
        "shaq": "/static/memes/sleeping_shaq.jpg",
        "change_mind": "/static/memes/change_my_mind.jpg"
    }

    if not meme_url and template_name in local_memes:
        meme_url = local_memes[template_name]
        meme_name = template_name.replace("_", " ").title()

    return render_template("meme_editor.html", meme_name=meme_name, meme_url=meme_url)

@app.route("/trendy", methods=["GET"])
@login_required
def trendy():
    return render_template("trendy.html", country=request.args.get("country", "India"), trends=generate_trends_with_gemini(request.args.get("country", "India")))

@app.route("/recommendations", methods=["GET", "POST"])
@login_required
def recommendations():
    ai_data = None
    if request.method == "POST" and GENAI_AVAILABLE:
        try:
            model = genai.GenerativeModel(DEFAULT_GEMINI_MODEL)
            resp = model.generate_content(f"Marketing ideas for '{request.form.get('campaign')}'. Return JSON keys: memes, reels, hashtags.")
            match = re.search(r"\{.*\}", resp.text, re.DOTALL)
            if match: ai_data = json.loads(match.group())
        except Exception as e: ai_data = {"error": str(e)}
    return render_template("recommendations.html", campaign=request.form.get("campaign", ""), data=ai_data)

# =========================================================
#  🎥 VIDEO EDITOR ROUTES & LOGIC
# =========================================================

@app.route("/video_editor")
@login_required
def video_editor():
    return render_template("video_editor.html", videos=get_video_files(), audios=get_audio_files())

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    """Serve uploaded files to the HTML player"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/upload_file", methods=["POST"])
@login_required
def upload_file():
    file = request.files.get("file")
    if not file or file.filename == '':
        flash("⚠️ No file selected.", "error")
        return redirect(url_for("video_editor"))

    is_video = allowed_file(file.filename, app.config['ALLOWED_VIDEO_EXTENSIONS'])
    is_audio = allowed_file(file.filename, app.config['ALLOWED_AUDIO_EXTENSIONS'])

    if not (is_video or is_audio):
        flash("⚠️ Unsupported file type.", "error")
        return redirect(url_for("video_editor"))

    try:
        filename = generate_unique_filename(file.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)
        flash(f"✅ Uploaded: {filename}", "success")
    except Exception as e:
        flash(f"⚠️ Upload failed: {e}", "error")
    
    return redirect(url_for("video_editor"))

# =========================================================
#  🎥 VIDEO PROCESSING LOGIC (The Engine)
# =========================================================

def trim_video_logic():
    video_filename = request.form.get('video')
    start = safe_float(request.form.get('start'), 0)
    end = safe_float(request.form.get('end'), 0)

    if not video_filename: 
        flash('No video selected', 'error')
        return redirect(url_for('video_editor'))
    
    path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
    if not os.path.exists(path): 
        flash('Video file not found', 'error')
        return redirect(url_for('video_editor'))

    try:
        with VideoFileClip(path) as clip:
            if end > clip.duration: end = clip.duration
            if start >= end: 
                flash('Invalid start/end times', 'error')
                return redirect(url_for('video_editor'))
            
            trimmed = clip.subclip(start, end)
            output_filename = generate_unique_filename(video_filename, prefix='trimmed')
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            
            trimmed.write_videofile(
                output_path, 
                codec="libx264", 
                audio_codec="aac", 
                temp_audiofile="temp-audio.m4a", 
                remove_temp=True,
                logger=None
            )
            flash(f"✅ Trimmed successfully: {output_filename}", "success")
    except Exception as e:
        flash(f"⚠️ Trim error: {e}", "error")
    
    return redirect(url_for('video_editor'))

def add_text_logic():
    video_filename = request.form.get('video')
    text = request.form.get('text')
    
    if not video_filename or not text: 
        flash("Missing video or text", "error")
        return redirect(url_for('video_editor'))
    
    path = os.path.join(app.config["UPLOAD_FOLDER"], video_filename)
    
    try:
        with VideoFileClip(path) as clip:
            # Note: TextClip requires ImageMagick installed on server/PC
            txt_clip = TextClip(text, fontsize=50, color='white', font='Arial-Bold', stroke_color='black', stroke_width=2)
            txt_clip = txt_clip.set_position(('center', 'bottom')).set_duration(clip.duration)
            
            final = CompositeVideoClip([clip, txt_clip])
            output_filename = generate_unique_filename(video_filename, prefix='text')
            output_path = os.path.join(app.config["UPLOAD_FOLDER"], output_filename)
            
            final.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
            flash(f"✅ Text added: {output_filename}", "success")
    except Exception as e:
        flash(f"⚠️ Text Error (Ensure ImageMagick is installed): {e}", "error")
    
    return redirect(url_for('video_editor'))

def add_audio_logic():
    video_name = request.form.get('video')
    audio_name = request.form.get('audio')
    
    if not video_name or not audio_name: 
        flash("Missing video or audio", "error")
        return redirect(url_for('video_editor'))
    
    vid_path = os.path.join(app.config["UPLOAD_FOLDER"], video_name)
    aud_path = os.path.join(app.config["UPLOAD_FOLDER"], audio_name)
    
    if not os.path.exists(vid_path) or not os.path.exists(aud_path):
        flash("File not found", "error")
        return redirect(url_for('video_editor'))
    
    try:
        with VideoFileClip(vid_path) as video, AudioFileClip(aud_path) as audio:
            # Logic: Loop audio if shorter, trim if longer
            if audio.duration < video.duration:
                # Calculate loops needed
                loops_needed = int(video.duration / audio.duration) + 1
                final_audio = concatenate_audioclips([audio] * loops_needed).subclip(0, video.duration)
            else:
                final_audio = audio.subclip(0, video.duration)
                
            final = video.set_audio(final_audio)
            output_filename = generate_unique_filename(video_name, prefix='audio')
            output_path = os.path.join(app.config["UPLOAD_FOLDER"], output_filename)
            
            final.write_videofile(
                output_path, 
                codec="libx264", 
                audio_codec="aac", 
                temp_audiofile="temp-audio.m4a", 
                remove_temp=True,
                logger=None
            )
            flash(f"✅ Audio merged: {output_filename}", "success")
    except Exception as e:
        flash(f"⚠️ Audio Error: {e}", "error")
    
    return redirect(url_for('video_editor'))

def merge_logic():
    video_names = request.form.getlist("videos")
    
    if not video_names or len(video_names) < 2:
        flash("Select at least 2 videos to merge (Hold Ctrl/Cmd to select multiple)", "error")
        return redirect(url_for('video_editor'))
    
    try:
        video_clips = []
        for name in video_names:
            path = os.path.join(app.config["UPLOAD_FOLDER"], name)
            if os.path.exists(path):
                video_clips.append(VideoFileClip(path))
        
        if len(video_clips) < 2:
            flash("Not enough valid videos found", "error")
            return redirect(url_for('video_editor'))

        final = concatenate_videoclips(video_clips, method="compose")
        output_filename = f"merged_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.join(app.config["UPLOAD_FOLDER"], output_filename)
        
        final.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
        
        # Close clips
        for c in video_clips: c.close()
        
        flash(f"✅ Videos merged: {output_filename}", "success")
    except Exception as e:
        flash(f"⚠️ Merge Error: {e}", "error")
    
    return redirect(url_for('video_editor'))

def export_logic():
    """Simple export/convert function"""
    video_filename = request.form.get('video')
    
    if not video_filename:
        flash('No video selected', 'error')
        return redirect(url_for('video_editor'))
        
    path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
    try:
        with VideoFileClip(path) as clip:
            output_filename = generate_unique_filename(video_filename, prefix='export')
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            
            # Re-encoding
            clip.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
            flash(f"✅ Exported successfully: {output_filename}", "success")
    except Exception as e:
        flash(f"Export failed: {e}", "error")
    
    return redirect(url_for('video_editor'))

# --- Central Processing Route ---
@app.route("/process_video", methods=["POST"])
@login_required
def process_video():
    action = request.form.get("action")
    
    if action == "trim": return trim_video_logic()
    elif action == "add_text": return add_text_logic()
    elif action == "add_audio": return add_audio_logic()
    elif action == "merge": return merge_logic()
    elif action == "export": return export_logic()
    else:
        flash("⚠️ Unknown action", "error")
        return redirect(url_for("video_editor"))

# ==========================================
#               EXECUTION
# ==========================================

if __name__ == "__main__":
    create_user_table()
    init_db()
    print(f"📂 Database: {os.path.abspath(DATABASE_FILE)}")
    print(f"📂 Uploads:  {app.config['UPLOAD_FOLDER']}")
    app.run(debug=True, port=5000)