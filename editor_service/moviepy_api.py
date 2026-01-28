# editor_service/moviepy_api.py
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, vfx
)
from werkzeug.utils import secure_filename
import os, uuid

app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5000", "http://localhost:5000"])  # limit origins in production

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VIDEO_DIR = os.path.join(ROOT_DIR, "videos")
os.makedirs(VIDEO_DIR, exist_ok=True)

def safe_path(filename):
    return os.path.join(VIDEO_DIR, secure_filename(filename))

def new_output(prefix="edited", ext=".mp4"):
    return os.path.join(VIDEO_DIR, f"{prefix}_{uuid.uuid4().hex}{ext}")

@app.route("/upload", methods=["POST"])
def upload_video():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    filename = secure_filename(file.filename)
    file_path = safe_path(filename)
    file.save(file_path)
    return jsonify({"message": "Uploaded successfully", "filename": filename}), 200

@app.route("/trim", methods=["POST"])
def trim_video():
    filename = request.form.get("filename")
    if not filename:
        return jsonify({"error": "filename required"}), 400
    start = float(request.form.get("start", 0))
    end = float(request.form.get("end", 0))
    in_path = safe_path(filename)
    clip = VideoFileClip(in_path)
    try:
        sub = clip.subclip(start, end)
        out = new_output("trim")
        sub.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
        sub.close()
    finally:
        clip.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/merge", methods=["POST"])
def merge_videos():
    files = request.form.getlist("filenames")
    if not files:
        return jsonify({"error": "filenames required"}), 400
    clips = []
    try:
        for f in files:
            clips.append(VideoFileClip(safe_path(f)))
        final = concatenate_videoclips(clips, method="compose")
        out = new_output("merge")
        final.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
        final.close()
        for c in clips: c.close()
    finally:
        for c in clips:
            try: c.close()
            except: pass
    return jsonify({"output": os.path.basename(out)})

@app.route("/add_text", methods=["POST"])
def add_text():
    filename = request.form.get("filename")
    text = request.form.get("text", "")
    fontsize = int(request.form.get("fontsize", 40))
    color = request.form.get("color", "white")
    in_path = safe_path(filename)
    clip = VideoFileClip(in_path)
    try:
        try:
            txt = TextClip(text, fontsize=fontsize, color=color, font="DejaVu-Sans").set_duration(clip.duration)
        except Exception:
            txt = TextClip(text, fontsize=fontsize, color=color).set_duration(clip.duration)
        final = CompositeVideoClip([clip, txt.set_pos(("center", "bottom"))])
        out = new_output("text")
        final.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
        final.close()
    finally:
        clip.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/add_audio", methods=["POST"])
def add_audio():
    filename = request.form.get("filename")
    audiofile = request.form.get("audiofile")
    volume = float(request.form.get("volume", 1.0))
    in_path = safe_path(filename)
    clip = VideoFileClip(in_path)
    try:
        audioclip = AudioFileClip(safe_path(audiofile)).volumex(volume)
        final = clip.set_audio(audioclip)
        out = new_output("audio")
        final.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
        try: audioclip.close()
        except: pass
        try: final.close()
        except: pass
    finally:
        clip.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/change_speed", methods=["POST"])
def change_speed():
    filename = request.form.get("filename")
    factor = float(request.form.get("factor", 1.0))
    in_path = safe_path(filename)
    clip = VideoFileClip(in_path)
    try:
        sped = clip.fx(vfx.speedx, factor)
        out = new_output("speed")
        sped.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
        sped.close()
    finally:
        clip.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/thumbnail", methods=["POST"])
def thumbnail():
    filename = request.form.get("filename")
    t = float(request.form.get("time", 1))
    clip = VideoFileClip(safe_path(filename))
    try:
        out = new_output("thumb", ".png")
        clip.save_frame(out, t)
    finally:
        clip.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/crop_resize", methods=["POST"])
def crop_resize():
    filename = request.form.get("filename")
    x1 = int(request.form.get("x1", 0)); y1 = int(request.form.get("y1", 0))
    x2 = int(request.form.get("x2", 0)); y2 = int(request.form.get("y2", 0))
    width = int(request.form.get("width", 720)); height = int(request.form.get("height", 720))
    clip = VideoFileClip(safe_path(filename))
    try:
        out_clip = clip.crop(x1=x1, y1=y1, x2=x2, y2=y2).resize((width, height))
        out = new_output("crop")
        out_clip.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
        out_clip.close()
    finally:
        clip.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/download/<filename>", methods=["GET"])
def download(filename):
    safe = secure_filename(filename)
    return send_from_directory(VIDEO_DIR, safe, as_attachment=True)

if __name__ == "__main__":
    app.run(port=9000, host="0.0.0.0")
