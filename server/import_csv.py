# -*- coding: utf-8 -*-
"""
ترحيل بيانات السجل من ملف CSV إلى قاعدة SQLite.

يدعم صيغتين تلقائياً:
  - تصدير Supabase: أعمدة مثل input_code, check_digit, full_gtin, created_at (بأي ترتيب، مع/بدون id).
  - تطبيق سطح المكتب: ترويسة "Timestamp,Input_Code,Check_Digit,Full_GTIN"
    أو صفوف بلا ترويسة على الشكل [timestamp, input, check, full].

الاستخدام:
  python import_csv.py <ملف.csv> [--db مسار_القاعدة]
  (افتراضياً يستخدم DB_PATH من البيئة أو <المشروع>/data/barcode.db)

الترحيل آمن للتكرار: الصفوف المطابقة (input_code + full_gtin + created_at) لا تُدرَج مرّتين.
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime, timezone

# إخراج UTF-8 آمن حتى على طرفية ويندوز (cp1252)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CODE_RE = re.compile(r"^[0-9]{1,14}$")
CHECK_RE = re.compile(r"^[0-9]$")
GTIN_RE = re.compile(r"^[0-9]{13}$")


def _clean(v):
    return ("" if v is None else str(v)).strip()


def _looks_like_header(first_row):
    joined = ",".join(first_row).lower()
    return ("input_code" in joined) or ("timestamp" in joined) or ("full_gtin" in joined)


def _map_row(row, header):
    """يعيد (input_code, check_digit, full_gtin, created_at) أو None إذا كان الصف غير صالح."""
    if header:
        idx = {k.strip().lower(): i for i, k in enumerate(header)}

        def col(*names):
            for n in names:
                if n in idx and idx[n] < len(row):
                    return _clean(row[idx[n]])
            return ""

        ic = col("input_code", "inputcode")
        cd = col("check_digit", "checkdigit", "check")
        fg = col("full_gtin", "fullgtin", "gtin", "full")
        ca = col("created_at", "timestamp", "created", "date")
    else:
        if len(row) < 4:
            return None
        ca, ic, cd, fg = _clean(row[0]), _clean(row[1]), _clean(row[2]), _clean(row[3])

    if not (CODE_RE.match(ic) and CHECK_RE.match(cd) and GTIN_RE.match(fg)):
        return None
    return ic, cd, fg, ca


def main():
    ap = argparse.ArgumentParser(description="Import barcode history CSV into SQLite")
    ap.add_argument("csv_path", help="path to the CSV file")
    ap.add_argument("--db", help="SQLite DB path (overrides the DB_PATH env var)")
    args = ap.parse_args()

    if args.db:
        os.environ["DB_PATH"] = args.db

    # يُستورد بعد ضبط DB_PATH كي تُنشأ القاعدة في المسار الصحيح
    import app  # noqa: E402

    with open(args.csv_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        print("CSV فارغ — لا شيء لاستيراده.")
        return

    header = None
    start = 0
    if _looks_like_header(rows[0]):
        header = rows[0]
        start = 1

    now_iso = datetime.now(timezone.utc).isoformat()
    inserted = skipped_invalid = skipped_dup = 0

    with app.get_db() as conn:
        for row in rows[start:]:
            mapped = _map_row(row, header)
            if mapped is None:
                skipped_invalid += 1
                continue
            ic, cd, fg, ca = mapped
            ca = ca or now_iso
            exists = conn.execute(
                "SELECT 1 FROM barcode_history WHERE input_code=? AND full_gtin=? AND created_at=? LIMIT 1",
                (ic, fg, ca),
            ).fetchone()
            if exists:
                skipped_dup += 1
                continue
            conn.execute(
                "INSERT INTO barcode_history (created_at, input_code, check_digit, full_gtin) "
                "VALUES (?, ?, ?, ?)",
                (ca, ic, cd, fg),
            )
            inserted += 1
        conn.commit()

    print(f"تم الاستيراد إلى: {app.DB_PATH}")
    print(f"  مُدرَج: {inserted}")
    print(f"  متخطّى (غير صالح/ترويسة): {skipped_invalid}")
    print(f"  متخطّى (مكرّر): {skipped_dup}")


if __name__ == "__main__":
    main()
