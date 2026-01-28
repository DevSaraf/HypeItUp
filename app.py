# # 1. IMPORTS
# import os
# import sqlite3
# import markdown
# import json
# import re
# from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
# from werkzeug.security import generate_password_hash, check_password_hash
# from functools import wraps
# from dotenv import load_dotenv
# # from serpapi import GoogleSearch
# import google.generativeai as genai
# from flask import send_from_directory
# # import praw
# from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, AudioFileClip
# # from utils.ai_connectors import fetch_youtube_trends


# # 2. INITIALIZATION & CONFIGURATION


# # --- App & Environment Setup ---
# app = Flask(__name__)
# load_dotenv()
# app.secret_key = os.getenv("SECRET_KEY", "a_super_secret_default_key") # Use a key from .env for security

# # --- API Client Configuration ---
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite") # Defaulting to 2.5 Pro
# SERPAPI_KEY = os.getenv("SERPAPI_KEY")
# GENAI_AVAILABLE = False

# if GEMINI_API_KEY:
#     try:
#         genai.configure(api_key=GEMINI_API_KEY)
#         GENAI_AVAILABLE = True
#         print(f"✅ Gemini Client initialized successfully. Using model: {DEFAULT_GEMINI_MODEL}")
#     except Exception as e:
#         print(f"⚠️ ERROR: Failed to configure Gemini: {e}")
# else:
#     print("🔴 WARNING: GEMINI_API_KEY not found. AI features will be disabled.")

# # --- Database & File Uploads ---
# DATABASE_FILE = "hypeup.db"
# app.config["UPLOAD_FOLDER"] = "uploads"
# os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# # 3. DATABASE & AUTH HELPERS


# def init_db():
#     """Initializes the goals table."""
#     with sqlite3.connect(DATABASE_FILE) as conn:
#         cursor = conn.cursor()
#         cursor.execute('''CREATE TABLE IF NOT EXISTS goals (
#                             id INTEGER PRIMARY KEY AUTOINCREMENT,
#                             task TEXT NOT NULL,
#                             duration TEXT NOT NULL,
#                             completed BOOLEAN NOT NULL CHECK (completed IN (0, 1))
#                         )''')
#         conn.commit()

# def create_user_table():
#     """Initializes the users table."""
#     with sqlite3.connect(DATABASE_FILE) as conn:
#         cursor = conn.cursor()
#         cursor.execute('''CREATE TABLE IF NOT EXISTS users (
#                             id INTEGER PRIMARY KEY AUTOINCREMENT,
#                             username TEXT NOT NULL,
#                             email TEXT UNIQUE NOT NULL,
#                             password_hash TEXT NOT NULL
#                         )''')
#         conn.commit()

# def register_user(username, email, password):
#     """Registers a new user."""
#     password_hash = generate_password_hash(password)
#     try:
#         with sqlite3.connect(DATABASE_FILE) as conn:
#             cursor = conn.cursor()
#             cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
#                            (username, email, password_hash))
#             conn.commit()
#         return True
#     except sqlite3.IntegrityError: # This happens if the email is already taken
#         return False

# def validate_user(email, password):
#     """Validates user credentials for login."""
#     with sqlite3.connect(DATABASE_FILE) as conn:
#         cursor = conn.cursor()
#         cursor.execute("SELECT password_hash FROM users WHERE email = ?", (email,))
#         result = cursor.fetchone()
#         if result and check_password_hash(result[0], password):
#             return True
#     return False

# # --- Login Protection Decorator ---
# def login_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if "user" not in session:
#             flash("Please log in to access this page.", "warning")
#             return redirect(url_for("login"))
#         return f(*args, **kwargs)
#     return decorated_function

# #trend fetching logic
# def generate_trends_with_gemini(region: str, max_items: int = 5):
#     """
#     Use Gemini LLM to generate short trending search queries/phrases for `region`.
#     Returns a list of clean short strings (max length = max_items).
#     """
#     region = (region or "Global").strip()
#     if not GENAI_AVAILABLE:
#         # LLM not configured — return a small default list so UI never breaks
#         return ["AI not configured - try SERPAPI", "Demo trend 2", "Demo trend 3"][:max_items]

