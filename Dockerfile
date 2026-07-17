# KARAHOCA BARCODE PRO — حاوية الإنتاج (Flask + waitress + SQLite)
# بايثون خالص، بلا وحدات native — يبني ويعمل على x86_64 و ARM64 (Hetzner CX/CAX).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/data/barcode.db \
    PORT=8000 \
    WAITRESS_THREADS=4

WORKDIR /app

# 1) الاعتماديات أولاً (طبقة كاش مستقلة)
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

# 2) الكود (الخلفية + الواجهة الثابتة)
COPY server/ server/
COPY web_app/ web_app/

# 3) مجلد قاعدة البيانات — يُركّب عليه volume دائم في Coolify
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

# فحص صحّة يستخدمه Docker/Coolify
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)"

# خادم الإنتاج (waitress متعدد المنصّات)
WORKDIR /app/server
CMD ["python", "serve.py"]
