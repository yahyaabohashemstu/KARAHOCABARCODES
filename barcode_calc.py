import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import os
import sys
import sqlite3
from datetime import datetime
import zipfile

# مسارات مرتبطة بمجلد السكربت/الملف التنفيذي بغض النظر عن مجلد التشغيل الحالي (CWD)
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(sys.executable)  # PyInstaller onefile: مجلد الـ exe الحقيقي وليس _MEIPASS
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DB = os.path.join(_BASE_DIR, "barcode_history.db")
HISTORY_CSV = os.path.join(_BASE_DIR, "barcode_history.csv")  # السجل القديم (للترحيل مرة واحدة)
# لوحة ألوان مطابقة لنسخة الويب
BRAND = "#26364a"; BRAND2 = "#31465d"
BG = "#eaeef2"; SURFACE = "#ffffff"; SURFACE2 = "#f4f6f9"; SURFACE3 = "#eaeff4"
BORDER = "#dbe1e8"; BORDER2 = "#c8d1da"
INK = "#1e2a38"; INK2 = "#51606f"; INK3 = "#5c6b7a"
PRIMARY = "#2471a3"; PRIMARY2 = "#1d5c88"
SUCCESS = "#178a4e"; SUCCESS2 = "#136f3f"
WARNING = "#b26a0f"; WARNING2 = "#95580b"
DANGER = "#cf3d3d"; DANGER2 = "#b23232"
INFO = "#8e44ad"; INFO2 = "#783a91"

class KarahocaBarcodeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KARAHOCA BARCODE PRO")
        self.root.geometry("700x700")
        self.root.resizable(True, True)
        
        # الأنماط الثنائية للأرقام (L-code, G-code, R-code)
        self.L_CODES = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
        self.G_CODES = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"]
        self.R_CODES = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"]
        
        # هيكلية التشفير حسب الرقم الأول (يسار)
        self.STRUCTURE = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]

        self._init_database()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.setup_ui()

    def _init_database(self):
        """فتح/إنشاء قاعدة SQLite المحلية وترحيل سجل CSV القديم مرة واحدة."""
        self.conn = sqlite3.connect(HISTORY_DB)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS barcode_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                input_code TEXT NOT NULL,
                check_digit TEXT NOT NULL,
                full_gtin TEXT NOT NULL
            );"""
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_barcode_input_code ON barcode_history(input_code);"
        )
        self.conn.commit()
        self._migrate_csv_if_needed()

    def _migrate_csv_if_needed(self):
        """استيراد سجل barcode_history.csv القديم مرة واحدة إذا كانت القاعدة فارغة."""
        if not os.path.exists(HISTORY_CSV):
            return
        try:
            count = self.conn.execute("SELECT COUNT(*) FROM barcode_history").fetchone()[0]
            if count > 0:
                return
            with open(HISTORY_CSV, "r", encoding="utf-8") as f:
                rows = [r for r in csv.reader(f) if len(r) == 4 and r[1].isdigit()]
            with self.conn:
                for ts, ic, cd, fg in rows:
                    self.conn.execute(
                        "INSERT INTO barcode_history (created_at, input_code, check_digit, full_gtin) VALUES (?, ?, ?, ?)",
                        (ts, ic, cd, fg),
                    )
        except Exception as e:
            print(f"CSV migration failed: {e}")
            return
        # منع إعادة الاستيراد مستقبلاً (حتى بعد حذف الكل): احفظ نسخة محوّلة
        try:
            os.replace(HISTORY_CSV, HISTORY_CSV + ".imported")
        except Exception:
            pass

    def _on_close(self):
        try:
            self.conn.close()
        except Exception:
            pass
        self.root.destroy()

    def setup_ui(self):
        self.root.configure(bg=BG)
        self._setup_styles()

        # الترويسة المشتركة (بلون الهوية الداكن) كما في نسخة الويب
        header = tk.Frame(self.root, bg=BRAND)
        header.pack(side="top", fill="x")
        tk.Label(header, text="KARAHOCA BARCODE PRO", font=("Segoe UI", 16, "bold"),
                 bg=BRAND, fg="white", pady=14).pack(fill="x")

        # التذييل كما في نسخة الويب
        tk.Label(self.root, text="Developed for KARAHOCA TEMİZLİK", bg=SURFACE, fg=INK3,
                 font=("Segoe UI", 8), pady=6).pack(side="bottom", fill="x")

        # حاوية التبويبات
        self.tab_control = ttk.Notebook(self.root)
        self.tab1 = ttk.Frame(self.tab_control)
        self.tab2 = ttk.Frame(self.tab_control)
        self.tab3 = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tab1, text="📠 مولد الباركود")
        self.tab_control.add(self.tab2, text="📜 سجل العمليات")
        self.tab_control.add(self.tab3, text="🔎 تحقق عكسي")
        self.tab_control.pack(expand=1, fill="both")
        self.tab_control.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.setup_generator_ui(self.tab1)
        self.setup_history_ui(self.tab2)
        self.setup_verify_ui(self.tab3)

        # تحميل السجل عند الفتح
        self.load_history()

    def _setup_styles(self):
        # نظام تنسيق مطابق لألوان نسخة الويب
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", font=("Segoe UI", 11))
        style.configure("TEntry", font=("Consolas", 12), padding=4)
        style.configure("TSpinbox", padding=4)

        def button_style(name, bg, active_bg, fg="white"):
            style.configure(name, font=("Segoe UI", 10, "bold"), foreground=fg,
                            background=bg, relief="flat", padding=(14, 8),
                            bordercolor=bg, lightcolor=bg, darkcolor=bg)
            style.map(name,
                      background=[("pressed", active_bg), ("active", active_bg), ("disabled", "#c9d2db")],
                      foreground=[("disabled", "#8894a1")])

        button_style("Primary.TButton", PRIMARY, PRIMARY2)
        button_style("Info.TButton", INFO, INFO2)
        button_style("Success.TButton", SUCCESS, SUCCESS2)
        button_style("Warning.TButton", WARNING, WARNING2)
        button_style("Danger.TButton", DANGER, DANGER2)

        # الزر الثانوي: محايد بحدود (كما في الويب)
        style.configure("Secondary.TButton", font=("Segoe UI", 10, "bold"), foreground=INK,
                        background=SURFACE2, relief="solid", padding=(14, 8),
                        bordercolor=BORDER2, lightcolor=SURFACE2, darkcolor=SURFACE2)
        style.map("Secondary.TButton",
                  background=[("pressed", SURFACE3), ("active", SURFACE3)])

        # التبويبات
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(18, 8),
                        background=BRAND2, foreground="#c9d3dd")
        style.map("TNotebook.Tab",
                  background=[("selected", SURFACE)], foreground=[("selected", BRAND)])

        # الجدول
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=26,
                        background=SURFACE, fieldbackground=SURFACE, foreground=INK)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        background=SURFACE2, foreground=INK2, relief="flat", padding=6)
        style.map("Treeview", background=[("selected", PRIMARY)], foreground=[("selected", "white")])

    def setup_generator_ui(self, container):
        frame = tk.Frame(container, bg=BG)
        frame.pack(expand=True, fill="both", padx=18, pady=18)

        # مدخلات البيانات: رقم المنتج + العدد (كما في الويب)
        input_frame = tk.Frame(frame, bg=BG)
        input_frame.pack(fill="x", pady=(0, 10))
        tk.Label(input_frame, text="أدخل رقم المنتج (12 خانة):", bg=BG, fg=INK2,
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=6, sticky="w")
        tk.Label(input_frame, text="العدد:", bg=BG, fg=INK2,
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=1, padx=6, sticky="w")
        self.code_entry = ttk.Entry(input_frame, width=24, justify="center", font=("Consolas", 13))
        self.code_entry.grid(row=1, column=0, padx=6, sticky="we")
        self.count_var = tk.IntVar(value=1)
        self.count_spin = tk.Spinbox(input_frame, from_=1, to=100, width=6, justify="center",
                                     textvariable=self.count_var, font=("Consolas", 13))
        self.count_spin.grid(row=1, column=1, padx=6)
        input_frame.columnconfigure(0, weight=1)

        # أزرار: مسح / (+1) / حساب (بألوان الويب الدلالية)
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill="x", pady=6)
        ttk.Button(btn_frame, text="مسح الحقول", command=self.clear_fields,
                   style="Secondary.TButton").pack(side="left", expand=True, fill="x", padx=3)
        ttk.Button(btn_frame, text="(+1)", command=self.increment_code,
                   style="Info.TButton").pack(side="left", expand=True, fill="x", padx=3)
        ttk.Button(btn_frame, text="حساب وتسجيل", command=self.calculate,
                   style="Primary.TButton").pack(side="left", expand=True, fill="x", padx=3)

        # صندوق النتيجة
        result_frame = tk.Frame(frame, bg=SURFACE2, highlightbackground=BORDER, highlightthickness=1)
        result_frame.pack(fill="x", pady=12)
        tk.Label(result_frame, text="رقم التحقق:", bg=SURFACE2, fg=INK2,
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self.check_digit_label = tk.Label(result_frame, text="-", font=("Consolas", 18, "bold"),
                                          fg=PRIMARY, bg=SURFACE2)
        self.check_digit_label.grid(row=0, column=1, sticky="e", padx=12, pady=(10, 4))
        tk.Label(result_frame, text="الباركود الكامل:", bg=SURFACE2, fg=INK2,
                 font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", padx=12, pady=(4, 10))
        self.full_code_entry = ttk.Entry(result_frame, width=20, justify="center", font=("Consolas", 13))
        self.full_code_entry.grid(row=1, column=1, sticky="e", padx=12, pady=(4, 10))
        result_frame.columnconfigure(0, weight=1)

        # أزرار التصدير والدفعة (بعرض كامل)
        self.save_btn = ttk.Button(frame, text="💾 حفظ صورة الباركود (SVG)", command=self.save_svg,
                                   state="disabled", style="Success.TButton")
        self.save_btn.pack(fill="x", pady=(6, 3))
        ttk.Button(frame, text="📦 توليد وتنزيل المجموعة (ZIP)", command=self.batch_export,
                   style="Warning.TButton").pack(fill="x", pady=3)

        # شريط آخر الأرقام المستخدمة
        self.recent_label = tk.Label(frame, text="آخر الأرقام المستخدمة: ...", bg=SURFACE2, fg=INK2,
                                     font=("Segoe UI", 9), pady=8, relief="solid", bd=1)
        self.recent_label.pack(side="bottom", fill="x", pady=(12, 0))

    def setup_history_ui(self, container):
        wrapper = tk.Frame(container, bg=BG)
        wrapper.pack(expand=True, fill="both", padx=12, pady=12)

        # شريط الأدوات: تحديث / تحديد الكل / حذف المحدد / حذف الكل (كما في الويب)
        toolbar = tk.Frame(wrapper, bg=BG)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="🔄 تحديث السجل", command=self.load_history,
                   style="Secondary.TButton").pack(side="left", expand=True, fill="x", padx=3)
        ttk.Button(toolbar, text="✔️ تحديد الكل", command=self.select_all_history,
                   style="Secondary.TButton").pack(side="left", expand=True, fill="x", padx=3)
        ttk.Button(toolbar, text="🗑️ حذف المحدد", command=self.delete_selected,
                   style="Warning.TButton").pack(side="left", expand=True, fill="x", padx=3)
        ttk.Button(toolbar, text="❌ حذف الكل", command=self.clear_history,
                   style="Danger.TButton").pack(side="left", expand=True, fill="x", padx=3)

        # الجدول
        table_frame = tk.Frame(wrapper, bg=BG)
        table_frame.pack(expand=True, fill="both")
        columns = ("date", "input", "check", "full")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("date", text="التوقيت")
        self.tree.heading("input", text="المدخل")
        self.tree.heading("check", text="التحقق")
        self.tree.heading("full", text="الكامل")
        self.tree.column("date", width=160, anchor="center")
        self.tree.column("input", width=110, anchor="center")
        self.tree.column("check", width=60, anchor="center")
        self.tree.column("full", width=150, anchor="center")
        slider = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=slider.set)
        slider.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

    def select_all_history(self):
        # تحديد كل الصفوف (يعادل مربع "تحديد الكل" في الويب)
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children)

    def on_tab_changed(self, event):
        # تحديث السجل تلقائياً عند الانتقال إلى تبويب السجل (كما في الويب)
        try:
            if self.tab_control.index(self.tab_control.select()) == 1:
                self.load_history()
        except Exception:
            pass

    def setup_verify_ui(self, container):
        frame = tk.Frame(container, bg=BG)
        frame.pack(expand=True, fill="both", padx=18, pady=18)

        tk.Label(frame, text="الصق باركود كامل (13 خانة):", bg=BG, fg=INK2,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.verify_entry = ttk.Entry(frame, justify="center", font=("Consolas", 14))
        self.verify_entry.pack(fill="x")

        ttk.Button(frame, text="تحقق وفكّ الترميز", command=self.verify_code,
                   style="Primary.TButton").pack(fill="x", pady=12)

        # حالة النتيجة (صالح / غير صالح)
        self.verify_status = tk.Label(frame, text="", bg=BG, font=("Segoe UI", 13, "bold"))
        self.verify_status.pack(fill="x")

        # تفاصيل التفكيك
        self.verify_details = tk.Label(frame, text="", bg=SURFACE2, fg=INK, justify="right",
                                       anchor="e", font=("Consolas", 11), padx=12, pady=10,
                                       relief="solid", bd=1)
        self.verify_details.pack(fill="x", pady=10)

        # لوحة رسم الباركود
        self.verify_canvas = tk.Canvas(frame, bg="white", height=150,
                                       highlightbackground=BORDER, highlightthickness=1)
        self.verify_canvas.pack(fill="x", pady=6)

    def gs1_country(self, prefix3):
        try:
            p = int(prefix3)
        except (TypeError, ValueError):
            return None
        ranges = [
            (0, 19, "الولايات المتحدة/كندا"), (30, 39, "الولايات المتحدة"), (300, 379, "فرنسا"),
            (400, 440, "ألمانيا"), (450, 459, "اليابان"), (460, 469, "روسيا"), (500, 509, "المملكة المتحدة"),
            (619, 620, "تونس"), (621, 621, "سوريا"), (622, 622, "مصر"), (625, 625, "الأردن"),
            (626, 626, "إيران"), (627, 627, "الكويت"), (628, 628, "السعودية"), (629, 629, "الإمارات"),
            (690, 699, "الصين"), (729, 729, "إسرائيل"), (868, 869, "تركيا"), (870, 879, "هولندا"), (890, 890, "الهند"),
        ]
        for lo, hi, name in ranges:
            if lo <= p <= hi:
                return name
        return None

    def get_ean13_binary(self, full_code):
        # يبني السلسلة الثنائية (95 وحدة) من نفس جداول التشفير
        if len(full_code) != 13:
            return None
        first_digit = int(full_code[0])
        left_digits = full_code[1:7]
        right_digits = full_code[7:]
        structure = self.STRUCTURE[first_digit]
        binary = "101"
        for i in range(6):
            d = int(left_digits[i])
            binary += self.L_CODES[d] if structure[i] == 'L' else self.G_CODES[d]
        binary += "01010"
        for i in range(6):
            binary += self.R_CODES[int(right_digits[i])]
        binary += "101"
        return binary

    def _draw_barcode(self, full_code):
        c = self.verify_canvas
        c.delete("all")
        binary = self.get_ean13_binary(full_code)
        if not binary:
            return
        module_w = 2
        bar_h = 95
        guard_h = 108
        c.update_idletasks()
        cw = c.winfo_width() or 600
        total = len(binary) * module_w
        x0 = max(20, (cw - total) // 2)
        y0 = 8
        for i, bit in enumerate(binary):
            if bit == '1':
                is_guard = (i < 3) or (45 <= i < 50) or (i >= 92)
                h = guard_h if is_guard else bar_h
                x = x0 + i * module_w
                c.create_rectangle(x, y0, x + module_w, y0 + h, fill="black", outline="")
        c.create_text(x0 + total // 2, y0 + guard_h + 16, text=full_code,
                      font=("Consolas", 12), fill="black")

    def verify_code(self):
        raw = self.verify_entry.get().strip().replace('-', '').replace(' ', '')
        self.verify_entry.delete(0, tk.END)
        self.verify_entry.insert(0, raw)
        if not raw.isdigit() or len(raw) != 13:
            self.verify_status.config(text="⚠ يجب إدخال 13 رقماً بالضبط.", fg=DANGER)
            self.verify_details.config(text="")
            self.verify_canvas.delete("all")
            return
        first12 = raw[:12]
        entered = raw[12]
        total = sum(int(ch) * (3 if i % 2 == 0 else 1) for i, ch in enumerate(first12[::-1]))
        computed = str((10 - (total % 10)) % 10)
        valid = (computed == entered)
        country = self.gs1_country(raw[:3]) or "غير محدّد"
        if valid:
            self.verify_status.config(text="✅ باركود صالح", fg=SUCCESS)
        else:
            self.verify_status.config(text=f"❌ غير صالح — رقم التحقق الصحيح: {computed}", fg=DANGER)
        self.verify_details.config(text=(
            f"نظام الترقيم (أول رقم): {raw[0]}\n"
            f"بادئة GS1: {raw[:3]}  ({country})\n"
            f"رمز المنتج (12 خانة): {first12}\n"
            f"رقم التحقق (مُدخل / محسوب): {entered} / {computed}"
        ))
        self._draw_barcode(raw)

    def load_history(self):
        # تنظيف الجدول
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        recent_items = []
        try:
            # الترتيب تنازلياً حسب رقم المنتج (الأصفار البادئة تجعل الترتيب النصي = الرقمي)
            rows = self.conn.execute(
                "SELECT id, created_at, input_code, check_digit, full_gtin "
                "FROM barcode_history ORDER BY input_code DESC, id DESC"
            ).fetchall()
            for row_id, created_at, input_code, check_digit, full_gtin in rows:
                # نستخدم id الصف كمعرّف (iid) للحذف الدقيق لاحقاً
                self.tree.insert('', 'end', iid=str(row_id),
                                 values=(created_at, input_code, check_digit, full_gtin))
                if len(recent_items) < 3:
                    recent_items.append(input_code)
        except Exception as e:
            print(f"load_history failed to read database: {e}")
            
        # تحديث شريط الحالة
        if recent_items:
            self.recent_label.config(text=f"آخر الأرقام: {' - '.join(recent_items)}")

    def get_recent_inputs(self, count=1):
        try:
            rows = self.conn.execute(
                "SELECT input_code FROM barcode_history ORDER BY id DESC LIMIT ?",
                (count,)
            ).fetchall()
            # الأحدث في النهاية (مطابقة لسلوك CSV السابق: rows[-count:])
            return [r[0] for r in reversed(rows)]
        except Exception:
            return []

    def increment_code(self):
        current_val = self.code_entry.get().strip()
        
        # If empty, try to get last used
        if not current_val:
            recents = self.get_recent_inputs(1)
            if recents:
                current_val = recents[-1]
        
        if not current_val:
            messagebox.showwarning("تنبيه", "لا يوجد رقم سابق للزيادة عليه. أدخل رقمًا لأول مرة.")
            return

        current_val = current_val.replace('-', '').replace(' ', '')
        
        if not current_val.isdigit():
             messagebox.showerror("خطأ", "القيمة الحالية ليست رقمًا صحيحًا.")
             return
             
        try:
            # Convert to int, add 1, convert back to string with zfill
            next_val = int(current_val) + 1
            if next_val > 999999999999:
                messagebox.showerror("خطأ", "تم الوصول إلى الحد الأقصى للرقم (12 خانة). لا يمكن الزيادة أكثر.")
                return
            new_code = str(next_val).zfill(12)
            
            self.clear_fields()
            self.code_entry.insert(0, new_code)
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ أثناء الزيادة: {e}")

    def clear_fields(self):
        self.code_entry.delete(0, tk.END)
        self.full_code_entry.delete(0, tk.END)
        self.check_digit_label.config(text="-")
        self.save_btn.config(state="disabled")

    def calculate(self):
        raw_code = self.code_entry.get().strip()
        
        # تنظيف المدخلات
        raw_code = raw_code.replace('-', '').replace(' ', '')
        self.code_entry.delete(0, tk.END)
        self.code_entry.insert(0, raw_code)
        
        if not raw_code.isdigit() or len(raw_code) != 12:
            messagebox.showerror("خطأ", "الرجاء إدخال 12 رقم صحيح.")
            return

        # حساب رقم التحقق
        reversed_digits = raw_code[::-1]
        total = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed_digits))
        check_digit = (10 - (total % 10)) % 10
        
        full_gtin = raw_code + str(check_digit)
        
        # تحديث الواجهة
        self.check_digit_label.config(text=str(check_digit))
        self.full_code_entry.delete(0, tk.END)
        self.full_code_entry.insert(0, full_gtin)
        self.save_btn.config(state="normal")
        
        # حفظ في السجل
        self.save_to_history(raw_code, check_digit, full_gtin)
        self.load_history()

    def save_to_history(self, input_code, check_digit, full_gtin):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.conn:
            self.conn.execute(
                "INSERT INTO barcode_history (created_at, input_code, check_digit, full_gtin) "
                "VALUES (?, ?, ?, ?)",
                (timestamp, input_code, str(check_digit), full_gtin)
            )

    def delete_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("تنبيه", "الرجاء تحديد سجل واحد على الأقل للحذف.")
            return
            
        if not messagebox.askyesno("تأكيد", f"هل أنت متأكد من حذف {len(selected_items)} سجل/سجلات؟"):
            return

        # المعرّفات المحددة هي id الصفوف (iid في الجدول) — حذف دقيق بالمعرّف
        try:
            ids = [int(iid) for iid in selected_items]
        except ValueError:
            messagebox.showerror("خطأ", "تعذّر تحديد السجلات المختارة.")
            return

        placeholders = ",".join("?" * len(ids))
        with self.conn:
            self.conn.execute(
                f"DELETE FROM barcode_history WHERE id IN ({placeholders})", ids
            )

        self.load_history()
        messagebox.showinfo("تم", "تم حذف السجلات المحددة بنجاح.")

    def clear_history(self):
        if not messagebox.askyesno("تأكيد", "هل أنت متأكد من حذف السجل كاملاً؟"):
            return

        with self.conn:
            self.conn.execute("DELETE FROM barcode_history")
        self.load_history()
        messagebox.showinfo("تم", "تم حذف السجل كاملاً.")

    def get_ean13_svg_content(self, full_code):
        if len(full_code) != 13:
            return None
            
        # تقسيم الكود
        first_digit = int(full_code[0])
        left_digits = full_code[1:7]
        right_digits = full_code[7:]
        
        # تحديد نمط التشفير للجزء الأيسر
        structure = self.STRUCTURE[first_digit]
        
        # بناء السلسلة الثنائية
        binary_string = "101" # Start Guard
        
        # Left Side
        for i in range(6):
            digit = int(left_digits[i])
            coding = structure[i]
            if coding == 'L':
                binary_string += self.L_CODES[digit]
            else:
                binary_string += self.G_CODES[digit]
                
        binary_string += "01010" # Center Guard
        
        # Right Side
        for i in range(6):
            digit = int(right_digits[i])
            binary_string += self.R_CODES[digit]
            
        binary_string += "101" # End Guard
        
        # إعدادات الرسم
        module_width = 2
        short_bar_height = 110  # Increased to match JS/Original
        long_bar_height = 123   # Increased to match JS/Original
        font_size = 20
        total_width = (10 + len(binary_string) + 7) * module_width  # 10 وحدات هامش يسار + 95 قضيباً + 7 وحدات هامش يمين 
        total_height = long_bar_height + 10 # Reduced padding
        start_x = 10 * module_width
        
        # إنشاء محتوى SVG
        svg_content = f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="{total_height}" viewBox="0 0 {total_width} {total_height}">\n'
        svg_content += f'<rect width="100%" height="100%" fill="white"/>\n'
        
        # رسم الخطوط
        for i, bit in enumerate(binary_string):
            if bit == '1':
                x = start_x + (i * module_width)
                # حراس البداية، المنتصف، والنهاية يكونون أطول
                is_guard = (i < 3) or (i >= 45 and i < 50) or (i >= 92)
                h = long_bar_height if is_guard else short_bar_height
                svg_content += f'<rect x="{x}" y="0" width="{module_width}" height="{h}" fill="black" shape-rendering="crispEdges"/>\n'
        
        # إضافة النصوص
        text_y = long_bar_height + 2 # Moved up significantly (was +15)
        
        # الرقم الأول
        svg_content += f'<text x="{start_x - 10}" y="{text_y}" font-family="monospace" font-size="{font_size}" text-anchor="end">{first_digit}</text>\n'
        
        # الجزء الأيسر
        left_x_str = start_x + (3 * module_width) + (3.5 * module_width) 
        for i, d in enumerate(left_digits):
            x = left_x_str + (i * 7 * module_width)
            svg_content += f'<text x="{x}" y="{text_y}" font-family="monospace" font-size="{font_size}" text-anchor="middle">{d}</text>\n'
            
        # الجزء الأيمن
        right_x_str = start_x + (50 * module_width) + (3.5 * module_width)
        for i, d in enumerate(right_digits):
            x = right_x_str + (i * 7 * module_width)
            svg_content += f'<text x="{x}" y="{text_y}" font-family="monospace" font-size="{font_size}" text-anchor="middle">{d}</text>\n'

        # علامة >
        svg_content += f'<text x="{start_x + (95 * module_width) + 10}" y="{text_y}" font-family="monospace" font-size="{font_size}" text-anchor="start">&gt;</text>\n'
        
        svg_content += '</svg>'
        return svg_content

    def save_svg(self):
        full_code = self.full_code_entry.get()
        if not full_code:
            return
            
        svg_content = self.get_ean13_svg_content(full_code)
        if not svg_content:
            return

        file_path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG files", "*.svg")], initialfile=f"EAN13_{full_code}.svg")
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
            messagebox.showinfo("تم الحفظ", f"تم حفظ الباركود بنجاح في:\n{file_path}")

    def batch_export(self):
        start_code_str = self.code_entry.get().strip().replace('-', '').replace(' ', '')
        
        if not start_code_str.isdigit() or len(start_code_str) != 12:
            messagebox.showerror("خطأ", "يجب إدخال 12 رقم صحيح في خانة المنتج.")
            return
            
        try:
            count = int(self.count_var.get())
        except:
            count = 1
            
        if count < 1: count = 1
        if count > 100:
            if not messagebox.askyesno("تأكيد", f"لقد اخترت عدداً كبيراً ({count}). قد يستغرق الأمر بعض الوقت. هل أنت متأكد؟"):
                return

        # طلب مكان حفظ الملف المضغوط
        zip_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP files", "*.zip")],
            initialfile=f"Barcodes_Batch_{start_code_str}_x{count}.zip",
            title="اختر مكان حفظ الملف المضغوط"
        )
        
        if not zip_path:
            return

        current_val = int(start_code_str)
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for _ in range(count):
                    # إيقاف التوليد إذا تجاوز الرقم نطاق 12 خانة
                    if current_val > 999999999999:
                        break
                    # 1. Prepare Code
                    current_code_str = str(current_val).zfill(12)
                    
                    # 2. Check Digit
                    reversed_digits = current_code_str[::-1]
                    total = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed_digits))
                    check_digit = (10 - (total % 10)) % 10
                    full_gtin = current_code_str + str(check_digit)
                    
                    # 3. Generate content
                    svg_content = self.get_ean13_svg_content(full_gtin)
                    if svg_content is None:
                        break
                    
                    # 4. Write to ZIP
                    zipf.writestr(f"EAN13_{full_gtin}.svg", svg_content)
                    
                    # 5. History
                    self.save_to_history(current_code_str, check_digit, full_gtin)
                    
                    # Increment for next
                    current_val += 1
            
            # Update UI for next valid code
            final_next_code = str(current_val).zfill(12)
            self.clear_fields()
            self.code_entry.insert(0, final_next_code)
            self.load_history()
            
            messagebox.showinfo("نجاح", f"تم توليد {count} باركود وحفظهم في الملف المضغوط بنجاح!\nالرقم التالي الجاهز: {final_next_code}")
            
        except Exception as e:
            messagebox.showerror("حدث خطأ", f"فشلت العملية: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = KarahocaBarcodeApp(root)
    root.mainloop()