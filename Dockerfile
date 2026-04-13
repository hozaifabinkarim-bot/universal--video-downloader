# ─────────────────────────────────────────────────────────
#  OneClick Video Downloader — Dockerfile
#  Python 3.11-slim + FFmpeg + yt-dlp
# ─────────────────────────────────────────────────────────
FROM python:3.11-slim

# Install FFmpeg (required for muxing video + audio streams)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Run with gunicorn in production (threaded for concurrent downloads)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "600", "app:app"]
