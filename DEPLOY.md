# نشر KARAHOCA BARCODE PRO على Hetzner عبر Coolify

تطبيق الويب صار يعمل بقاعدة **SQLite** بدل Supabase. المكوّنات:

- **خلفية Flask** (`server/app.py`) تخدم الواجهة الثابتة (`web_app/`) وتوفّر واجهة REST تحت `/api`.
- **قاعدة SQLite** في ملف واحد على المسار `DB_PATH` (افتراضياً داخل الحاوية: `/data/barcode.db`).
- **خادم إنتاجي waitress** (`server/serve.py`) — بايثون خالص، بلا وحدات native، يعمل على معماريّتي Hetzner (x86_64 و ARM64).

كل شيء في حاوية واحدة؛ الشرط الوحيد للبقاء بعد إعادة النشر هو **volume دائم على `/data`**.

---

## 1) المتطلّبات المسبقة
- خادم Hetzner (CX أو CAX) عليه Coolify مثبّت وشغّال.
- المستودع (Git) موصول بـ Coolify، أو ارفع المجلد يدوياً.
- نطاق (أو دومين فرعي) موجّه إلى عنوان الخادم (سجل `A`).

---

## 2) النشر عبر Coolify (الأسلوب الموصى به: Docker Compose)

الملف `docker-compose.yml` في جذر المشروع يعرّف الخدمة والـ volume الدائم تلقائياً.

