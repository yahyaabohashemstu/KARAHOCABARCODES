import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import datetime
import csv

class KarahocaBarcodeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KARAHOCA - نظام الباركود المتقدم (EAN-13)")
        self.root.geometry("700x650") # زيادة الطول قليلاً لاستيعاب الشريط الجديد
        self.root.resizable(True, True)
        
        # ملف السجل
        self.history_file = "barcode_history.csv"
        self.ensure_history_file_exists()

        # الأنماط والتنسيق
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[10, 5])
        
        # --- جداول تشفير EAN-13 ---
        self.L_CODES = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
        self.G_CODES = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"]
        self.R_CODES = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001000", "1010000", "1000100", "1001000", "1110100"]
        self.STRUCTURE = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]

        # --- الحاوية الرئيسية (Tabs) ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # التبويب الأول: المولد
        self.tab_generator = tk.Frame(self.notebook, bg="#f0f0f0")
        self.notebook.add(self.tab_generator, text=" 📠 مولد الباركود ")
        self.setup_generator_ui()

        # التبويب الثاني: السجل
        self.tab_history = tk.Frame(self.notebook, bg="#f0f0f0")
        self.notebook.add(self.tab_history, text=" 📜 سجل العمليات ")
        self.setup_history_ui()

        # تحميل البيانات الأولية
        self.load_history_to_tree()
        self.update_recent_label() # تحديث الشريط السفلي عند التشغيل

    # ==========================
    # جزء إدارة الملفات (Backend)
    # ==========================
    def ensure_history_file_exists(self):
        if not os.path.exists(self.history_file):
            with open(self.history_file, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "Input_Code", "Check_Digit", "Full_GTIN"])

    def save_record(self, input_code, check_digit, full_gtin):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. الحفظ في الملف
        with open(self.history_file, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, input_code, check_digit, full_gtin])
        
        # 2. التحديث في واجهة السجل
        self.tree.insert("", 0, values=(timestamp, input_code, check_digit, full_gtin))
        
        # 3. تحديث الشريط السفلي في الصفحة الرئيسية
        self.update_recent_label()

    def get_recent_inputs(self, count=2):
        """جلب آخر رقمين تم استخدامهما من ملف CSV"""
        recent_items = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, mode='r', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    next(reader, None) # skip header
                    # قراءة كل الصفوف
                    rows = list(reader)
                    # نأخذ آخر عنصرين (أو أقل إذا لم يوجد)
                    last_rows = rows[-count:]
                    # استخراج العمود الثاني (Input_Code)
                    for row in last_rows:
                        if len(row) > 1:
                            recent_items.append(row[1])
            except:
                pass
        return recent_items

    # ==========================
    # واجهة المولد (Generator UI)
    # ==========================
    def setup_generator_ui(self):
        # العنوان
        header = tk.Frame(self.tab_generator, bg="#2c3e50", height=70)
        header.pack(fill=tk.X)
        tk.Label(header, text="KARAHOCA BARCODE PRO", font=("Segoe UI", 18, "bold"), fg="white", bg="#2c3e50").pack(pady=15)

        container = tk.Frame(self.tab_generator, bg="#f0f0f0", padx=30, pady=10) # قللنا الـ pady لتقريب العناصر
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(container, text="أدخل رقم المنتج (12 خانة):", font=("Segoe UI", 11), bg="#f0f0f0").pack(anchor="e")
        
        self.entry_var = tk.StringVar()
        self.entry_code = ttk.Entry(container, textvariable=self.entry_var, font=("Consolas", 16), justify="center")
        self.entry_code.pack(fill=tk.X, pady=5, ipady=8)
        self.entry_code.bind('<Return>', self.calculate)
        self.create_context_menu(self.entry_code)
        self.entry_code.focus()

        # أزرار
        btn_frame = tk.Frame(container, bg="#f0f0f0")
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="مسح الحقول", command=self.clear_fields).grid(row=0, column=0, padx=10)
        ttk.Button(btn_frame, text="(+1)", command=self.increment_code).grid(row=0, column=1, padx=10)
        ttk.Button(btn_frame, text="حساب وتسجيل", command=self.calculate).grid(row=0, column=2, padx=10)

        # النتيجة
        res_frame = tk.LabelFrame(container, text=" النتيجة الحالية ", font=("Segoe UI", 10, "bold"), bg="#f0f0f0", padx=15, pady=10)
        res_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(res_frame, text="رقم التحقق:", bg="#f0f0f0").grid(row=0, column=1, sticky="e")
        self.lbl_check_digit = tk.Label(res_frame, text="-", font=("Consolas", 18, "bold"), fg="#e74c3c", bg="#f0f0f0")
        self.lbl_check_digit.grid(row=0, column=0, sticky="w", padx=20)

        tk.Label(res_frame, text="الباركود الكامل:", bg="#f0f0f0").grid(row=1, column=1, sticky="e", pady=(5,0))
        self.full_barcode_var = tk.StringVar()
        full_entry = ttk.Entry(res_frame, textvariable=self.full_barcode_var, font=("Consolas", 14), state="readonly", justify="center")
        full_entry.grid(row=1, column=0, sticky="ew", padx=5, pady=(5,0))
        self.create_copy_menu(full_entry)

        # زر التصدير
        self.btn_export_svg = ttk.Button(container, text="💾 حفظ صورة الباركود (SVG)", command=self.export_perfect_svg, state="disabled")
        self.btn_export_svg.pack(pady=15, fill=tk.X)

        # === المنطقة الجديدة: آخر الأرقام المستخدمة ===
        recent_frame = tk.Frame(self.tab_generator, bg="#e0e0e0", bd=1, relief="solid")
        recent_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 20))
        
        tk.Label(recent_frame, text="آخر الأرقام المستخدمة:", font=("Segoe UI", 9, "bold"), bg="#e0e0e0", fg="#555").pack(pady=(5,0))
        
        self.lbl_recent_display = tk.Label(recent_frame, text="...", font=("Consolas", 12, "bold"), fg="#2980b9", bg="#e0e0e0")
        self.lbl_recent_display.pack(pady=(0, 5))

        tk.Label(self.tab_generator, text="Developed for KARAHOCA TEMİZLİK", font=("Arial", 8), fg="#7f8c8d", bg="#f0f0f0").pack(side=tk.BOTTOM, pady=2)

    def update_recent_label(self):
        """تحديث النص في أسفل الصفحة"""
        recents = self.get_recent_inputs(2) # جلب آخر رقمين
        if not recents:
            display_text = "لا يوجد سجل بعد"
        else:
            # دمجهم بشرطة (الأقدم - الأحدث)
            display_text = " - ".join(recents)
        
        self.lbl_recent_display.config(text=display_text)

    # ==========================
    # واجهة السجل (History UI)
    # ==========================
    def setup_history_ui(self):
        container = tk.Frame(self.tab_history, bg="#f0f0f0", padx=10, pady=10)
        container.pack(fill=tk.BOTH, expand=True)

        toolbar = tk.Frame(container, bg="#f0f0f0")
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(toolbar, text="تحديث السجل", command=self.load_history_to_tree).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="مسح السجل بالكامل", command=self.clear_history_file).pack(side=tk.LEFT, padx=5)

        columns = ("time", "input", "check", "full")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("time", text="التوقيت")
        self.tree.column("time", width=150, anchor="center")
        self.tree.heading("input", text="الرقم المدخل")
        self.tree.column("input", width=120, anchor="center")
        self.tree.heading("check", text="التحقق")
        self.tree.column("check", width=50, anchor="center")
        self.tree.heading("full", text="الباركود الناتج")
        self.tree.column("full", width=150, anchor="center")

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def load_history_to_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not os.path.exists(self.history_file): return
        try:
            with open(self.history_file, mode='r', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader, None)
                rows = list(reader)
                for row in reversed(rows):
                    if row: self.tree.insert("", "end", values=row)
        except: pass

    def clear_history_file(self):
        if messagebox.askyesno("تأكيد", "هل أنت متأكد من مسح السجل؟"):
            if os.path.exists(self.history_file):
                os.remove(self.history_file)
            self.ensure_history_file_exists()
            self.load_history_to_tree()
            self.update_recent_label() # تحديث الشريط ليصبح فارغاً

    # ==========================
    # المنطق
    # ==========================
    def increment_code(self):
        current_val = self.entry_var.get().strip()
        
        # إذا كان الحقل فارغاً، نحاول جلب آخر رقم من السجل
        if not current_val:
            recents = self.get_recent_inputs(1)
            if recents:
                current_val = recents[-1] # السجل يحتوي [الأقدام، ...، الأحدث]

        if not current_val:
            messagebox.showinfo("تنبيه", "لا يوجد رقم سابق للزيادة عليه. يرجى إدخال رقم مبدئي.")
            return

        try:
            # تنظيف المدخل
            clean_val = current_val.replace(" ", "").replace("-", "")
            if not clean_val.isdigit():
                 messagebox.showerror("خطأ", "القيمة الحالية ليست رقمًا صحيحًا.")
                 return

            next_val = int(clean_val) + 1
            # تنسيق الرقم ليكون 12 خانة (إضافة أصفار على اليسار إذا لزم الأمر)
            new_code = str(next_val).zfill(12)
            
            self.entry_var.set(new_code)
            
        except Exception as e:
             messagebox.showerror("خطأ", str(e))

    def calculate(self, event=None):
        raw_code = self.entry_var.get().strip().replace(" ", "").replace("-", "")
        self.entry_var.set(raw_code)

        if not raw_code.isdigit() or len(raw_code) != 12:
            messagebox.showerror("خطأ", "يجب إدخال 12 رقم بالضبط.")
            return

        try:
            reversed_digits = raw_code[::-1]
            total = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed_digits))
            check_digit = (10 - (total % 10)) % 10
            
            full_gtin = f"{raw_code}{check_digit}"

            self.lbl_check_digit.config(text=str(check_digit))
            self.full_barcode_var.set(full_gtin)
            self.btn_export_svg.config(state="normal")
            
            # حفظ وتحديث
            self.save_record(raw_code, check_digit, full_gtin)

        except Exception as e:
            messagebox.showerror("خطأ", str(e))

    # ==========================
    # خوارزمية الرسم (الدقيقة)
    # ==========================
    def encode_ean13(self, code):
        if len(code) != 13: return None
        first = int(code[0])
        left = code[1:7]
        right = code[7:13]
        
        binary = "101"
        structure = self.STRUCTURE[first]
        for i, d in enumerate(left):
            binary += self.L_CODES[int(d)] if structure[i] == 'L' else self.G_CODES[int(d)]
        binary += "01010"
        for d in right:
            binary += self.R_CODES[int(d)]
        binary += "101"
        return binary

    def export_perfect_svg(self):
        code = self.full_barcode_var.get()
        if not code: return

        file_path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG Image", "*.svg")], initialfile=f"EAN13_{code}")
        if not file_path: return

        try:
            pattern = self.encode_ean13(code)
            if not pattern: return

            module_width = 1.8
            short_bar_h = 110    
            long_bar_h = 123
            font_size = 20
            total_width = (95 + 14) * module_width
            
            svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="{long_bar_h + 10}" viewBox="0 0 {total_width} {long_bar_h + 10}">']
            svg.append(f'<rect width="100%" height="100%" fill="white"/>')
            
            start_x = 9 * module_width 

            for i, bit in enumerate(pattern):
                if bit == "1":
                    x = start_x + (i * module_width)
                    is_guard = (i < 3) or (45 <= i < 50) or (i >= 92)
                    h = long_bar_h if is_guard else short_bar_h
                    svg.append(f'<rect x="{x}" y="0" width="{module_width}" height="{h}" fill="black" shape-rendering="crispEdges"/>')

            text_y = long_bar_h + 2 
            
            svg.append(f'<text x="{start_x - 5}" y="{text_y}" font-family="Consolas, monospace" font-size="{font_size}" text-anchor="end">{code[0]}</text>')
            
            cur_x = start_x + (3 * module_width)
            for d in code[1:7]:
                cx = cur_x + (3.5 * module_width)
                svg.append(f'<text x="{cx}" y="{text_y}" font-family="Consolas, monospace" font-size="{font_size}" text-anchor="middle">{d}</text>')
                cur_x += (7 * module_width)

            cur_x = start_x + (50 * module_width)
            for d in code[7:13]:
                cx = cur_x + (3.5 * module_width)
                svg.append(f'<text x="{cx}" y="{text_y}" font-family="Consolas, monospace" font-size="{font_size}" text-anchor="middle">{d}</text>')
                cur_x += (7 * module_width)

            svg.append(f'<text x="{start_x + (95 * module_width) + 5}" y="{text_y}" font-family="Consolas, monospace" font-size="{font_size}" text-anchor="start">&gt;</text>')
            svg.append('</svg>')
            
            with open(file_path, 'w', encoding='utf-8') as f: f.write("\n".join(svg))
            messagebox.showinfo("تم", f"تم الحفظ: {os.path.basename(file_path)}")

        except Exception as e: messagebox.showerror("خطأ", str(e))

    # ==========================
    # Helpers
    # ==========================
    def create_context_menu(self, widget):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="لصق (Paste)", command=lambda: self.paste_to_widget(widget))
        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
        self.root.bind_class("Entry", "<Control-v>", lambda e: self.paste_to_widget(widget))

    def create_copy_menu(self, widget):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="نسخ (Copy)", command=lambda: self.root.clipboard_append(self.full_barcode_var.get()))
        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    def paste_to_widget(self, widget):
        try: widget.insert(tk.INSERT, self.root.clipboard_get())
        except: pass

    def clear_fields(self):
        self.entry_var.set("")
        self.full_barcode_var.set("")
        self.lbl_check_digit.config(text="-")
        self.btn_export_svg.config(state="disabled")
        self.entry_code.focus()

if __name__ == "__main__":
    root = tk.Tk()
    app = KarahocaBarcodeApp(root)
    root.mainloop()