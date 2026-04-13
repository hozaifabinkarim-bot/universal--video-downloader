"""
OneClick Video Downloader — Backend
Flask + yt-dlp + FFmpeg
"""

import os
import uuid
import json
import time
import threading
import tempfile
import re
import shutil

from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
import yt_dlp

# ─────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", tempfile.gettempdir())

# In-memory job store  {job_id: {...}}
jobs: dict = {}
jobs_lock = threading.Lock()


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def safe_filename(title: str) -> str:
    s = re.sub(r"[^\w\s\-]", "", title or "video")
    s = re.sub(r"\s+", "_", s.strip())
    return s[:80] or "video"


def human_size(b: int | None) -> str:
    if not b:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def best_resolution_label(formats: list) -> str:
    heights = [f.get("height") or 0 for f in formats]
    h = max(heights, default=0)
    if h >= 2160:
        return "4K"
    if h >= 1440:
        return "1440p"
    if h >= 1080:
        return "1080p"
    if h >= 720:
        return "720p"
    if h > 0:
        return f"{h}p"
    return "Unknown"


# ─────────────────────────────────────────────
# yt-dlp options builder
# ─────────────────────────────────────────────
def build_ydl_opts(fmt: str, out_dir: str, job_id: str) -> dict:

    def hook(d):
        with jobs_lock:
            if job_id not in jobs:
                return
            status = d.get("status")
            if status == "downloading":
                total   = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done    = d.get("downloaded_bytes") or 0
                speed   = d.get("speed") or 0
                pct     = (done / total * 80) if total > 0 else 0   # 0-80 %
                jobs[job_id].update(
                    progress=round(min(pct, 80), 1),
                    stage="downloading",
                    speed=round(speed / 1024, 1),          # KB/s
                    downloaded=done,
                    total_bytes=total,
                )
            elif status == "finished":
                jobs[job_id].update(progress=88, stage="muxing")

    common = {
        "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ignoreerrors": False,
        "geo_bypass": True,
    }

    if fmt in ("mp3", "aac"):
        common.update(
            format="bestaudio/best",
            postprocessors=[
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": fmt,
                    "preferredquality": "0",
                }
            ],
        )
    elif fmt == "webm":
        common.update(
            format="bestvideo[ext=webm]+bestaudio[ext=webm]/bestvideo+bestaudio/best",
            merge_output_format="webm",
        )
    else:   # mp4 (default)
        common.update(
            format="bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            merge_output_format="mp4",
        )

    return common


# ─────────────────────────────────────────────
# Background download worker
# ─────────────────────────────────────────────
def do_download(job_id: str, url: str, fmt: str):
    tmp_dir = tempfile.mkdtemp(prefix="oneclick_")

    def fail(msg: str):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        with jobs_lock:
            jobs[job_id].update(status="error", error=msg, progress=0)

    try:
        with jobs_lock:
            jobs[job_id].update(stage="fetching", progress=5)

        opts = build_ydl_opts(fmt, tmp_dir, job_id)

        with jobs_lock:
            jobs[job_id].update(stage="analyzing", progress=12)

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Find downloaded file
        files = [f for f in os.listdir(tmp_dir) if not f.endswith(".part")]
        if not files:
            return fail("Download completed but no output file was found.")

        # Pick the biggest file (the merged one)
        files.sort(key=lambda f: os.path.getsize(os.path.join(tmp_dir, f)), reverse=True)
        filename = files[0]
        filepath = os.path.join(tmp_dir, filename)

        with jobs_lock:
            jobs[job_id].update(
                status="done",
                progress=100,
                stage="ready",
                file_path=filepath,
                tmp_dir=tmp_dir,
                filename=filename,
                title=info.get("title", "video"),
                filesize=human_size(os.path.getsize(filepath)),
            )

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "private" in msg.lower():
            msg = "This video is private or age-restricted and cannot be downloaded."
        elif "not available" in msg.lower():
            msg = "This video is unavailable in your region or has been removed."
        elif "unsupported url" in msg.lower():
            msg = "This URL is not supported. Please try a direct video link."
        else:
            msg = f"Download failed: {msg[:200]}"
        fail(msg)

    except Exception as e:
        fail(f"Unexpected error: {str(e)[:200]}")


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": "2.0.0"})


