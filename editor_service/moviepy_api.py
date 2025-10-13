# editor_service/moviepy_api.py
from flask import Flask, request, jsonify, send_from_directory
from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, vfx
)
from werkzeug.utils import secure_filename
import os, uuid

app = Flask(__name__)

VIDEO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "videos"))
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
    filename = secure_filename(file.filename)
    file_path = safe_path(filename)
    file.save(file_path)
    return jsonify({"message": "Uploaded successfully", "filename": filename}), 200

@app.route("/trim", methods=["POST"])
def trim_video():
    filename = request.form["filename"]
    start = float(request.form.get("start", 0))
    end = float(request.form.get("end", 0))
    clip = VideoFileClip(safe_path(filename)).subclip(start, end)
    out = new_output("trim")
    clip.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
    clip.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/merge", methods=["POST"])
def merge_videos():
    files = request.form.getlist("filenames")
    clips = [VideoFileClip(safe_path(f)) for f in files]
    final = concatenate_videoclips(clips, method="compose")
    out = new_output("merge")
    final.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
    for c in clips: c.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/add_text", methods=["POST"])
def add_text():
    filename = request.form["filename"]
    text = request.form["text"]
    fontsize = int(request.form.get("fontsize", 40))
    color = request.form.get("color", "white")
    clip = VideoFileClip(safe_path(filename))
    txt = TextClip(text, fontsize=fontsize, color=color).set_duration(clip.duration)
    final = CompositeVideoClip([clip, txt.set_pos(("center", "bottom"))])
    out = new_output("text")
    final.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
    clip.close(); final.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/add_audio", methods=["POST"])
def add_audio():
    filename = request.form["filename"]
    audiofile = request.form["audiofile"]
    volume = float(request.form.get("volume", 1.0))
    clip = VideoFileClip(safe_path(filename))
    audioclip = AudioFileClip(safe_path(audiofile)).volumex(volume)
    final = clip.set_audio(audioclip)
    out = new_output("audio")
    final.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
    clip.close(); audioclip.close(); final.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/change_speed", methods=["POST"])
def change_speed():
    filename = request.form["filename"]
    factor = float(request.form["factor"])
    clip = VideoFileClip(safe_path(filename)).fx(vfx.speedx, factor)
    out = new_output("speed")
    clip.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
    clip.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/thumbnail", methods=["POST"])
def thumbnail():
    filename = request.form["filename"]
    t = float(request.form.get("time", 1))
    clip = VideoFileClip(safe_path(filename))
    out = new_output("thumb", ".png")
    clip.save_frame(out, t)
    clip.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/crop_resize", methods=["POST"])
def crop_resize():
    filename = request.form["filename"]
    x1 = int(request.form["x1"]); y1 = int(request.form["y1"])
    x2 = int(request.form["x2"]); y2 = int(request.form["y2"])
    width = int(request.form.get("width", 720))
    height = int(request.form.get("height", 720))
    clip = VideoFileClip(safe_path(filename)).crop(x1=x1, y1=y1, x2=x2, y2=y2).resize((width, height))
    out = new_output("crop")
    clip.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
    clip.close()
    return jsonify({"output": os.path.basename(out)})

@app.route("/download/<filename>", methods=["GET"])
def download(filename):
    return send_from_directory(VIDEO_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(port=9000)
