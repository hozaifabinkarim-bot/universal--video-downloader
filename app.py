"""
OneClick Video Downloader — Backend v2.0.0
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

# Allow ALL origins (required when frontend is on GitHub Pages / different domain)
CORS(app, resources={r"/api/*": {"origins": "*"}},
     supports_credentials=False,
     allow_headers=["Content-Type", "Accept"],
     methods=["GET", "POST", "OPTIONS"])

# Jobs store: {job_id: {...state...}}
jobs: dict = {}
jobs_lock  = threading.Lock()

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def human_size(b) -> str:
    if not b:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def best_resolution(formats: list) -> str:
    heights = [f.get("height") or 0 for f in (formats or [])]
    h = max(heights, default=0)
    if h >= 2160: return "4K"
    if h >= 1440: return "1440p"
    if h >= 1080: return "1080p"
    if h >= 720:  return "720p"
    if h > 0:     return f"{h}p"
    return "Unknown"


def clean_error(msg: str) -> str:
    """Turn raw yt-dlp errors into user-friendly messages."""
    m = msg.lower()
    if "private" in m:
        return "This video is private or age-restricted and cannot be downloaded."
    if "not available" in m or "unavailable" in m:
        return "This video is unavailable in your region or has been removed."
    if "unsupported url" in m:
        return "This URL is not supported. Please try a direct video link."
    if "sign in" in m or "login" in m:
        return "This video requires a login to access and cannot be downloaded."
    if "copyright" in m:
        return "This video is blocked due to copyright restrictions."
    if "live" in m and "stream" in m:
        return "Live streams cannot be downloaded while they are broadcasting."
    if "no video formats" in m:
        return "No downloadable video formats found for this URL."
    # Trim raw technical output
    if len(msg) > 250:
        msg = msg[:247] + "…"
    return msg


# ─────────────────────────────────────────────
# yt-dlp options
# ─────────────────────────────────────────────
def build_ydl_opts(fmt: str, out_dir: str, job_id: str) -> dict:

    def hook(d):
        with jobs_lock:
            if job_id not in jobs:
                return
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done  = d.get("downloaded_bytes") or 0
                speed = d.get("speed") or 0
                pct   = (done / total * 80) if total > 0 else 0
                jobs[job_id].update(
                    progress=round(min(pct, 80), 1),
                    stage="downloading",
                    speed=round(speed / 1024, 1),
                    downloaded=done,
                    total_bytes=total,
                )
            elif status == "finished":
                jobs[job_id].update(progress=88, stage="muxing")

    base = {
        "outtmpl":     os.path.join(out_dir, "%(title)s.%(ext)s"),
        "progress_hooks": [hook],
        "quiet":       True,
        "no_warnings": True,
        "noplaylist":  True,
        "ignoreerrors": False,
        "geo_bypass":  True,
        "retries":     3,
        "fragment_retries": 3,
    }

    if fmt in ("mp3", "aac"):
        base.update(
            format="bestaudio/best",
            postprocessors=[{
                "key": "FFmpegExtractAudio",
                "preferredcodec": fmt,
                "preferredquality": "0",
            }],
        )
    elif fmt == "webm":
        base.update(
            format="bestvideo[ext=webm]+bestaudio[ext=webm]/bestvideo+bestaudio/best",
            merge_output_format="webm",
        )
    else:  # mp4
        base.update(
            format="bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            merge_output_format="mp4",
        )

    return base


# ─────────────────────────────────────────────
# Background worker
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

        if not info:
            return fail("yt-dlp returned no information. The URL may be unsupported.")

        # Find the output file (pick largest, skip .part files)
        files = [f for f in os.listdir(tmp_dir)
                 if not f.endswith(".part") and not f.endswith(".ytdl")]
        if not files:
            return fail("Download completed but no output file was created.")

        files.sort(key=lambda f: os.path.getsize(os.path.join(tmp_dir, f)), reverse=True)
        filename = files[0]
        filepath = os.path.join(tmp_dir, filename)
        size     = os.path.getsize(filepath)

        with jobs_lock:
            jobs[job_id].update(
                status="done",
                progress=100,
                stage="ready",
                file_path=filepath,
                tmp_dir=tmp_dir,
                filename=filename,
                title=info.get("title", "video"),
                filesize=human_size(size),
            )

    except yt_dlp.utils.DownloadError as e:
        fail(clean_error(str(e)))
    except Exception as e:
        fail(f"Unexpected error: {clean_error(str(e))}")


# ─────────────────────────────────────────────
# CORS preflight handler (explicit OPTIONS support)
# ─────────────────────────────────────────────
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
    return response


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
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "url param is required"}), 400

    try:
        opts = {
            "quiet":       True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist":  True,
            "geo_bypass":  True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return jsonify({"error": "Could not extract info from this URL"}), 400

        formats  = info.get("formats") or []
        duration = info.get("duration") or 0
        mins, sec = divmod(int(duration), 60)

        # Estimate combined file size
        vid_size = max((f.get("filesize") or 0 for f in formats
                        if f.get("vcodec") not in (None, "none")
                        and f.get("acodec") in (None, "none")), default=0)
        aud_size = max((f.get("filesize") or 0 for f in formats
                        if f.get("acodec") not in (None, "none")
                        and f.get("vcodec") in (None, "none")), default=0)
        est_bytes = (vid_size + aud_size) or None

        return jsonify({
            "title":          info.get("title", "Unknown"),
            "thumbnail":      info.get("thumbnail", ""),
            "duration":       f"{mins}:{sec:02d}",
            "resolution":     best_resolution(formats),
            "uploader":       info.get("uploader", ""),
            "platform":       info.get("extractor_key", "Unknown"),
            "filesize":       human_size(est_bytes),
            "filesize_bytes": est_bytes,
        })

    except yt_dlp.utils.DownloadError as e:
        return jsonify({"error": clean_error(str(e))}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to fetch info: {clean_error(str(e))}"}), 500


@app.route("/api/download", methods=["POST", "OPTIONS"])
def api_download():
    if request.method == "OPTIONS":
        return "", 204

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
    def stream():
        deadline  = time.time() + 600
        last_hash = None

        while time.time() < deadline:
            with jobs_lock:
                job = jobs.get(job_id)

            if job is None:
                yield f'data: {json.dumps({"status":"error","error":"Job not found"})}\n\n'
                return

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
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


@app.route("/api/file/<job_id>")
def api_file(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job.get("status") != "done":
        return jsonify({"error": "File not ready yet"}), 202

    filepath = job.get("file_path")
    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "File missing on server — it may have been cleaned up"}), 404

    filename = job.get("filename", "video.mp4")
    tmp_dir  = job.get("tmp_dir")

    # Clean up after 2 minutes
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
    print(f"\n🎬  OneClick Video Downloader")
    print(f"    Running → http://0.0.0.0:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