@app.route("/api/info")
def api_info():
    """Fetch video metadata without downloading."""
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "url param is required"}), 400

    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats   = info.get("formats") or []
        duration  = info.get("duration") or 0
        mins, sec = divmod(int(duration), 60)

        # Rough file-size estimate from best video + best audio
        vid_size = max((f.get("filesize") or 0 for f in formats if f.get("vcodec") != "none"), default=0)
        aud_size = max((f.get("filesize") or 0 for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"), default=0)
        est_bytes = (vid_size + aud_size) or None

        return jsonify(
            {
                "title":      info.get("title", "Unknown"),
                "thumbnail":  info.get("thumbnail", ""),
                "duration":   f"{mins}:{sec:02d}",
                "resolution": best_resolution_label(formats),
                "uploader":   info.get("uploader", ""),
                "platform":   info.get("extractor_key", "Unknown"),
                "filesize":   human_size(est_bytes),
                "filesize_bytes": est_bytes,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)[:300]}), 400


@app.route("/api/download", methods=["POST"])
def api_download():
    """Start a download job. Returns job_id immediately."""
    data = request.get_json(silent=True) or {}
    url  = (data.get("url") or "").strip()
    fmt  = (data.get("format") or "mp4").lower()

    if not url:
        return jsonify({"error": "url is required"}), 400
    if fmt not in ("mp4", "mp3", "aac", "webm"):
        fmt = "mp4"

    job_id = str(uuid.uuid4())

    with jobs_lock:
        jobs[job_id] = {
            "status":      "processing",
            "progress":    0,
            "stage":       "starting",
            "error":       None,
            "filename":    None,
            "file_path":   None,
            "title":       None,
            "filesize":    None,
            "speed":       0,
            "downloaded":  0,
            "total_bytes": 0,
        }

    t = threading.Thread(target=do_download, args=(job_id, url, fmt), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/api/progress/<job_id>")
def api_progress(job_id: str):
    """Server-Sent Events stream for live download progress."""

    def stream():
        deadline = time.time() + 600   # 10-minute hard timeout
        last_hash = None

        while time.time() < deadline:
            with jobs_lock:
                job = jobs.get(job_id)

            if job is None:
                yield f'data: {json.dumps({"status":"error","error":"Job not found"})}\n\n'
                return

            # Exclude internal paths from SSE payload
            payload = {k: v for k, v in job.items()
                       if k not in ("file_path", "tmp_dir")}

            h = json.dumps(payload, sort_keys=True)
            if h != last_hash:
                yield f"data: {h}\n\n"
                last_hash = h

            if job.get("status") in ("done", "error"):
                return

            time.sleep(0.25)

        yield f'data: {json.dumps({"status":"error","error":"Timeout"})}\n\n'

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":      "keep-alive",
        },
    )


@app.route("/api/file/<job_id>")
def api_file(job_id: str):
    """Stream the finished file to the client, then clean up."""
    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job.get("status") != "done":
        return jsonify({"error": "File not ready yet"}), 202

    filepath = job.get("file_path")
    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "File missing on server"}), 404

    filename = job.get("filename", "video.mp4")
    tmp_dir  = job.get("tmp_dir")

    # Schedule cleanup 2 min after serving
    def cleanup():
        time.sleep(120)
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        with jobs_lock:
            jobs.pop(job_id, None)

    threading.Thread(target=cleanup, daemon=True).start()

    return send_file(filepath, as_attachment=True, download_name=filename)


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    print(f"🎬 OneClick Video Downloader running on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
