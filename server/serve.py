# -*- coding: utf-8 -*-
"""
مدخل الإنتاج: خادم WSGI عبر waitress (متعدد المنصّات: Linux و Windows).
يعمل داخل حاوية Docker وأيضاً محلياً على ويندوز.
"""

import os

from waitress import serve

from app import app, init_db  # مجلد السكربت مُضاف تلقائياً إلى sys.path عند التشغيل بـ python serve.py

if __name__ == "__main__":
    init_db()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    threads = int(os.environ.get("WAITRESS_THREADS", 4))
    print(f"KARAHOCA Barcode server (waitress) listening on http://{host}:{port}")
    serve(app, host=host, port=port, threads=threads)