#     try:
#         model = genai.GenerativeModel(DEFAULT_GEMINI_MODEL)
#         prompt = (
#             f"You are a helpful assistant that invents realistic, short trending search queries people in "
#             f"{region} might search for today. Produce exactly {max_items} short lines (one trend per line). "
#             "Each line should be a short phrase (3–7 words), do NOT include long explanations or numbering, "
#             "and avoid punctuation at the end. Example lines: 'Monsoon weather updates', 'University admission dates'."
#         )

#         # Generate content (model API call)
#         response = model.generate_content(prompt)
#         text = (response.text or "").strip()

#         # Parse lines into items (robust cleaning)
#         items = []
#         for raw in text.splitlines():
#             line = raw.strip()
#             if not line:
#                 continue
#             # remove any leading numbering or bullets like '1.' or '•'
#             line = re.sub(r'^\s*\d+[\).\-\s]*', '', line)
#             line = re.sub(r'^[\u2022\-\•\*]\s*', '', line)
#             # collapse multiple spaces
#             line = re.sub(r'\s{2,}', ' ', line).strip()
#             # require a sensible length and characters
#             if 3 <= len(line) <= 120:
#                 items.append(line)
#             if len(items) >= max_items:
#                 break

#         # final dedupe/pad/truncate
#         seen = set()
#         cleaned = []
#         for it in items:
#             if it.lower() not in seen:
#                 cleaned.append(it)
#                 seen.add(it.lower())
#             if len(cleaned) >= max_items:
#                 break

#         # fallback if model gave nothing useful
#         if not cleaned:
#             return ["No AI trends generated."][:max_items]

#         return cleaned

#     except Exception as e:
#         print("⚠️ Gemini trend generation failed:", e)
#         # Last fallback static list
#         return [
#             f"{region} trending topic 1",
#             f"{region} trending topic 2",
#             f"{region} trending topic 3",
#             f"{region} trending topic 4",
#             f"{region} trending topic 5",
#         ][:max_items]
    
# # 4. AUTHENTICATION ROUTES


# @app.route("/")
# def home():
#     return redirect(url_for("login"))

# @app.route("/signup", methods=["GET", "POST"])
# def signup():
#     if "user" in session:
#         return redirect(url_for("dashboard"))
#     if request.method == "POST":
#         if register_user(request.form["username"], request.form["email"], request.form["password"]):
#             flash("✅ Account created successfully! Please log in.", "success")
#             return redirect(url_for("login"))
#         else:
#             flash("⚠️ Email already exists. Try another.", "error")
#     return render_template("signup.html")

# @app.route("/login", methods=["GET", "POST"])
# def login():
#     if "user" in session:
#         return redirect(url_for("dashboard"))
#     if request.method == "POST":
#         if validate_user(request.form["email"], request.form["password"]):
#             session["user"] = request.form["email"]
#             flash("✅ Logged in successfully!", "success")
#             return redirect(url_for("dashboard"))
#         else:
#             flash("❌ Invalid credentials. Try again.", "error")
#     return render_template("login.html")

# @app.route("/logout")
# def logout():
#     session.pop("user", None)
#     flash("👋 Logged out successfully.", "info")
#     return redirect(url_for("login"))


# # 5. CORE FEATURE ROUTES


# @app.route("/dashboard")
# @login_required
# def dashboard():
#     with sqlite3.connect(DATABASE_FILE) as conn:
#         conn.row_factory = sqlite3.Row
#         cursor = conn.cursor()
#         cursor.execute("SELECT * FROM goals ORDER BY id DESC")
#         reminders = cursor.fetchall()
#     return render_template("index.html", reminders=reminders)

# @app.route("/goals", methods=["GET", "POST"])
# @login_required
# def goals():
#     with sqlite3.connect(DATABASE_FILE) as conn:
#         conn.row_factory = sqlite3.Row
#         cursor = conn.cursor()
#         if request.method == 'POST':
#             task, duration = request.form.get('task'), request.form.get('duration')
#             if task and duration:
#                 cursor.execute("INSERT INTO goals (task, duration, completed) VALUES (?, ?, ?)", (task, duration, False))
#                 conn.commit()
#             return redirect(url_for('goals'))
#         cursor.execute("SELECT * FROM goals ORDER BY id DESC")
#         all_goals = cursor.fetchall()
#     return render_template("goal.html", goals=all_goals)

