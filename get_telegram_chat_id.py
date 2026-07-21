# -*- coding: utf-8 -*-
"""
أداة مساعدة: تطبع معرّف محادثتك الخاصة (Chat ID) مع البوت لاستخدامه في الإعداد.

الخطوات:
  1) افتح بوتك في تلجرام واضغط /start (أو أرسل له أي رسالة).
  2) شغّل:  python get_telegram_chat_id.py <BOT_TOKEN>
            (أو اضبط متغيّر البيئة TELEGRAM_BOT_TOKEN ثم شغّله بلا وسيط)
  3) انسخ الـ chat_id من نوع "private" وضعه في:
       - سطح المكتب: telegram.json  ("chat_id": "...")
       - الويب:      متغيّر البيئة TELEGRAM_CHAT_ID في Coolify
"""

import os
import sys
import json
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    token = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
    if not token:
        print("الاستخدام:  python get_telegram_chat_id.py <BOT_TOKEN>")
        sys.exit(2)

    base = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
    url = "%s/bot%s/getUpdates" % (base, token)
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.load(resp)
    except Exception as e:
        print("فشل الاتصال بتلجرام:", e)
        sys.exit(1)

    if not data.get("ok"):
        print("رد غير متوقّع من تلجرام:", data)
        sys.exit(1)

    seen = {}
    for upd in data.get("result", []):
        msg = upd.get("message") or upd.get("edited_message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is None:
            continue
        name = (chat.get("title")
                or " ".join(x for x in [chat.get("first_name"), chat.get("last_name")] if x)
                or chat.get("username") or "")
        seen[cid] = (chat.get("type", ""), name)

    if not seen:
        print("لا توجد رسائل بعد. افتح بوتك في تلجرام واضغط /start ثم أعد المحاولة.")
        sys.exit(0)

    print("المحادثات التي راسلت البوت مؤخّراً:")
    for cid, (ctype, name) in seen.items():
        print("  chat_id = %-16s (%s)  %s" % (cid, ctype, name))
    print("\nلمحادثتك الخاصة: اختر الـ chat_id من النوع 'private'.")


if __name__ == "__main__":
    main()
