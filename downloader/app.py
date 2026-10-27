"""Microservicio de descarga.

Recibe un link de TikTok (perfil o video) y ejecuta yt-dlp en segundo plano.
n8n inicia el trabajo con POST /download y lo consulta con GET /status/<job_id>.
"""
import os
import re
import subprocess
import threading
import uuid
from collections import deque

from flask import Flask, jsonify, request

app = Flask(__name__)

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/downloads")
COOKIES_FILE = os.environ.get("COOKIES_FILE", "/config/cookies.txt")
ARCHIVE_FILE = os.path.join(DOWNLOAD_DIR, "archive.txt")

# Carpeta/nombre de cada archivo: downloads/USUARIO/FECHA_IDVIDEO.mp4
OUTPUT_TEMPLATE = os.path.join(
    DOWNLOAD_DIR, "%(uploader)s", "%(upload_date)s_%(id)s.%(ext)s"
)

# Solo se aceptan links de tiktok.com (incluye vm.tiktok.com, www.tiktok.com, etc.)
TIKTOK_URL = re.compile(r"^https?://([a-z0-9-]+\.)?tiktok\.com/", re.IGNORECASE)

# Estado de los trabajos en memoria: job_id -> diccionario
jobs = {}


def count_videos():
    """Cuenta los .mp4 que hay en la carpeta de descargas."""
    total = 0
    for _root, _dirs, files in os.walk(DOWNLOAD_DIR):
        total += sum(1 for name in files if name.lower().endswith(".mp4"))
    return total


def build_command(url):
    """Arma el comando de yt-dlp."""
    command = [
        "yt-dlp",
        url,
        # Mejor video + mejor audio disponibles (si no se puede, el mejor archivo unico)
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "-o", OUTPUT_TEMPLATE,
        "--restrict-filenames",
        # Guarda los IDs ya descargados: si repites el perfil, no duplica nada
        "--download-archive", ARCHIVE_FILE,
        "--ignore-errors",
        "--no-progress",
        # Pausas cortas entre videos para no ser bloqueado por TikTok
        "--sleep-interval", "1",
        "--max-sleep-interval", "3",
    ]
    # Si existe config/cookies.txt, se usa (ayuda cuando TikTok bloquea)
    if os.path.isfile(COOKIES_FILE):
        command += ["--cookies", COOKIES_FILE]
    return command


def run_job(job_id, url):
    """Corre yt-dlp y va actualizando el estado del trabajo."""
    job = jobs[job_id]
    try:
        process = subprocess.Popen(
            build_command(url),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            job["log"].append(line)

            item = re.search(r"Downloading item (\d+) of (\d+)", line)
            if item:
                job["current_item"] = int(item.group(1))
                job["total_items"] = int(item.group(2))
            if "has already been recorded in the archive" in line:
                job["skipped"] += 1
            if line.startswith("ERROR"):
                job["errors"] += 1

        job["exit_code"] = process.wait()
        job["status"] = "finished" if job["exit_code"] == 0 else "finished_with_errors"
    except Exception as exc:  # noqa: BLE001
        job["status"] = "error"
        job["error"] = str(exc)
    finally:
        job["videos_on_disk"] = count_videos()


def running_job_id():
    for job_id, job in jobs.items():
        if job["status"] == "running":
            return job_id
    return None


def public_view(job_id):
    job = jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "url": job["url"],
        "current_item": job["current_item"],
        "total_items": job["total_items"],
        "skipped": job["skipped"],
        "errors": job["errors"],
        "videos_on_disk": count_videos(),
        "error": job["error"],
        "last_log": list(job["log"])[-15:],
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Falta el campo 'url'"}), 400
    if not TIKTOK_URL.match(url):
        return jsonify({"error": "La URL debe ser un link de tiktok.com"}), 400

    busy = running_job_id()
    if busy:
        return jsonify({"error": "Ya hay una descarga en curso", "job_id": busy}), 409

    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {
        "status": "running",
        "url": url,
        "current_item": 0,
        "total_items": 0,
        "skipped": 0,
        "errors": 0,
        "exit_code": None,
        "error": None,
        "log": deque(maxlen=60),
    }
    threading.Thread(target=run_job, args=(job_id, url), daemon=True).start()
    return jsonify(public_view(job_id)), 202


@app.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    if job_id not in jobs:
        return jsonify({"error": "job_id no encontrado"}), 404
    return jsonify(public_view(job_id))


if __name__ == "__main__":
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, threaded=True)
