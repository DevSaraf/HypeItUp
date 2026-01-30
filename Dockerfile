# Use Python 3.11
FROM python:3.11-slim

# 1. Install System Dependencies
# We NEED imagemagick for TextClip and ffmpeg for video processing
RUN apt-get update && apt-get install -y \
    imagemagick \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 2. Fix ImageMagick Policy (Crucial for MoviePy TextClip)
# This allows the app to read/write text on images
RUN sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/g' /etc/ImageMagick-6/policy.xml || true

# 3. Set Working Directory
WORKDIR /app

# 4. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy Your Entire App (Templates, app.py, etc.)
COPY . .

# 6. Create Uploads Directory to prevent errors
RUN mkdir -p uploads

# 7. Run the Flask App with Gunicorn
# Render expects the app to listen on port 10000
CMD gunicorn app:app --bind 0.0.0.0:10000