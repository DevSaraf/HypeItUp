
# 1. IMPORTS
import os
import sqlite3
import markdown
import json
import re
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv
from serpapi import GoogleSearch
import google.generativeai as genai
from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, AudioFileClip
from utils.ai_connectors import fetch_youtube_trends


# 2. INITIALIZATION & CONFIGURATION


# --- App & Environment Setup ---
app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY", "a_super_secret_default_key") # Use a key from .env for security

# --- API Client Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro") # Defaulting to 2.5 Pro
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
GENAI_AVAILABLE = False

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        GENAI_AVAILABLE = True
        print(f"✅ Gemini Client initialized successfully. Using model: {DEFAULT_GEMINI_MODEL}")
    except Exception as e:
        print(f"⚠️ ERROR: Failed to configure Gemini: {e}")
else:
    print("🔴 WARNING: GEMINI_API_KEY not found. AI features will be disabled.")

# --- Database & File Uploads ---
DATABASE_FILE = "hypeup.db"
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# 3. DATABASE & AUTH HELPERS


def init_db():
    """Initializes the goals table."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS goals (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            task TEXT NOT NULL,
                            duration TEXT NOT NULL,
                            completed BOOLEAN NOT NULL CHECK (completed IN (0, 1))
                        )''')
        conn.commit()

def create_user_table():
    """Initializes the users table."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT NOT NULL,
                            email TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL
                        )''')
        conn.commit()

def register_user(username, email, password):
    """Registers a new user."""
    password_hash = generate_password_hash(password)
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                           (username, email, password_hash))
            conn.commit()
        return True
    except sqlite3.IntegrityError: # This happens if the email is already taken
        return False

def validate_user(email, password):
    """Validates user credentials for login."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE email = ?", (email,))
        result = cursor.fetchone()
        if result and check_password_hash(result[0], password):
            return True
    return False

# --- Login Protection Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# 4. AUTHENTICATION ROUTES


@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        if register_user(request.form["username"], request.form["email"], request.form["password"]):
            flash("✅ Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))
        else:
            flash("⚠️ Email already exists. Try another.", "error")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        if validate_user(request.form["email"], request.form["password"]):
            session["user"] = request.form["email"]
            flash("✅ Logged in successfully!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("❌ Invalid credentials. Try again.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("👋 Logged out successfully.", "info")
    return redirect(url_for("login"))


# 5. CORE FEATURE ROUTES


@app.route("/dashboard")
@login_required
def dashboard():
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM goals ORDER BY id DESC")
        reminders = cursor.fetchall()
    return render_template("index.html", reminders=reminders)

@app.route("/goals", methods=["GET", "POST"])
@login_required
def goals():
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if request.method == 'POST':
            task, duration = request.form.get('task'), request.form.get('duration')
            if task and duration:
                cursor.execute("INSERT INTO goals (task, duration, completed) VALUES (?, ?, ?)", (task, duration, False))
                conn.commit()
            return redirect(url_for('goals'))
        cursor.execute("SELECT * FROM goals ORDER BY id DESC")
        all_goals = cursor.fetchall()
    return render_template("goal.html", goals=all_goals)

@app.route("/delete_goal/<int:goal_id>", methods=["POST"])
@login_required
def delete_goal(goal_id):
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        conn.commit()
    return redirect(url_for("goals"))

@app.route("/create_post", methods=["GET", "POST"])
@login_required
def create_post():
    ai_generated = None
    if request.method == "POST":
        platform = request.form.get("platform", "social media")
        content = request.form.get("content", "")
        if not GENAI_AVAILABLE:
            ai_generated = "⚠️ AI service unavailable. Check GEMINI_API_KEY."
        else:
            try:
                model = genai.GenerativeModel(DEFAULT_GEMINI_MODEL)
                prompt = f"Create a viral, catchy post for {platform} about '{content}'. Include relevant hashtags and emojis. Format with Markdown."
                response = model.generate_content(prompt)
                ai_generated = markdown.markdown(response.text)
            except Exception as e:
                ai_generated = f"⚠️ Error generating content: {e}"
    return render_template("create_post.html", ai_generated=ai_generated)

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
    country = request.args.get("country", "India")
    state = request.args.get("state", "")
    region = state or country
    trends, ai_tip = [], "Submit a location to get trends."
    if 'country' in request.args:
        if not GENAI_AVAILABLE:
            ai_tip = "⚠️ AI service is unavailable."
            trends = ["AI Offline"]
        else:
            try:
                params = {"engine": "google_trends", "q": f"Top searches in {region}", "api_key": SERPAPI_KEY}
                results = GoogleSearch(params).get_dict()
                trends = [item['query'] for item in results.get("related_queries", {}).get('rising', [])[:5]]
                if trends:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    prompt = f"Given these trending topics in {region}: {', '.join(trends)}. Provide one short, actionable marketing tip (max 15 words)."
                    response = model.generate_content(prompt)
                    ai_tip = response.text
                else:
                    ai_tip = "No specific rising trends found for this region."
            except Exception as e:
                ai_tip, trends = f"⚠️ Error: {e}", ["Error"]
    return render_template("trendy.html", country=country, state=state, trends=trends, ai_tip=ai_tip)

@app.route("/recommendations", methods=["GET", "POST"])
@login_required
def recommendations():
    campaign_topic = request.form.get("campaign", "").strip()
    ai_data = None
    if campaign_topic:
        if not GENAI_AVAILABLE:
            ai_data = {"error": "AI service unavailable."}
        else:
            try:
                # This function needs to be in your utils/ai_connectors.py
                video_titles = fetch_youtube_trends(campaign_topic)
                prompt = f"""
                You are a social media expert. Based on the campaign "{campaign_topic}" and these trending YouTube titles: {', '.join(video_titles)}.
                Suggest ideas in the following exact JSON format only:
                {{
                    "memes": ["idea1", "idea2", "idea3"],
                    "reels": ["idea1", "idea2", "idea3"],
                    "hashtags": ["#tag1", "#tag2", "#tag3"],
                    "best_time": "time to post",
                    "tip": "short viral tip"
                }}
                """
                model = genai.GenerativeModel(DEFAULT_GEMINI_MODEL)
                response = model.generate_content(prompt)
                match = re.search(r"\{.*\}", response.text, re.DOTALL)
                ai_data = json.loads(match.group()) if match else {"error": "Invalid AI response format"}
            except Exception as e:
                ai_data = {"error": f"An error occurred: {e}"}
    return render_template("recommendations.html", campaign=campaign_topic, data=ai_data)


# 6. VIDEO EDITOR ROUTES


@app.route("/video_editor")
@login_required
def video_editor():
    video_files = [f for f in os.listdir(app.config["UPLOAD_FOLDER"]) if f.endswith((".mp4", ".mov", ".avi"))]
    audio_files = [f for f in os.listdir(app.config["UPLOAD_FOLDER"]) if f.endswith((".mp3", ".wav"))]
    return render_template("video_editor.html", videos=video_files, audios=audio_files)

@app.route("/upload_file", methods=["POST"])
@login_required
def upload_file():
    file = request.files.get("file")
    if file and file.filename:
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
        flash(f"✅ Uploaded successfully: {file.filename}", "success")
    else:
        flash("⚠️ No file selected.", "error")
    return redirect(url_for("video_editor"))

@app.route("/process_video", methods=["POST"])
@login_required
def process_video():
    action = request.form.get("action")
    video_name = request.form.get("video")
    
    # The 'merge' action is special because it doesn't use a single 'video_name'
    if action == "merge":
        video_names = request.form.getlist("videos") # Use getlist for multiple selections
        if not video_names or len(video_names) < 2:
            flash("⚠️ Please select at least two videos to merge.", "error")
            return redirect(url_for("video_editor"))
        
        try:
            clips = []
            for name in video_names:
                path = os.path.join(app.config["UPLOAD_FOLDER"], name)
                if os.path.exists(path):
                    clips.append(VideoFileClip(path))
            
            if not clips:
                flash("⚠️ Could not find the selected video files.", "error")
                return redirect(url_for("video_editor"))

            final_clip = concatenate_videoclips(clips, method="compose")
            output_path = os.path.join(app.config["UPLOAD_FOLDER"], "merged_output.mp4")
            final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
            
            # Close all the clip objects to free up resources
            for clip in clips:
                clip.close()

            return send_file(output_path, as_attachment=True)

        except Exception as e:
            flash(f"⚠️ An error occurred during merge: {e}", "error")
            return redirect(url_for("video_editor"))

    # --- This part handles trim, add_text, and add_audio ---
    if not video_name:
        flash("⚠️ Please select a video for this action.", "error")
        return redirect(url_for("video_editor"))
        
    video_path = os.path.join(app.config["UPLOAD_FOLDER"], video_name)
    if not os.path.exists(video_path):
        flash("⚠️ Video file not found!", "error")
        return redirect(url_for("video_editor"))

    try:
        with VideoFileClip(video_path) as clip:
            if action == "trim":
                start, end = float(request.form.get("start")), float(request.form.get("end"))
                result = clip.subclip(start, end)
                output_filename = f"trimmed_{video_name}"
            elif action == "add_text":
                text = request.form.get("text")
                txt_clip = TextClip(text, fontsize=70, color='white', font='Arial-Bold').set_position('center').set_duration(clip.duration)
                result = CompositeVideoClip([clip, txt_clip])
                output_filename = f"text_{video_name}"
            elif action == "add_audio":
                audio_name = request.form.get("audio")
                audio_path = os.path.join(app.config["UPLOAD_FOLDER"], audio_name)
                if not os.path.exists(audio_path):
                    flash("⚠️ Audio file not found!", "error")
                    return redirect(url_for("video_editor"))
                audio_clip = AudioFileClip(audio_path)
                result = clip.set_audio(audio_clip.set_duration(clip.duration)) # Ensure audio matches video length
                output_filename = f"audio_{video_name}"
            else:
                flash("⚠️ Unknown action.", "error")
                return redirect(url_for("video_editor"))
            
            output_path = os.path.join(app.config["UPLOAD_FOLDER"], output_filename)
            result.write_videofile(output_path, codec="libx24", audio_codec="aac")
            return send_file(output_path, as_attachment=True)

    except Exception as e:
        flash(f"⚠️ An error occurred: {e}", "error")
        return redirect(url_for("video_editor"))
    # Merge is a special case with multiple files
    if action == "merge":
        # ... logic for merge ...
        pass

    return redirect(url_for("video_editor"))


# 7. MAIN EXECUTION BLOCK


if __name__ == "__main__":
    create_user_table()
    init_db()
    print(f"📂 Databases ready at: {os.path.abspath(DATABASE_FILE)}")
    app.run(debug=True, port=5000)