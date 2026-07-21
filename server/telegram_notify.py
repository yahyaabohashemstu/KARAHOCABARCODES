# -*- coding: utf-8 -*-
"""
إشعار تلجرام: يُرسل باركوداً جديداً (الرقم الأساسي + الكامل + ملف SVG) إلى محادثة محدّدة.

الإعداد عبر متغيّرات البيئة (تُضبط في Coolify):
    TELEGRAM_BOT_TOKEN   توكن البوت من BotFather
    TELEGRAM_CHAT_ID     معرّف المحادثة/القناة التي يُرسل إليها
    TELEGRAM_API_BASE    (اختياري) أساس واجهة تلجرام، افتراضياً https://api.telegram.org

إن لم تُضبط القيم، يُعطَّل الإرسال بصمت ولا يتأثّر عمل التطبيق.
"""

import os
import threading
import urllib.request

import barcode_svg


def _config():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if token and chat:
        return token, chat
    return None, None


def is_enabled():
    return _config()[0] is not None


def _api_base():
    return os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")


def _build_multipart(fields, file_field, filename, file_bytes, content_type):
    import uuid
    boundary = "----Karahoca" + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(("--" + boundary + "\r\n").encode())
        parts.append(('Content-Disposition: form-data; name="%s"\r\n\r\n' % k).encode())
        parts.append((str(v) + "\r\n").encode("utf-8"))
    parts.append(("--" + boundary + "\r\n").encode())
    parts.append(('Content-Disposition: form-data; name="%s"; filename="%s"\r\n'
                  % (file_field, filename)).encode())
    parts.append(("Content-Type: %s\r\n\r\n" % content_type).encode())
    parts.append(file_bytes)
    parts.append(("\r\n--" + boundary + "--\r\n").encode())
    return b"".join(parts), boundary


def _send(input_code, full_gtin):
    token, chat = _config()
    if not token:
        return
    try:
        svg = barcode_svg.generate_svg(full_gtin)
        if not svg:
            return
        caption = (
            "🆕 <b>باركود جديد — KARAHOCA</b>\n\n"
            "🔢 <b>الرقم الأساسي:</b> <code>%s</code>\n"
            "🏷️ <b>الباركود الكامل:</b> <code>%s</code>" % (input_code, full_gtin)
        )
        body, boundary = _build_multipart(
            {"chat_id": chat, "caption": caption, "parse_mode": "HTML"},
            "document", "EAN13_%s.svg" % full_gtin, svg.encode("utf-8"), "image/svg+xml",
        )
        url = "%s/bot%s/sendDocument" % (_api_base(), token)
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "multipart/form-data; boundary=" + boundary}
        )
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:  # لا يجب أن يعطّل حفظ الباركود
        print("[telegram] send failed:", e)


def send_barcode_async(input_code, full_gtin):
    """يُرسل في خيط منفصل حتى لا يؤخّر استجابة الـ API. لا يفعل شيئاً إن لم يُضبط الإعداد."""
    if not is_enabled():
        return
    threading.Thread(target=_send, args=(input_code, full_gtin), daemon=True).start()