# @app.route("/delete_goal/<int:goal_id>", methods=["POST"])
# @login_required
# def delete_goal(goal_id):
#     with sqlite3.connect(DATABASE_FILE) as conn:
#         cursor = conn.cursor()
#         cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
#         conn.commit()
#     return redirect(url_for("goals"))

# @app.route("/create_post", methods=["GET", "POST"])
# @login_required
# def create_post():
#     ai_generated = None
#     if request.method == "POST":
#         platform = request.form.get("platform", "social media")
#         content = request.form.get("content", "")
#         if not GENAI_AVAILABLE:
#             ai_generated = "⚠️ AI service unavailable. Check GEMINI_API_KEY."
#         else:
#             try:
#                 model = genai.GenerativeModel(DEFAULT_GEMINI_MODEL)
#                 prompt = f"Create a viral, catchy post for {platform} about '{content}'. Include relevant hashtags and emojis. Format with Markdown."
#                 response = model.generate_content(prompt)
#                 ai_generated = markdown.markdown(response.text)
#             except Exception as e:
#                 ai_generated = f"⚠️ Error generating content: {e}"
#     return render_template("create_post.html", ai_generated=ai_generated)


# @app.route("/meme_templates")
# @login_required
# def meme_templates():
#     memes = []

#     try:
#         response = requests.get("https://api.imgflip.com/get_memes", timeout=5)
#         data = response.json()
#         if data.get("success"):
#             memes = data["data"]["memes"][:20]
#     except Exception as e:
#         print("⚠️ Could not fetch memes:", e)

#     # Local fallback if no internet
#     if not memes:
#         memes = [
#             {"id": "drake", "name": "Drake Hotline Bling", "url": "/static/memes/drake.jpg"},
#             {"id": "boyfriend", "name": "Distracted Boyfriend", "url": "/static/memes/distracted_boyfriend.jpg"},
#             {"id": "success", "name": "Success Kid", "url": "/static/memes/success_kid.jpg"},
#             {"id": "two_buttons", "name": "Two Buttons", "url": "/static/memes/two_buttons.jpg"},
#             {"id": "gru_plan", "name": "Gru’s Plan", "url": "/static/memes/gru_plan.jpg"},
#             {"id": "shaq", "name": "Sleeping Shaq", "url": "/static/memes/sleeping_shaq.jpg"},
#             {"id": "change_mind", "name": "Change My Mind", "url": "/static/memes/change_my_mind.jpg"}
#         ]

#     return render_template("meme_templates.html", memes=memes)



# import requests
# @app.route("/meme_editor/<template_name>")
# @login_required
# def meme_editor(template_name):
#     # Try to find the meme by ID from Imgflip API first
#     meme_url = None
#     meme_name = None

#     try:
#         response = requests.get("https://api.imgflip.com/get_memes", timeout=5)
#         data = response.json()
#         if data.get("success"):
#             for meme in data["data"]["memes"]:
#                 if str(meme["id"]) == template_name:
#                     meme_url = meme["url"]
#                     meme_name = meme["name"]
#                     break
#     except:
#         pass

#     # If not found, fallback to local static memes
#     local_memes = {
#         "drake": "/static/memes/drake.jpg",
#         "boyfriend": "/static/memes/distracted_boyfriend.jpg",
#         "success": "/static/memes/success_kid.jpg",
#         "two_buttons": "/static/memes/two_buttons.jpg",
#         "gru_plan": "/static/memes/gru_plan.jpg",
#         "shaq": "/static/memes/sleeping_shaq.jpg",
#         "change_mind": "/static/memes/change_my_mind.jpg"
#     }

#     if not meme_url and template_name in local_memes:
#         meme_url = local_memes[template_name]
#         meme_name = template_name.replace("_", " ").title()

#     return render_template("meme_editor.html", meme_name=meme_name, meme_url=meme_url)


# @app.route("/trendy", methods=["GET"])
# @login_required
# def trendy():
#     # read query params
#     country = request.args.get("country", "India")
#     state = request.args.get("state", "")
#     region = (state or country).strip()

