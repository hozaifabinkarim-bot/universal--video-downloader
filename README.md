# 🎬 OneClick Video Downloader

Download videos from 1000+ sites (YouTube, TikTok, Instagram, Vimeo, Twitter/X, and more)
in the highest available quality. Real backend with yt-dlp + FFmpeg.

---

## ⚠️ GitHub Pages Users — Read This First

**GitHub Pages only serves static HTML. It cannot run Python.**

If you see `"Unexpected token '<'"` or `"Network error"` — that's because the
Python backend isn't running.

**You have two options:**

### Option A — Deploy Everything to Render (Recommended, FREE)
Deploy the full app (frontend + backend) to Render.com.
You get a real HTTPS URL that works. See [Deploy to Render](#deploy-to-render) below.

### Option B — Keep GitHub Pages + Deploy Backend Separately
1. Deploy the backend to Render → you get `https://your-app.onrender.com`
2. Open the app on GitHub Pages
3. The yellow banner at the top says "Backend not connected"
4. Enter your Render URL there and click **Connect**
5. It saves the URL in your browser — works from then on

---

## 🚀 Running Locally (Development)

### Step 1 — Install FFmpeg

| OS | Command |
|---|---|
| macOS | `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt install ffmpeg` |
| Windows | Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH |

### Step 2 — Install Python Dependencies

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/oneclick-video-downloader.git
cd oneclick-video-downloader

# Create virtual environment
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3 — Run

```bash
python app.py
# Open http://localhost:5000
```

---

## 🐳 Running with Docker (Easiest)

```bash
# Build and run everything (FFmpeg is installed automatically)
docker compose up --build

# Open http://localhost:5000
```

---

## Deploy to Render

Render.com offers **free hosting** with Docker support.

1. Push this repo to GitHub (make sure all files are included)
2. Go to [render.com](https://render.com) → Sign up (free)
3. Click **New → Web Service**
4. Connect your GitHub repo
5. Render detects `render.yaml` automatically
6. Click **Deploy** → wait ~3 minutes
7. Your app is live at `https://your-app-name.onrender.com`

> **Note:** Free tier "sleeps" after 15 min of inactivity. First request after sleep
> takes ~30 seconds to wake up. Upgrade to paid tier to avoid this.

---

## Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

---

## 📁 File Structure

```
oneclick-video-downloader/
├── app.py                ← Flask backend (all API routes)
├── requirements.txt      ← Python packages
├── Dockerfile            ← Python 3.11 + FFmpeg
├── docker-compose.yml    ← One-command local setup
├── Procfile              ← Railway / Heroku
├── render.yaml           ← Render.com config
├── .gitignore
├── README.md
└── static/
    └── index.html        ← Frontend (self-contained, works anywhere)
```

---

## 🔌 API

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | — | Frontend UI |
| `GET /api/health` | GET | Health check → `{"status":"ok"}` |
| `GET /api/info?url=...` | GET | Fetch video metadata |
| `POST /api/download` | POST | Start download → `{"job_id":"..."}` |
| `GET /api/progress/:id` | SSE | Live progress stream |
| `GET /api/file/:id` | GET | Download finished file |

---

## 🔧 Troubleshooting

| Error | Fix |
|---|---|
| `Unexpected token '<'` | Backend not running. Deploy to Render or run locally |
| `Cannot reach backend` | Check the URL in the banner. Make sure it's `https://` not `http://` |
| `Failed to fetch info` | Video may be private, age-restricted, or region-locked |
| `No file was created` | yt-dlp format issue — try a different format (MP3 vs MP4) |
| Download takes >60s | Normal for long videos. Free Render tier also adds latency |
| `yt-dlp` errors on YouTube | Run `pip install -U yt-dlp` to update (YouTube changes frequently) |

---

## ⚠️ Legal

Personal use only. Do not download copyrighted content without permission.
Users are solely responsible for compliance with applicable laws.