1. في Coolify: **+ New → Resource → Docker Compose** (أو اختر مستودع Git ثم Build Pack = **Docker Compose**).
2. عيّن **Base Directory** = جذر المشروع (حيث يوجد `docker-compose.yml` و`Dockerfile`).
3. اضغط **Deploy**. سيبني Coolify الصورة من `Dockerfile` وينشئ الـ volume المسمّى `barcode_data` المربوط على `/data`.
4. من تبويب **Domains** أضف نطاقك وفعّل **HTTPS** (Coolify يصدر شهادة Let's Encrypt تلقائياً).
5. تأكّد أن **Port** (المنفذ الذي يوجّه إليه الوكيل) = **8000**.

> بديل: Build Pack = **Dockerfile**. عندها **يجب** أن تضيف يدوياً **Persistent Storage** يربط volume على المسار `/data` داخل الحاوية، وإلا ستُفقد البيانات عند كل نشر.

---

## 3) التخزين الدائم (الأهم ⚠️)
- قاعدة البيانات كلها ملف واحد: `/data/barcode.db` (مع ملفّي `-wal` و`-shm` بجانبه).
- مع `docker-compose.yml` الـ volume `barcode_data:/data` مُعرّف مسبقاً — لا حاجة لإجراء إضافي.
- مع أسلوب Dockerfile المجرّد: أضف Persistent Storage → Mount Path = `/data`.
- **لا تخزّن القاعدة داخل نظام ملفات الحاوية دون volume** — ستختفي عند إعادة النشر.

---

## 4) المتغيّرات البيئية (اختيارية — القيم الافتراضية تعمل)
| المتغيّر | الافتراضي | الوصف |
|---|---|---|
| `DB_PATH` | `/data/barcode.db` | مسار ملف SQLite (يجب أن يكون داخل الـ volume) |
| `PORT` | `8000` | منفذ الاستماع |
| `WAITRESS_THREADS` | `4` | عدد خيوط الخادم |
| `TELEGRAM_BOT_TOKEN` | — | (اختياري) توكن بوت تلجرام؛ فارغ = الإشعارات مُعطّلة |
| `TELEGRAM_CHAT_ID` | — | (اختياري) معرّف المحادثة/القناة التي تصلها الباركودات |

---

## 4.1) إشعارات تلجرام — إلى محادثتك الخاصة مع البوت (اختياري)
عند كل توليد باركود **مفرد**، يُرسل البوت **الرقم الأساسي + الباركود الكامل + ملف SVG** إلى **محادثتك الخاصة مع البوت** (لا قناة ولا مجموعة)، برسالة منسّقة.

**التهيئة:**
1. أنشئ بوتاً عبر **@BotFather** في تلجرام واحصل على **التوكن**.
2. **افتح بوتك في تلجرام واضغط /start** — ضروري؛ تلجرام يمنع البوت من مراسلتك قبل أن تبدأه.
3. احصل على **Chat ID** لمحادثتك الخاصة:
   - شغّل: `python get_telegram_chat_id.py <BOT_TOKEN>` وانسخ الـ id من نوع **`private`**.
   - أو افتح في المتصفح: `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates` وابحث عن `chat.id`.
4. **الويب (Coolify):** أضف متغيّرَي البيئة `TELEGRAM_BOT_TOKEN` و`TELEGRAM_CHAT_ID` في إعدادات المورد ثم أعد النشر. الخادم هو من يُرسل — فالتوكن يبقى آمناً ولا يظهر للمتصفح.
5. **سطح المكتب:** انسخ `telegram.example.json` إلى `telegram.json` بجانب الـ exe واملأ القيمتين (`telegram.json` مُستبعَد من Git).

- `chat_id` هو **رقم حسابك** (محادثتك الخاصة مع البوت) — ليس معرّف قناة.
- إن تُركت القيم فارغة، تُعطَّل الإشعارات تلقائياً ويعمل التطبيق طبيعياً.
- التوليد الجماعي (ZIP) لا يُرسل إشعارات (تفادياً للإغراق) — فقط التوليد المفرد.

---

## 5) فحص الصحّة (Health check)
- المسار: `GET /api/health` → `{"status":"ok"}` برمز 200.
- مُعرّف مسبقاً في `Dockerfile` و`docker-compose.yml`؛ يمكنك استخدامه في إعداد Health check داخل Coolify أيضاً.

---

## 6) ترحيل بياناتك القديمة (اختياري)

### أ) من Supabase
1. من لوحة Supabase: **Table Editor → barcode_history → Export → CSV**.
2. انسخ ملف `.csv` إلى الخادم (أو استورده محلياً قبل النشر).
3. شغّل داخل مجلد `server`:
   ```bash
   python import_csv.py /path/to/supabase_export.csv --db /data/barcode.db
   ```

### ب) من ملف `barcode_history.csv` (تطبيق سطح المكتب)
```bash
python server/import_csv.py barcode_history.csv --db /data/barcode.db
```
- السكربت يكتشف الصيغة تلقائياً، ويتخطّى صف الترويسة والصفوف غير الصالحة.
- **آمن للتكرار**: الصفوف المطابقة لا تُدرَج مرّتين.

> داخل Coolify يمكنك تشغيل الأمر عبر **Terminal/Exec** على الحاوية (تأكّد أن `--db` يشير إلى `/data/barcode.db`).

---

## 7) النسخ الاحتياطي والاسترجاع
- **نسخ احتياطي**: انسخ ملف `/data/barcode.db` (يكفي نسخه أثناء التشغيل بفضل وضع WAL؛ للنسخة المتّسقة تماماً استخدم `sqlite3 /data/barcode.db ".backup '/data/backup.db'"`).
- **استرجاع**: أوقف الخدمة، استبدل `barcode.db`، أعد التشغيل.
- يمكنك جدولة نسخ احتياطي دوري للـ volume عبر Coolify أو cron على الخادم.

---

## 8) التشغيل المحلي (اختبار قبل النشر)

بايثون مباشرة:
```bash
cd server
pip install -r requirements.txt
python serve.py          # إنتاجي (waitress) على http://localhost:8000
# أو خادم التطوير:  python app.py
```

Docker محلياً:
```bash
docker compose up --build       # بعد إزالة التعليق عن سطري ports في docker-compose.yml
# ثم افتح http://localhost:8000
```

---

## 9) واجهة REST (للمرجع)
| الطريقة | المسار | الوصف |
|---|---|---|
| GET | `/api/health` | فحص صحّة |
| GET | `/api/history?order=code\|recent&limit=N` | قائمة السجل (افتراضي: حسب الرقم تنازلياً، 50) |
| POST | `/api/history` | إضافة سجل `{input_code, check_digit, full_gtin}` |
| POST | `/api/history/batch` | إضافة دفعة `{items:[...]}` |
| DELETE | `/api/history` | حذف محدد `{ids:[...]}` |
| DELETE | `/api/history/all` | حذف الكل |

كل الحقول تُتحقَّق كأرقام فقط على الخادم (`input_code` 1–14 رقماً، `check_digit` رقم واحد، `full_gtin` 13 رقماً) — ما يمنع تخزين أي محتوى ضار.

---

## 10) ملاحظات أمنية
- الواجهة والـ API على **نفس الأصل** — لا CORS ولا مفاتيح مكشوفة (بخلاف Supabase سابقاً).
- الـ API **مفتوح** (بلا مصادقة) تماماً كما كان سلوك Supabase سابقاً. إن رغبت في تقييده:
  - فعّل **Basic Auth** على مستوى وكيل Coolify، أو قيّد الوصول بجدار ناري/شبكة خاصة.
- التحقّق الرقمي على الخادم + عرض الواجهة عبر `textContent` (لا `innerHTML`) يمنعان حقن XSS المخزَّن.

---

## 11) ملفات لم تعد مستخدمة
- `web_app/supabase_setup.sql` — لم يعد له داعٍ بعد الانتقال إلى SQLite (يمكن حذفه).
- مكتبة Supabase (CDN) أُزيلت من `index.html`. تبقى مكتبتا JSZip و FileSaver (لميزة الـ ZIP) تُحمَّلان من CDN.