#     trends = []
#     ai_tip = "Submit a location to get trends."

#     # If the page was requested with parameters, generate trends
#     if 'country' in request.args or 'state' in request.args:
#         # Use Gemini LLM to generate trends (primary for demo)
#         trends = generate_trends_with_gemini(region, max_items=5)

#         # Prepare a short marketing tip via Gemini if available
#         if GENAI_AVAILABLE and trends and trends[0] not in ("No AI trends generated.", "No AI trends generated."):
#             try:
#                 model = genai.GenerativeModel(DEFAULT_GEMINI_MODEL)
#                 tip_prompt = (
#                     f"Given these trending topics in {region}: {', '.join(trends)}. "
#                     "Write one short, actionable marketing tip (max 12 words)."
#                 )
#                 tip_resp = model.generate_content(tip_prompt)
#                 ai_tip = (tip_resp.text or "").strip()
#                 # keep tip short (fallback)
#                 if not ai_tip:
#                     ai_tip = f"Create short posts around '{trends[0]}' and reuse across formats."
#             except Exception as e:
#                 print("⚠️ AI tip generation failed:", e)
#                 ai_tip = f"Create short posts around '{trends[0]}' and reuse across formats."
#         else:
#             # If LLM unavailable, deterministic tip
#             ai_tip = f"Create quick content around '{trends[0]}' and reuse across formats."

#     return render_template("trendy.html", country=country, state=state, trends=trends, ai_tip=ai_tip)

# @app.route("/recommendations", methods=["GET", "POST"])
# @login_required
# def recommendations():
#     campaign_topic = request.form.get("campaign", "").strip()
#     ai_data = None
#     if campaign_topic:
#         if not GENAI_AVAILABLE:
#             ai_data = {"error": "AI service unavailable."}
#         else:
#             try:
#                 # This function needs to be in your utils/ai_connectors.py
#                 video_titles = fetch_youtube_trends(campaign_topic)
#                 prompt = f"""
#                 You are a social media expert. Based on the campaign "{campaign_topic}" and these trending YouTube titles: {', '.join(video_titles)}.
#                 Suggest ideas in the following exact JSON format only:
#                 {{
#                     "memes": ["idea1", "idea2", "idea3"],
#                     "reels": ["idea1", "idea2", "idea3"],
#                     "hashtags": ["#tag1", "#tag2", "#tag3"],
#                     "best_time": "time to post",
#                     "tip": "short viral tip"
#                 }}
#                 """
#                 model = genai.GenerativeModel(DEFAULT_GEMINI_MODEL)
#                 response = model.generate_content(prompt)
#                 match = re.search(r"\{.*\}", response.text, re.DOTALL)
#                 ai_data = json.loads(match.group()) if match else {"error": "Invalid AI response format"}
#             except Exception as e:
#                 ai_data = {"error": f"An error occurred: {e}"}
#     return render_template("recommendations.html", campaign=campaign_topic, data=ai_data)


# # 6. VIDEO EDITOR ROUTES


# @app.route("/video_editor")
# @login_required
# def video_editor():
#     video_files = [f for f in os.listdir(app.config["UPLOAD_FOLDER"]) if f.endswith((".mp4", ".mov", ".avi"))]
#     audio_files = [f for f in os.listdir(app.config["UPLOAD_FOLDER"]) if f.endswith((".mp3", ".wav"))]
#     return render_template("video_editor.html", videos=video_files, audios=audio_files)

# @app.route("/upload_file", methods=["POST"])
# @login_required
# def upload_file():
#     file = request.files.get("file")
#     if file and file.filename:
#         file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
#         flash(f"✅ Uploaded successfully: {file.filename}", "success")
#     else:
#         flash("⚠️ No file selected.", "error")
#     return redirect(url_for("video_editor"))

# @app.route("/process_video", methods=["POST"])
# @login_required
# def process_video():
#     action = request.form.get("action")
#     video_name = request.form.get("video")
    
#     # The 'merge' action is special because it doesn't use a single 'video_name'
#     if action == "merge":
#         video_names = request.form.getlist("videos") # Use getlist for multiple selections
#         if not video_names or len(video_names) < 2:
#             flash("⚠️ Please select at least two videos to merge.", "error")
#             return redirect(url_for("video_editor"))
        
