from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
from functools import wraps
import os
import requests
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai
import markdown
from serpapi import GoogleSearch
from utils.auth import create_user_table, register_user, validate_user
from utils.ai_connectors import generate_text
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip
import tempfile
from dotenv import load_dotenv
import google.generativeai as genai
import re
import json
from utils.ai_connectors import fetch_youtube_trends

# Add this entire block at the top of your app.py

# ... (your other imports like Flask, render_template, etc.)
from dotenv import load_dotenv
import google.generativeai as genai
import os

# --- INITIALIZATION & API SETUP ---
app = Flask(__name__)
load_dotenv() # Load variables from .env file

# --- Configure and Initialize Gemini Client ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GENAI_AVAILABLE = False # This is the variable that was missing

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        GENAI_AVAILABLE = True
        print(f"✅ Gemini Client initialized successfully. Using model: {DEFAULT_GEMINI_MODEL}")
    except Exception as e:
        print(f"⚠️ ERROR: Failed to configure Gemini: {e}")
else:
    print("🔴 WARNING: GEMINI_API_KEY not found. AI features will be disabled.")



# ------------------ BASIC SETUP ------------------

load_dotenv()

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Initialize database for goals and users
DATABASE_FILE = "hypeup.db"
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

def init_db():
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS goals (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            task TEXT NOT NULL,
                            duration TEXT NOT NULL
                        )''')
        conn.commit()

create_user_table()
init_db()

# ------------------ OPENROUTER + GEMINI CONFIG ------------------

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("🔑 OpenRouter key loaded:", bool(os.getenv("OPENROUTER_API_KEY")))

# ------------------ LOGIN PROTECTION ------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ------------------ AUTH ROUTES ------------------

@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))



@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        if register_user(username, email, password):
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
        email = request.form["email"]
        password = request.form["password"]

        if validate_user(email, password):
            session["user"] = email
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


# ------------------ DASHBOARD ------------------

@app.route("/dashboard")
@login_required
def dashboard():
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM goals ORDER BY id DESC")
        reminders = cursor.fetchall()
    return render_template("index.html", reminders=reminders)





# ------------------ GOALS ------------------
@app.route("/goals", methods=["GET", "POST"])
def goals():
    if request.method == "POST":
        task = request.form["task"]
        duration = request.form["duration"]

        if task and duration:
            with sqlite3.connect(DATABASE_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO goals (task, duration) VALUES (?, ?)", (task, duration))
                conn.commit()
        return redirect(url_for("goals"))

    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM goals ORDER BY id DESC")
        goals = cursor.fetchall()
    return render_template("goal.html", goals=goals)


@app.route("/delete_goal/<int:goal_id>", methods=["POST"])
def delete_goal(goal_id):
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        conn.commit()
    return redirect(url_for("goals"))


# ------------------ CREATE POST ------------------
# import markdown  

# @app.route("/create_post", methods=["GET", "POST"])
# def create_post():
#     ai_generated = None

#     if request.method == "POST":
#         content = request.form.get("content", "")
#         platform = request.form.get("platform", "")

#         try:
#             prompt = f"""
#             Create a viral, catchy, and engaging post for {platform}.
#             Campaign details: {content}.
#             Keep it under 100 words and include relevant hashtags.
#             """

#             completion = client.chat.completions.create(
#                 model="deepseek/deepseek-r1:free",
#                 messages=[
#                     {"role": "system", "content": "You are a professional digital marketing assistant."},
#                     {"role": "user", "content": prompt}
#                 ]
#             )

#             raw_text = completion.choices[0].message.content.strip()

#             # ✅ Convert Markdown to clean HTML
#             ai_generated = markdown.markdown(raw_text)

#         except Exception as e:
#             ai_generated = f"⚠️ Error generating content: {str(e)}"

#     return render_template("create_post.html", ai_generated=ai_generated)

# from utils.ai_connectors import generate_text
# import markdown

# @app.route("/create_post", methods=["GET", "POST"])
# def create_post():
#     ai_generated = None

#     if request.method == "POST":
#         content = request.form.get("content", "")
#         platform = request.form.get("platform", "")

#         try:
#             prompt = f"""
#             Create a viral, catchy, and engaging post for {platform}.
#             Campaign details: {content}.
#             Keep it under 100 words and include relevant hashtags and emojis.
#             """

#             # ✅ Use the universal helper (DeepSeek via OpenRouter)
#             raw_text = generate_text(prompt)

#             # ✅ Convert Markdown to clean HTML
#             ai_generated = markdown.markdown(raw_text)

#         except Exception as e:
#             ai_generated = f"⚠️ Error generating content: {str(e)}"

#     return render_template("create_post.html", ai_generated=ai_generated)

# @app.route("/create_post", methods=["GET", "POST"])
# def create_post():
#     ai_output = ""
#     if request.method == "POST":
#         topic = request.form.get("topic", "")
#         platform = request.form.get("platform", "")
#         tone = request.form.get("tone", "")
#         length = request.form.get("length", "")

#         prompt = f"""
#         Create a {length} social media post about "{topic}" for {platform}.
#         The tone should be {tone}. Make it catchy, concise, and engaging.
#         """

#         try:
#             import os, requests

#             # Use main OpenRouter API key
#             api_key = os.getenv("OPENROUTER_API_KEY")

#             headers = {
#                 "Authorization": f"Bearer {api_key}",
#                 "Content-Type": "application/json",
#             }

#             payload = {
#                 "model": "deepseek/deepseek-r1:free",
#                 "messages": [
#                     {
#                         "role": "system",
#                         "content": "You are a creative and precise social media content generator."
#                     },
#                     {"role": "user", "content": prompt}
#                 ],
#                 "max_tokens": 300,
#                 "temperature": 0.8,
#             }

#             # Direct call to OpenRouter API
#             response = requests.post(
#                 "https://openrouter.ai/api/v1/chat/completions",
#                 headers=headers,
#                 json=payload,
#                 timeout=60
#             )

#             data = response.json()

#             # ✅ Success Case
#             if "choices" in data and len(data["choices"]) > 0:
#                 ai_output = data["choices"][0]["message"]["content"].strip()

#             # ⚠️ Handle OpenRouter-side errors
#             elif "error" in data:
#                 ai_output = f"⚠️ OpenRouter error: {data['error'].get('message', 'Unknown error')}"

#             # 🚨 Handle unexpected JSON
#             else:
#                 ai_output = "⚠️ Unexpected response from AI model. Please try again later."

#         except requests.exceptions.RequestException as e:
#             ai_output = f"⚠️ Network error: {e}"
#         except Exception as e:
#             ai_output = f"⚠️ Error generating content: {e}"

#     return render_template("create_post.html", ai_output=ai_output)
# --- UPDATED: Create Post Feature with Gemini ---
# Make sure 'markdown' is imported at the top of your app.py
import markdown

# --- UPDATED: Create Post Feature with Gemini ---
@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    ai_generated = None  # Use None to indicate no output yet

    if request.method == "POST":
        # 1. Get the new form fields: 'platform' and 'content'
        platform = request.form.get("platform", "social media")
        content = request.form.get("content", "")

        # 2. Check if the API key is available
        if not GEMINI_API_KEY:
            ai_generated = "⚠️ AI service is unavailable. The GEMINI_API_KEY is not configured."
            return render_template("create_post.html", ai_generated=ai_generated)

        # 3. Construct a better prompt using the new fields
        prompt = f"""
        You are a professional digital marketing assistant.
        Create a viral, catchy, and engaging post for the platform: {platform}.
        The campaign is about: "{content}".
        Keep the post concise and include relevant hashtags and emojis.
        Format your response using Markdown (e.g., use **bold** for emphasis and bullet points for lists).
        """

        try:
            # 4. Make the API call to Gemini
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(prompt)
            raw_text = response.text

            # 5. Convert the AI's Markdown response to HTML
            # This is crucial for the '|safe' filter in your HTML to work correctly
            ai_generated = markdown.markdown(raw_text)

        except Exception as e:
            print(f"Gemini Error in create_post: {e}")
            ai_generated = f"⚠️ Error generating content: {e}"

    # 6. Render the page, passing in the generated HTML
    return render_template("create_post.html", ai_generated=ai_generated)

    



# @app.route("/create_post", methods=["GET", "POST"])
# def create_post():
#     ai_generated = None

#     if request.method == "POST":
#         content = request.form.get("content", "")
#         platform = request.form.get("platform", "")

#         try:
            # Create a prompt for the local Gemma 2 model
            # prompt = f"""
            # You are a creative social media strategist.
            # Write a short, viral, and engaging post for {platform}.
            # Campaign details: {content}.
            # Keep it within 100 words, add emojis, and include 3–5 relevant hashtags.
            # """

            # 🔹 Generate using your local Ollama model (Gemma 2)
    #         ai_generated = generate_text(prompt)

    #     except Exception as e:
    #         ai_generated = f"⚠️ Error generating content: {str(e)}"

    # return render_template("create_post.html", ai_generated=ai_generated)




@app.route("/meme_templates")
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



@app.route("/meme_editor/<template_name>")
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



# ------------------ TRENDY (NEW FEATURE) ------------------
# import re, json, html

# def clean_ai_text(s: str) -> str:
#     """
#     Remove Markdown/asterisks/extra whitespace/HTML entities/emojis and return plain text.
#     """
#     if not s:
#         return ""
#     # Decode HTML entities
#     s = html.unescape(s)
#     # Remove code fences and inline code ticks
#     s = re.sub(r"```.*?```", " ", s, flags=re.DOTALL)
#     s = s.replace("`", " ")
#     # Remove Markdown emphasis/strong markers and leftover asterisks / underscores
#     s = re.sub(r"(\*|_){1,}", " ", s)
#     # Remove common emoji characters (basic range), keep simple characters
#     s = re.sub(r"[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\U00002600-\U000027BF]+", " ", s)
#     # Remove repeated punctuation
#     s = re.sub(r"[^\w#\s,-]{2,}", " ", s)
#     # Collapse whitespace
#     s = re.sub(r"\s+", " ", s).strip()
#     return s

# def extract_hashtags_and_tip(raw_output: str):
    # """
    # Given raw AI output, try:
    #   1) JSON extraction (preferred),
    #   2) Regex hashtag extraction + sentence heuristics for tip,
    #   3) fallback defaults.
    # Returns: (list_of_hashtags, tip_string)
    # """
    # hashtags = []
    # tip = ""

    # # 1) Try to locate JSON-like substring and parse
    # try:
    #     json_match = re.search(r"\{.*\}", raw_output, re.DOTALL)
    #     if json_match:
    #         # attempt to clean common separators before json parse
    #         possible_json = json_match.group(0)
    #         possible_json = possible_json.replace("\n", " ")
    #         data = json.loads(possible_json)
    #         # normalize values
    #         raw_hashtags = data.get("hashtags") or data.get("tags") or data.get("tags_list") or []
    #         if isinstance(raw_hashtags, str):
    #             # sometimes single string of comma separated tags
    #             raw_hashtags = re.findall(r"#\w+", raw_hashtags) or [t.strip() for t in raw_hashtags.split(",") if t.strip()]
    #         hashtags = [clean_ai_text(h) for h in raw_hashtags if h]
    #         tip = clean_ai_text(data.get("tip") or data.get("advice") or data.get("strategy") or "")
    # except Exception:
    #     # ignore parse errors and fall back
    #     pass

    # # 2) If JSON failed or produced few results, fallback to regex
    # if len(hashtags) < 3:
    #     # Extract hashtags (#word) first
    #     found = re.findall(r"(?:#\w[\w-]*)", raw_output)
    #     if found:
    #         hashtags = [clean_ai_text(h) for h in found]
    #         # remove duplicates while preserving order
    #         seen = set(); uniq = []
    #         for h in hashtags:
    #             if h.lower() not in seen:
    #                 seen.add(h.lower()); uniq.append(h)
    #         hashtags = uniq

    # # 3) If still not enough, look for comma-separated keywords and pick top candidates
    # if len(hashtags) < 3:
    #     # attempt to look for "Hashtags:" lines or "1." lists
    #     lines = raw_output.splitlines()
    #     candidates = []
    #     for line in lines:
    #         line_clean = clean_ai_text(line)
    #         # comma separated tokens that look like tag words
    #         parts = re.split(r"[,\-—\|;:]", line_clean)
    #         for p in parts:
    #             p = p.strip()
    #             # skip sentences
    #             if len(p) <= 0 or len(p.split()) > 4:
    #                 continue
    #             # convert phrase -> hashtag
    #             h = "#" + re.sub(r"[^\w]", "", p)
    #             if len(h) > 1:
    #                 candidates.append(h)
    #     # append candidates
    #     for c in candidates:
    #         if c.lower() not in {h.lower() for h in hashtags}:
    #             hashtags.append(c)
    #             if len(hashtags) >= 5:
    #                 break

    # # ensure lowercase and remove duplicates, keep up to 5
    # normalized = []
    # seen = set()
    # for h in hashtags:
    #     h_clean = h.strip()
    #     if not h_clean:
    #         continue
    #     # ensure leading #
    #     if not h_clean.startswith("#"):
    #         h_clean = "#" + re.sub(r"[^\w-]", "", h_clean)
    #     if h_clean.lower() not in seen:
    #         seen.add(h_clean.lower())
    #         normalized.append(h_clean)
    #     if len(normalized) >= 5:
    #         break
    # hashtags = normalized

    # # 4) Tip extraction heuristics: look for short sentences beginning with verbs or explicit "Tip:"
    # if not tip:
    #     # try "Tip: ..." or "Advice: ..."
    #     m = re.search(r"(?:Tip|Advice|Strategy|Suggestion|Post)\s*[:\-]\s*(.+?)(?:\.|$)", raw_output, re.IGNORECASE)
    #     if m:
    #         tip = clean_ai_text(m.group(1))
    #     else:
    #         # fallback: find a short sentence with imperative verbs
    #         sentences = re.split(r"[.\n]", raw_output)
    #         for s in sentences:
    #             s_clean = clean_ai_text(s)
    #             if not s_clean:
    #                 continue
    #             # pick short sentence (<= 18 words) that starts with a verb-ish or strong phrase
    #             if len(s_clean.split()) <= 18 and re.match(r"^(Post|Use|Try|Share|Focus|Target|Emphas|Include|Upload|Use|Add|Post|Engage)\b", s_clean, re.IGNORECASE):
    #                 tip = s_clean
    #                 break

    # # 5) final fallbacks if nothing found
    # if not hashtags:
    #     hashtags = ["#Viral", "#TrendingNow", "#SocialMedia", "#Meme", "#Marketing"]
    # if not tip:
    #     tip = "Post between 6–9 PM local time and use 3–5 relevant hashtags."

    # return hashtags[:5], tip.strip()
# @app.route("/trendy", methods=["GET", "POST"])
# def trendy():
#     """
#     Improved trendy endpoint: deterministic, structured prompt and robust extraction.
#     """
#     country = request.args.get("country", "India")
#     state = request.args.get("state", "")
#     region = state or country

#     # Strict prompt: ask for JSON and short answers, insist on 5 hashtags + short tip
#     prompt = f"""
# You are a precise social media growth assistant. For the region: {region}, produce exactly FIVE trending hashtags
# and one extremely short viral tip (no more than 14 words). Output MUST be valid JSON only, like:

# {{ "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"], "tip": "one short tip here" }}

# Do not add any commentary, markdown, bullets or explanation — ONLY the JSON object.
# If you do not know exact trending tags, produce plausible popular hashtags for that region.
# """



    # raw_output = ""
    # try:
    #     # Use deterministic generation
    #     completion = client.chat.completions.create(
    #         model="deepseek/deepseek-r1:free",
    #         messages=[
    #             {"role": "system", "content": "You are a concise, structured marketing assistant."},
    #             {"role": "user", "content": prompt}
    #         ],
    #         max_tokens=200,
    #         temperature=0.0  # low randomness
    #     )

    #     raw_output = completion.choices[0].message.content.strip()


    # try:
    #     raw_output = generate_text(prompt)
    #     print("🧠 raw_output from model:", raw_output)
    # except Exception as e:
    #     print("⚠️ Error calling model:", e)
        # Fallback response if local model fails
    #     raw_output = '{"hashtags": ["#Viral", "#TrendingNow", "#SocialMedia", "#Marketing", "#Buzz"], "tip": "Post during evening peak hours."}'
    # # Extract hashtags + tip robustly
    # hashtags, ai_tip = extract_hashtags_and_tip(raw_output)

    # Render the template
    # return render_template("trendy.html", country=country, state=state, trends=hashtags, ai_tip=ai_tip)


# # ------------------ TRENDY (FINAL RESTORED VERSION) ------------------
# import re, json, html, os, requests
# from flask import render_template, request
# from dotenv import load_dotenv

# load_dotenv()

# # --- Text cleaner utility ---
# def clean_ai_text(s: str) -> str:
#     """Clean text from markdown, emojis, and junk."""
#     if not s:
#         return ""
#     s = html.unescape(s)
#     s = re.sub(r"```.*?```", " ", s, flags=re.DOTALL)
#     s = s.replace("`", " ")
#     s = re.sub(r"(\*|_){1,}", " ", s)
#     s = re.sub(r"[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\U00002600-\U000027BF]+", " ", s)
#     s = re.sub(r"[^\w#\s,-]{2,}", " ", s)
#     s = re.sub(r"\s+", " ", s).strip()
#     return s


# # --- Hashtag & Tip extractor ---
# def extract_hashtags_and_tip(raw_output: str):
#     """Extract hashtags and viral tip safely from AI output."""
#     hashtags, tip = [], ""

#     try:
#         # Try to find JSON content and parse it
#         match = re.search(r"\{.*\}", raw_output, re.DOTALL)
#         if match:
#             data = json.loads(match.group(0))
#             hashtags = data.get("hashtags", [])
#             tip = data.get("tip", "")
#     except Exception:
#         pass

#     # Fallback to regex hashtag extraction
#     if not hashtags:
#         hashtags = re.findall(r"#\w[\w-]*", raw_output)
#         hashtags = list(dict.fromkeys(hashtags))[:5]  # remove duplicates, limit 5

#     # Tip extraction heuristic
#     if not tip:
#         m = re.search(r"(?:Tip|Advice|Strategy|Suggestion)\s*[:\-]\s*(.+?)(?:\.|$)", raw_output, re.IGNORECASE)
#         if m:
#             tip = clean_ai_text(m.group(1))
#         else:
#             tip = "Post between 6–9 PM local time using 3–5 relevant hashtags."

#     if not hashtags:
#         hashtags = ["#Viral", "#TrendingNow", "#SocialBuzz", "#MarketingTips", "#HypeUp"]

#     return hashtags, tip


# # --- Trendy route ---
# @app.route("/trendy", methods=["GET", "POST"])
# def trendy():
#     """
#     Restored and fixed 'Trendy' feature using dedicated OPENROUTER_TRENDY_API_KEY.
#     Deterministic output with strong fallback handling.
#     """
#     country = request.args.get("country", "India")
#     state = request.args.get("state", "")
#     region = state or country

#     # Strict, structured prompt
#     prompt = f"""
#     You are a precise social media growth assistant. For the region: {region},
#     produce exactly FIVE trending hashtags and one extremely short viral tip (no more than 14 words).
#     Output MUST be valid JSON only, like:
#     {{
#         "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"],
#         "tip": "one short tip here"
#     }}
#     Do not add commentary or markdown — ONLY return the JSON object.
#     """

#     raw_output = ""
#     try:
#         # 🔑 Use the dedicated Trendy API key
#         headers = {
#             "Authorization": f"Bearer {os.getenv('OPENROUTER_TRENDY_API_KEY')}",
#             "Content-Type": "application/json",
#         }

#         data = {
#             "model": "deepseek/deepseek-r1:free",
#             "messages": [
#                 {"role": "system", "content": "You are a concise, structured marketing assistant."},
#                 {"role": "user", "content": prompt},
#             ],
#             "temperature": 0.0,
#             "max_tokens": 200,
#         }

#         response = requests.post("https://openrouter.ai/api/v1/chat/completions",
#                                  headers=headers, json=data, timeout=60)
#         response.raise_for_status()

#         raw_output = response.json()["choices"][0]["message"]["content"].strip()
#         print("🧠 Raw AI output:", raw_output)

#     except Exception as e:
#         print("⚠️ Error calling model:", e)
#         raw_output = '{"hashtags": ["#Viral", "#TrendingNow", "#SocialMedia", "#Marketing", "#Buzz"], "tip": "Post during evening peak hours."}'

#     # ✅ Extract hashtags and viral tip
#     hashtags, ai_tip = extract_hashtags_and_tip(raw_output)

#     return render_template("trendy.html", country=country, state=state, trends=hashtags, ai_tip=ai_tip)

# Make sure 'json' is imported at the top of your app.py
import json

# --- UPDATED: Trendy Feature with Gemini 2.5 Pro ---
@app.route("/trendy", methods=["GET"]) # Changed to GET to match the form
def trendy():
    # Get country and state from the URL parameters (from the GET form)
    country = request.args.get("country", "India")
    state = request.args.get("state", "")
    region = state or country

    hashtags = []
    ai_tip = "Submit a location to get the latest trends and AI tips."

    # Only run the API calls if a form was submitted (i.e., country is not the default initial value)
    if 'country' in request.args:
        # Check if the Gemini API is available first
        if not GENAI_AVAILABLE:
            ai_tip = "⚠️ AI service is unavailable. Check your GEMINI_API_KEY."
            hashtags = ["AI Offline"]
        else:
            # 1. Construct a strict prompt asking for JSON output
            prompt = f"""
            You are a precise social media growth assistant. For the region: {region},
            produce exactly FIVE trending hashtags and one extremely short viral tip (no more than 14 words).
            Your output MUST be a valid JSON object only, like this:
            {{
                "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"],
                "tip": "one short tip here"
            }}
            Do not add any commentary, markdown, or explanation — ONLY the JSON object.
            """
            try:
                # 2. Make the API call using the model from your .env file (gemini-2.5-pro)
                model = genai.GenerativeModel(DEFAULT_GEMINI_MODEL)
                response = model.generate_content(prompt)
                raw_output = response.text

                # 3. Parse the JSON response directly (this is simpler and more reliable)
                try:
                    data = json.loads(raw_output)
                    hashtags = data.get("hashtags", [])
                    ai_tip = data.get("tip", "")
                except json.JSONDecodeError:
                    # Fallback if the AI doesn't return perfect JSON
                    print("⚠️ AI did not return valid JSON. Using fallback parsing.")
                    hashtags = [tag.strip() for tag in raw_output.split(',') if tag.strip().startswith('#')]
                    ai_tip = "Post during peak evening hours for maximum reach."

            except Exception as e:
                print(f"Gemini Error in trendy: {e}")
                ai_tip = f"⚠️ Error generating content: {e}"
                hashtags = ["Error"]

    # 4. Render the template with the fetched data
    return render_template("trendy.html", country=country, state=state, trends=hashtags, ai_tip=ai_tip)

# ------------------ MEME/REEL RECOMMENDATION ------------------
# @app.route("/recommendations", methods=["GET", "POST"])
# def recommendations():
#     """
#     AI-powered Meme & Reel Recommendation System using DeepSeek
#     """
#     campaign_topic = request.form.get("campaign", "").strip()
#     ai_data = None

#     if not campaign_topic:
#         return render_template("recommendations.html", data=None, campaign=None)

#     try:
#         # 🔹 AI Prompt
#         prompt = f"""
#         You are a professional social media strategist.
#         Suggest viral ideas for memes, reels, and hashtags for a campaign about "{campaign_topic}".
#         Provide JSON output in this exact structure only:
#         {{
#           "memes": ["Meme idea 1", "Meme idea 2", "Meme idea 3"],
#           "reels": ["Reel idea 1", "Reel idea 2", "Reel idea 3"],
#           "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
#           "best_time": "Best posting time for viral reach",
#           "tip": "One short expert viral strategy tip"
#         }}
#         Keep your ideas creative, short, and relevant.
#         """



        # completion = client.chat.completions.create(
        #     model="deepseek/deepseek-r1:free",
        #     messages=[
        #         {"role": "system", "content": "You are a marketing AI that gives viral social media strategies."},
        #         {"role": "user", "content": prompt}
        #     ],
        #     temperature=0.7,
        #     max_tokens=500
        # )

        # raw_output = completion.choices[0].message.content.strip()
        # raw_output = generate_text(prompt)


    #     import json, re
    #     match = re.search(r"\{.*\}", raw_output, re.DOTALL)
    #     if match:
    #         ai_data = json.loads(match.group())
    #     else:
    #         raise ValueError("Invalid AI output format")

    # except Exception as e:
    #     print("⚠️ AI Recommendation Error:", e)
    #     ai_data = {
    #         "memes": [
    #             "Relatable before/after meme",
    #             "Screenshot of customer reaction meme",
    #             "Funny reaction mashup"
    #         ],
    #         "reels": [
    #             "Behind-the-scenes video",
    #             "Trend remix with voiceover",
    #             "Fast tutorial with trending audio"
    #         ],
    #         "hashtags": ["#Viral", "#TrendingNow", "#SocialMediaBuzz", "#MarketingTrend"],
    #         "best_time": "6–9 PM local time",
    #         "tip": "Keep the first 2 seconds engaging — start with emotion or humor."
    #     }

    # return render_template("recommendations.html", campaign=campaign_topic, data=ai_data)


from utils.ai_connectors import generate_text, fetch_youtube_trends
import re, json

@app.route("/recommendations", methods=["GET", "POST"])
def recommendations():
    campaign_topic = request.form.get("campaign", "").strip()
    ai_data = None

    if not campaign_topic:
        return render_template("recommendations.html", data=None, campaign=None)

    # Step 1️⃣: Fetch YouTube trends via SerpAPI
    video_titles = fetch_youtube_trends(campaign_topic)
    print("🎥 YouTube results:", video_titles)

    # Step 2️⃣: Create prompt for DeepSeek/OpenRouter
    prompt = f"""
    You are a social media expert specializing in digital marketing.
    Based on these trending YouTube topics:
    {', '.join(video_titles) or campaign_topic}

    Suggest creative ideas in the following exact JSON format only:
    {{
      "memes": ["idea1", "idea2", "idea3"],
      "reels": ["idea1", "idea2", "idea3"],
      "hashtags": ["#tag1", "#tag2", "#tag3"],
      "best_time": "time to post",
      "tip": "short viral posting tip"
    }}
    """

    # Step 3️⃣: Call AI via OpenRouter (with “recommendation” context)
    raw_output = generate_text(prompt, context="recommendation")
    print("🧠 Raw AI output:", raw_output)

    # Step 4️⃣: Try to extract JSON safely
    try:
        match = re.search(r"\{.*\}", raw_output, re.DOTALL)
        if match:
            ai_data = json.loads(match.group())
        else:
            raise ValueError("No JSON object found in AI response")

    except Exception as e:
        print("⚠️ JSON parse error:", e)
        # Safe fallback data
        ai_data = {
            "memes": [
                "When analytics show 0 views but your mom liked it ❤️",
                "POV: Your campaign finally goes viral 🎯",
                "Me waiting for engagement after posting at 3 AM ⏰"
            ],
            "reels": [
                "Mini tutorial using trending audio",
                "BTS reel showing your creative process",
                "Before/After reel of campaign success"
            ],
            "hashtags": ["#MarketingHumor", "#RelatableReels", "#Viral2025", "#ContentKing", "#DigitalHype"],
            "best_time": "6–9 PM local time",
            "tip": "Mix humor and relatability with trending sounds to maximize reach."
        }

    return render_template("recommendations.html", campaign=campaign_topic, data=ai_data)


# ------------------ VIDEO EDITOR ------------------
# @app.route("/video_editor", methods=["GET", "POST"])
# def video_editor():
#     if request.method == "POST":
#         action = request.form.get("action")

#         uploaded_files = request.files.getlist("videos")
#         if not uploaded_files:
#             return render_template("video_editor.html", message="⚠️ No video uploaded!")

#         clips = []
#         temp_dir = tempfile.mkdtemp()

#         for file in uploaded_files:
#             file_path = os.path.join(temp_dir, file.filename)
#             file.save(file_path)
#             clips.append(VideoFileClip(file_path))

#         try:
#             start_time = float(request.form.get("start_time") or 0)
#             end_time = float(request.form.get("end_time") or 0)
#         except ValueError:
#             start_time, end_time = 0, 0

#         result = None

#         if action == "trim":
#             trimmed_clips = [
#                 clip.subclip(start_time, end_time if end_time > start_time else clip.duration)
#                 for clip in clips
#             ]
#             result = trimmed_clips[0] if len(trimmed_clips) == 1 else concatenate_videoclips(trimmed_clips)

#         elif action == "merge":
#             result = concatenate_videoclips(clips)

#         if result:
#             output_path = os.path.join(temp_dir, "output.mp4")
#             result.write_videofile(output_path, codec="libx264", audio_codec="aac")
#             return send_file(output_path, as_attachment=True, download_name="edited_video.mp4")

#     return render_template("video_editor.html")


# @app.route("/download_video")
# def download_video():
#     temp_path = os.path.join(tempfile.gettempdir(), "merged_video.mp4")
#     if os.path.exists(temp_path):
#         return send_file(temp_path, as_attachment=False)
#     return "No video found.", 404

# ------------------ VIDEO EDITOR (Frontend) ------------------
import os
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, TextClip, CompositeVideoClip
import tempfile

# Ensure uploads folder exists
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/video_editor", methods=["GET", "POST"])
def video_editor():
    # List available uploaded videos
    video_files = [f for f in os.listdir(app.config["UPLOAD_FOLDER"]) if f.endswith(".mp4")]
    audio_files = [f for f in os.listdir(app.config["UPLOAD_FOLDER"]) if f.endswith(".mp3")]
    return render_template("video_editor.html", videos=video_files, audios=audio_files)


# ------------------ UPLOAD ------------------
@app.route("/upload_video", methods=["POST"])
def upload_video():
    file = request.files.get("video")
    if not file:
        flash("⚠️ No video file selected.", "error")
        return redirect(url_for("video_editor"))

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)
    flash(f"✅ Uploaded successfully: {file.filename}", "success")
    return redirect(url_for("video_editor"))


# ------------------ TRIM ------------------
@app.route("/trim", methods=["POST"])
def trim_video():
    video_name = request.form.get("video")
    start = request.form.get("start")
    end = request.form.get("end")

    try:
        start = float(start)
        end = float(end)
    except:
        flash("⚠️ Invalid start or end time!", "error")
        return redirect(url_for("video_editor"))

    video_path = os.path.join(app.config["UPLOAD_FOLDER"], video_name)
    if not os.path.exists(video_path):
        flash("⚠️ Video not found!", "error")
        return redirect(url_for("video_editor"))

    output_path = os.path.join(app.config["UPLOAD_FOLDER"], f"trimmed_{video_name}")
    with VideoFileClip(video_path) as clip:
        new_clip = clip.subclip(start, end)
        new_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")

    flash(f"🎬 Trimmed video saved as trimmed_{video_name}", "success")
    return send_file(output_path, as_attachment=True)


# ------------------ MERGE ------------------
@app.route("/merge", methods=["POST"])
def merge_videos():
    video_files = request.form.get("videos")
    if not video_files:
        flash("⚠️ Enter video filenames separated by commas.", "error")
        return redirect(url_for("video_editor"))

    paths = [os.path.join(app.config["UPLOAD_FOLDER"], v.strip()) for v in video_files.split(",")]
    clips = [VideoFileClip(p) for p in paths if os.path.exists(p)]

    if not clips:
        flash("⚠️ No valid videos found!", "error")
        return redirect(url_for("video_editor"))

    output_path = os.path.join(app.config["UPLOAD_FOLDER"], "merged_video.mp4")
    final = concatenate_videoclips(clips)
    final.write_videofile(output_path, codec="libx264", audio_codec="aac")

    flash("✅ Videos merged successfully!", "success")
    return send_file(output_path, as_attachment=True)


# ------------------ ADD TEXT ------------------
@app.route("/add_text", methods=["POST"])
def add_text():
    video_name = request.form.get("video")
    text = request.form.get("text")

    video_path = os.path.join(app.config["UPLOAD_FOLDER"], video_name)
    if not os.path.exists(video_path):
        flash("⚠️ Video not found!", "error")
        return redirect(url_for("video_editor"))

    output_path = os.path.join(app.config["UPLOAD_FOLDER"], f"text_{video_name}")
    with VideoFileClip(video_path) as clip:
        txt_clip = TextClip(text, fontsize=50, color='white', font='Arial-Bold')
        txt_clip = txt_clip.set_position('center').set_duration(clip.duration)
        final = CompositeVideoClip([clip, txt_clip])
        final.write_videofile(output_path, codec="libx264", audio_codec="aac")

    flash(f"✅ Text added successfully to {video_name}", "success")
    return send_file(output_path, as_attachment=True)


# ------------------ ADD AUDIO ------------------
@app.route("/add_audio", methods=["POST"])
def add_audio():
    video_name = request.form.get("video")
    audio_name = request.form.get("audio")

    video_path = os.path.join(app.config["UPLOAD_FOLDER"], video_name)
    audio_path = os.path.join(app.config["UPLOAD_FOLDER"], audio_name)
    if not os.path.exists(video_path) or not os.path.exists(audio_path):
        flash("⚠️ Video or audio file not found!", "error")
        return redirect(url_for("video_editor"))

    output_path = os.path.join(app.config["UPLOAD_FOLDER"], f"mixed_{video_name}")
    with VideoFileClip(video_path) as clip:
        audio_clip = AudioFileClip(audio_path)
        final = clip.set_audio(audio_clip)
        final.write_videofile(output_path, codec="libx264", audio_codec="aac")

    flash("🎧 Audio added successfully!", "success")
    return send_file(output_path, as_attachment=True)




if __name__ == "__main__":
    if not os.path.exists(DATABASE_FILE):
        init_db()
    print(f"📂 Database ready at: {os.path.abspath(DATABASE_FILE)}")
    app.run(debug=True)
