# 🎬 OneClick Video Downloader

A beautiful, production-ready web app that downloads videos from **1000+ sites** (YouTube, Vimeo, TikTok, Instagram, Twitter/X, Facebook, Reddit, and more) in the highest available quality.

**Stack:** Python · Flask · yt-dlp · FFmpeg · Vanilla JS

---

## ✨ Features

- 🎯 **Paste & Download** — paste any public video URL, it downloads immediately
- 🔥 **Highest quality auto-selected** — 4K, 1080p, 720p — best available
- 🎵 **FFmpeg muxing** — merges separate video + audio streams into one file
- 📊 **Live progress bar** — real-time updates via Server-Sent Events
- 🎨 **Beautiful UI** — dark/light mode, fully responsive, works on mobile
- 🗑️ **Auto cleanup** — temp files deleted 2 minutes after download
- 📦 **Formats:** MP4, MP3, AAC, WebM

---

## 🚀 Quick Start (3 ways)

### Option 1 — Docker (recommended, works anywhere)

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/oneclick-video-downloader.git
cd oneclick-video-downloader

# 2. Start with Docker Compose
docker compose up --build

# 3. Open your browser
# http://localhost:5000
```

### Option 2 — Run locally (Python)

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/oneclick-video-downloader.git
cd oneclick-video-downloader

# 2. Install FFmpeg
#    macOS:   brew install ffmpeg
#    Ubuntu:  sudo apt install ffmpeg
#    Windows: https://ffmpeg.org/download.html (add to PATH)

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Run
python app.py

# 6. Open http://localhost:5000
```

### Option 3 — Deploy to Render (free, public URL)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New → Web Service**
3. Connect your GitHub repo
4. Render auto-detects the `render.yaml` config
5. Click **Deploy** — you get a live HTTPS URL in ~3 minutes

---

## 📁 Project Structure

```
oneclick-video-downloader/
├── app.py                 # Flask backend — all API routes
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker image (Python + FFmpeg)
├── docker-compose.yml     # One-command local setup
├── Procfile               # Railway / Heroku deployment
├── render.yaml            # Render.com deployment config
├── .env.example           # Environment variable template
├── .gitignore
├── README.md
└── static/
    └── index.html         # Frontend (HTML + CSS + JS)
```

---

## 🔌 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | — | Serves the web UI |
| `GET /api/health` | — | Health check |
| `GET /api/info?url=...` | GET | Fetch video metadata (title, thumbnail, duration, resolution) |
| `POST /api/download` | POST | Start a download job → returns `{job_id}` |
| `GET /api/progress/:job_id` | SSE | Stream live progress updates |
| `GET /api/file/:job_id` | GET | Download the finished file |

**POST /api/download body:**
```json
{
  "url": "https://youtube.com/watch?v=...",
  "format": "mp4"
}
```
Supported formats: `mp4` `mp3` `aac` `webm`

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5000` | Server port |
| `FLASK_ENV` | `production` | `development` enables debug mode |
| `DOWNLOAD_DIR` | `/tmp` | Where temp files are stored |

---

## 🛠️ How It Works

```
User pastes URL
     ↓
GET /api/info  →  yt-dlp extracts metadata (title, thumbnail, resolution)
     ↓
POST /api/download  →  background thread starts
     ↓
GET /api/progress/:id  →  SSE stream (0% → 100%)
     ↓
yt-dlp downloads best video stream + best audio stream separately
     ↓
FFmpeg muxes them into a single MP4 file
     ↓
GET /api/file/:id  →  Flask streams file to browser
     ↓
Server deletes temp file after 2 minutes
```

---

## ⚠️ Legal

This tool is for **personal use only** — archiving public videos you have rights to.  
Do not use this to download copyrighted content you don't own.  
Users are solely responsible for compliance with applicable laws and platform terms of service.

---

## 🧰 Built With

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — video extraction engine
- [FFmpeg](https://ffmpeg.org) — video/audio muxing
- [Flask](https://flask.palletsprojects.com) — Python web framework
- [Syne](https://fonts.google.com/specimen/Syne) + [Space Mono](https://fonts.google.com/specimen/Space+Mono) — fonts