#         try:
#             clips = []
#             for name in video_names:
#                 path = os.path.join(app.config["UPLOAD_FOLDER"], name)
#                 if os.path.exists(path):
#                     clips.append(VideoFileClip(path))
            
#             if not clips:
#                 flash("⚠️ Could not find the selected video files.", "error")
#                 return redirect(url_for("video_editor"))

#             final_clip = concatenate_videoclips(clips, method="compose")
#             output_path = os.path.join(app.config["UPLOAD_FOLDER"], "merged_output.mp4")
#             final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
            
#             # Close all the clip objects to free up resources
#             for clip in clips:
#                 clip.close()

#             return send_file(output_path, as_attachment=True)

#         except Exception as e:
#             flash(f"⚠️ An error occurred during merge: {e}", "error")
#             return redirect(url_for("video_editor"))

#     # --- This part handles trim, add_text, and add_audio ---
#     if not video_name:
#         flash("⚠️ Please select a video for this action.", "error")
#         return redirect(url_for("video_editor"))
        
#     video_path = os.path.join(app.config["UPLOAD_FOLDER"], video_name)
#     if not os.path.exists(video_path):
#         flash("⚠️ Video file not found!", "error")
#         return redirect(url_for("video_editor"))

#     try:
#         with VideoFileClip(video_path) as clip:
#             if action == "trim":
#                 start, end = float(request.form.get("start")), float(request.form.get("end"))
#                 result = clip.subclip(start, end)
#                 output_filename = f"trimmed_{video_name}"
#             elif action == "add_text":
#                 text = request.form.get("text")
#                 txt_clip = TextClip(text, fontsize=70, color='white', font='Arial-Bold').set_position('center').set_duration(clip.duration)
#                 result = CompositeVideoClip([clip, txt_clip])
#                 output_filename = f"text_{video_name}"
#             elif action == "add_audio":
#                 audio_name = request.form.get("audio")
#                 audio_path = os.path.join(app.config["UPLOAD_FOLDER"], audio_name)
#                 if not os.path.exists(audio_path):
#                     flash("⚠️ Audio file not found!", "error")
#                     return redirect(url_for("video_editor"))
#                 audio_clip = AudioFileClip(audio_path)
#                 result = clip.set_audio(audio_clip.set_duration(clip.duration)) # Ensure audio matches video length
#                 output_filename = f"audio_{video_name}"
#             else:
#                 flash("⚠️ Unknown action.", "error")
#                 return redirect(url_for("video_editor"))
            
#             output_path = os.path.join(app.config["UPLOAD_FOLDER"], output_filename)
#             result.write_videofile(output_path, codec="libx24", audio_codec="aac")
#             return send_file(output_path, as_attachment=True)

#     except Exception as e:
#         flash(f"⚠️ An error occurred: {e}", "error")
#         return redirect(url_for("video_editor"))
#     # Merge is a special case with multiple files
#     if action == "merge":
#         # ... logic for merge ...
#         pass

#     return redirect(url_for("video_editor"))


# # 7. MAIN EXECUTION BLOCK


# if __name__ == "__main__":
#     create_user_table()
#     init_db()
#     print(f"📂 Databases ready at: {os.path.abspath(DATABASE_FILE)}")
#     app.run(debug=True, port=5000)

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
        reminders = conn.cursor().execute("SELECT * FROM goals ORDER BY id DESC").fetchall()
    return render_template("index.html", reminders=reminders)

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

@app.route("/meme_templates")
@login_required
def meme_templates():
    memes = []
    try:
        r = requests.get("https://api.imgflip.com/get_memes", timeout=5)
        if r.json().get("success"): memes = r.json()["data"]["memes"][:20]
    except: pass
    if not memes: memes = [{"id": "drake", "name": "Drake", "url": "/static/memes/drake.jpg"}]
    return render_template("meme_templates.html", memes=memes)

@app.route("/meme_editor/<template_name>")
@login_required
def meme_editor(template_name):
    return render_template("meme_editor.html", meme_name=template_name, meme_url=f"https://i.imgflip.com/{template_name}.jpg")

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