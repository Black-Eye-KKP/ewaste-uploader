"""
Flask server - EVS E-Waste Pipeline
  POST /upload        -> validate image, forward to n8n webhook
  POST /save-report   -> save HTML report to D:\EVS\EVs\Reports
  POST /metal-prices  -> generate 12-month simulated market price data
  GET  /health        -> health check
"""

import os
import re
import json
import math
import random
import pathlib
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Config
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/ewaste")
REPORTS_FOLDER  = pathlib.Path(os.getenv("REPORTS_FOLDER", r"D:\EVS\EVs\Reports"))
UPLOAD_TMP      = pathlib.Path("./tmp_uploads")
MAX_CONTENT_MB  = 20

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "bmp"}

# Magic-byte signatures (replaces imghdr which was removed in Python 3.13)
MAGIC_SIGNATURES = [
    (b"\xff\xd8\xff",    "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a",          "gif"),
    (b"GIF89a",          "gif"),
    (b"BM",              "bmp"),
    (b"RIFF",            "webp"),
]

METAL_BASE_PRICES = {
    "Copper": 8500, "Gold": 60000, "Silver": 800, "Palladium": 40000,
    "Platinum": 30000, "Nickel": 14000, "Tin": 26000, "Lead": 2000,
    "Zinc": 2500, "Aluminium": 2200, "Iron": 120, "Cobalt": 25000,
    "Lithium": 13000, "Manganese": 2000, "Indium": 167000,
}

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
UPLOAD_TMP.mkdir(parents=True, exist_ok=True)
REPORTS_FOLDER.mkdir(parents=True, exist_ok=True)


def allowed_file(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED_EXTENSIONS


def is_real_image(filepath: str) -> bool:
    """Magic-byte check compatible with Python 3.13+ (imghdr removed)."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(16)
        for sig, kind in MAGIC_SIGNATURES:
            if header[:len(sig)] == sig:
                if kind == "webp":
                    return header[8:12] == b"WEBP"
                return True
        return False
    except Exception:
        return False


def sanitise_filename(name: str) -> str:
    name = secure_filename(name)
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name or "upload"


def generate_price_series(metal: str, days: int = 365) -> list:
    base = METAL_BASE_PRICES.get(metal, 5000)
    series = []
    today = datetime.today()
    random.seed(hash(metal) % 10000)
    price = base
    for i in range(days, -1, -1):
        date  = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        trend = base * 0.08 * math.sin(2 * math.pi * i / 365)
        noise = random.gauss(0, base * 0.005)
        price = max(base * 0.6, price + trend * 0.01 + noise)
        series.append({"date": date, "price": round(price, 2)})
    return series


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "n8n_webhook": N8N_WEBHOOK_URL,
                    "reports_folder": str(REPORTS_FOLDER)})


@app.route("/upload", methods=["POST"])
def upload():
    if request.content_length and request.content_length > MAX_CONTENT_MB * 1024 * 1024:
        return jsonify({"error": f"File too large (max {MAX_CONTENT_MB} MB)"}), 413
    if "image" not in request.files:
        return jsonify({"error": "No 'image' field in request"}), 400
    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "File extension not allowed"}), 415

    safe_name = sanitise_filename(file.filename)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    tmp_path = UPLOAD_TMP / f"{ts}_{safe_name}"
    file.save(str(tmp_path))

    if not is_real_image(str(tmp_path)):
        tmp_path.unlink(missing_ok=True)
        return jsonify({"error": "Not a real image file"}), 415

    try:
        with open(tmp_path, "rb") as img_fh:
            n8n_resp = requests.post(
                N8N_WEBHOOK_URL,
                files={"image": (safe_name, img_fh, file.content_type)},
                data={"original_name": safe_name, "timestamp": ts},
                timeout=90,
            )
        n8n_resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        tmp_path.unlink(missing_ok=True)
        return jsonify({"error": f"n8n unreachable: {exc}"}), 502

    report_path = None
    ct = n8n_resp.headers.get("Content-Type", "")
    if "text/html" in ct or n8n_resp.text.strip().startswith("<!"):
        stem = pathlib.Path(safe_name).stem
        report_name = f"{ts}_{stem}.html"
        report_path = REPORTS_FOLDER / report_name
        report_path.write_text(n8n_resp.text, encoding="utf-8")

    tmp_path.unlink(missing_ok=True)
    return jsonify({
        "status": "accepted", "filename": safe_name,
        "report_saved": str(report_path) if report_path else None,
        "n8n_status": n8n_resp.status_code,
    }), 200


@app.route("/save-report", methods=["POST"])
def save_report():
    data       = request.get_json(force=True, silent=True) or request.form
    html       = data.get("html", "")
    image_name = data.get("image_name", "report")
    if not html:
        return jsonify({"error": "No HTML content provided"}), 400
    stem  = pathlib.Path(sanitise_filename(image_name)).stem
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{ts}_{stem}.html"
    out_path = REPORTS_FOLDER / fname
    out_path.write_text(html, encoding="utf-8")
    return jsonify({"status": "saved", "path": str(out_path), "filename": fname}), 200


@app.route("/metal-prices", methods=["POST"])
def metal_prices():
    data       = request.get_json(force=True, silent=True) or {}
    metals_raw = data.get("metals", "[]")
    if isinstance(metals_raw, str):
        try:
            metals = json.loads(metals_raw)
        except Exception:
            metals = [metals_raw]
    else:
        metals = metals_raw
    if not isinstance(metals, list):
        metals = [str(metals)]
    prices = {}
    for metal in metals:
        prices[metal] = generate_price_series(metal.strip().capitalize())
    return jsonify({"prices": prices}), 200


if __name__ == "__main__":
    print(f"[EVS Flask] n8n webhook : {N8N_WEBHOOK_URL}")
    print(f"[EVS Flask] Reports     : {REPORTS_FOLDER}")
    app.run(host="0.0.0.0", port=5000, debug=False)
