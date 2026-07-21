# -*- coding: utf-8 -*-
"""
KARAHOCA BARCODE PRO — الخلفية (Flask + SQLite)

يخدم واجهة الويب الثابتة (web_app/) ويوفّر واجهة REST فوق قاعدة SQLite.
لا يعتمد على أي وحدات native — يعمل على أي معمارية (x86/ARM) في Docker.

المتغيّرات البيئية:
    DB_PATH  مسار ملف SQLite (افتراضياً <المشروع>/data/barcode.db ؛ في Docker: /data/barcode.db)
    WEB_DIR  مجلد ملفات الواجهة (افتراضياً <المشروع>/web_app)
    PORT     منفذ خادم التطوير (افتراضياً 8000)
"""

import os
import re
import sqlite3
from datetime import datetime, timezone

from flask import Flask, request, jsonify, send_from_directory, abort

import telegram_notify

# ---------------------------------------------------------------------------
# المسارات (مستقلة عن مجلد التشغيل الحالي)
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)

WEB_DIR = os.environ.get("WEB_DIR", os.path.join(_PROJECT, "web_app"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(_PROJECT, "data", "barcode.db"))

# ---------------------------------------------------------------------------
# قواعد التحقّق (نفس قيود قاعدة البيانات السابقة — بيانات رقمية فقط)
# ---------------------------------------------------------------------------
CODE_RE = re.compile(r"^[0-9]{1,14}$")
CHECK_RE = re.compile(r"^[0-9]$")
GTIN_RE = re.compile(r"^[0-9]{13}$")

MAX_LIMIT = 500
MAX_BATCH = 5000

app = Flask(__name__)


# ---------------------------------------------------------------------------
# قاعدة البيانات
# ---------------------------------------------------------------------------
def get_db():
    """اتصال جديد لكل طلب (آمن مع خيوط waitress)."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db():
    """إنشاء الجدول والفهرس عند الإقلاع (idempotent)."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS barcode_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                input_code TEXT NOT NULL,
                check_digit TEXT NOT NULL,
                full_gtin  TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_barcode_input_code "
            "ON barcode_history(input_code);"
        )
        conn.commit()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _validate(data):
    """يتحقّق من حقل واحد ويعيد dict نظيفاً، أو يوقف الطلب بـ 400."""
    if not isinstance(data, dict):
        abort(400, description="expected a JSON object")
    ic = str(data.get("input_code", "")).strip()
    cd = str(data.get("check_digit", "")).strip()
    fg = str(data.get("full_gtin", "")).strip()
    if not CODE_RE.match(ic) or not CHECK_RE.match(cd) or not GTIN_RE.match(fg):
        abort(400, description="invalid barcode fields (must be numeric)")
    return {"input_code": ic, "check_digit": cd, "full_gtin": fg}


# ---------------------------------------------------------------------------
# واجهة REST
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/history")
def list_history():
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, MAX_LIMIT))
    order = request.args.get("order", "code")
    order_sql = "created_at DESC, id DESC" if order == "recent" else "input_code DESC, id DESC"
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, created_at, input_code, check_digit, full_gtin "
            "FROM barcode_history ORDER BY " + order_sql + " LIMIT ?",
            (limit,),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/history")
def create_history():
    row = _validate(request.get_json(silent=True))
    created_at = _now()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO barcode_history (created_at, input_code, check_digit, full_gtin) "
            "VALUES (?, ?, ?, ?)",
            (created_at, row["input_code"], row["check_digit"], row["full_gtin"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    # إشعار تلجرام (غير حاجب؛ يُعطَّل تلقائياً إن لم يُضبط الإعداد)
    telegram_notify.send_barcode_async(row["input_code"], row["full_gtin"])
    return jsonify(id=new_id, created_at=created_at, **row), 201


@app.post("/api/history/batch")
def create_batch():
    data = request.get_json(silent=True) or {}
    items = data.get("items")
    if not isinstance(items, list) or not items:
        abort(400, description="'items' must be a non-empty array")
    if len(items) > MAX_BATCH:
        abort(400, description="too many items (max %d)" % MAX_BATCH)
    validated = [_validate(it) for it in items]  # يتحقّق من الكل قبل الإدراج
    created = []
    with get_db() as conn:
        for row in validated:
            created_at = _now()
            cur = conn.execute(
                "INSERT INTO barcode_history (created_at, input_code, check_digit, full_gtin) "
                "VALUES (?, ?, ?, ?)",
                (created_at, row["input_code"], row["check_digit"], row["full_gtin"]),
            )
            created.append({"id": cur.lastrowid, "created_at": created_at, **row})
        conn.commit()
    return jsonify(created), 201


@app.delete("/api/history")
def delete_selected():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids")
    if not isinstance(ids, list) or not ids:
        abort(400, description="'ids' must be a non-empty array")
    try:
        ids = [int(x) for x in ids]
    except (TypeError, ValueError):
        abort(400, description="all ids must be integers")
    placeholders = ",".join("?" * len(ids))
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM barcode_history WHERE id IN (%s)" % placeholders, ids
        )
        conn.commit()
    return jsonify(deleted=cur.rowcount)


@app.delete("/api/history/all")
def delete_all():
    with get_db() as conn:
        cur = conn.execute("DELETE FROM barcode_history")
        conn.commit()
    return jsonify(deleted=cur.rowcount)


# ---------------------------------------------------------------------------
# الملفات الثابتة (الواجهة)
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/<path:filename>")
def assets(filename):
    if filename.startswith("api/"):
        abort(404)
    return send_from_directory(WEB_DIR, filename)


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(500)
def json_errors(e):
    code = getattr(e, "code", 500)
    if request.path.startswith("/api"):
        return jsonify(error=getattr(e, "description", str(e))), code
    return e


# إنشاء المخطّط عند الاستيراد (يشمل خادم waitress في الإنتاج)
init_db()


if __name__ == "__main__":
    # خادم تطوير فقط — الإنتاج يستخدم waitress عبر serve.py
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
