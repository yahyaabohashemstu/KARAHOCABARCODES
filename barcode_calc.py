import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import os
from datetime import datetime
import zipfile

class KarahocaBarcodeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KARAHOCABARCODES PRO")
        self.root.geometry("700x700")
        self.root.resizable(True, True)
        
        # الأنماط الثنائية للأرقام (L-code, G-code, R-code)
        self.L_CODES = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
        self.G_CODES = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"]
        self.R_CODES = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001000", "1010000", "1000100", "1001000", "1110100"]
        
        # هيكلية التشفير حسب الرقم الأول (يسار)
        self.STRUCTURE = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]

        self.setup_ui()

    def setup_ui(self):
        # النمط العام
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', font=('Segoe UI', 10, 'bold'), padding=5)
        style.configure('TLabel', font=('Segoe UI', 11))
        style.configure('TEntry', font=('Consolas', 12))

        # حاوية التبويبات
        tab_control = ttk.Notebook(self.root)
        
        self.tab1 = ttk.Frame(tab_control)
        self.tab2 = ttk.Frame(tab_control)
        
        tab_control.add(self.tab1, text='مولد الباركود')
        tab_control.add(self.tab2, text='سجل العمليات')
        tab_control.pack(expand=1, fill="both")
        
        self.setup_generator_ui(self.tab1)
        self.setup_history_ui(self.tab2)
        
        # تحميل السجل عند الفتح
        self.load_history()

    def setup_generator_ui(self, container):
        frame = tk.Frame(container, bg="#f0f0f0")
        frame.pack(expand=True, fill="both", padx=20, pady=20)
        
        # الشعار أو العنوان
        tk.Label(frame, text="KARAHOCA BARCODE PRO", font=("Segoe UI", 18, "bold"), bg="#2c3e50", fg="white").pack(fill="x", pady=(0, 20))
        
        # مدخلات البيانات
        input_frame = tk.Frame(frame, bg="#f0f0f0")
        input_frame.pack(pady=10)
        
        tk.Label(input_frame, text="أدخل رقم المنتج (12 خانة):", bg="#f0f0f0").grid(row=0, column=0, padx=5, sticky="e")
        
        self.code_entry = ttk.Entry(input_frame, width=20, justify='center')
        self.code_entry.grid(row=0, column=1, padx=5)

        # خانة العدد (Quantity)
        tk.Label(input_frame, text="العدد:", bg="#f0f0f0").grid(row=0, column=2, padx=5, sticky="e")
        self.count_var = tk.IntVar(value=1)
        self.count_spin = tk.Spinbox(input_frame, from_=1, to=100, width=5, textvariable=self.count_var)
        self.count_spin.grid(row=0, column=3, padx=5)

        # الأزرار
        btn_frame = tk.Frame(frame, bg="#f0f0f0")
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="مسح الحقول", command=self.clear_fields).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="(+1)", command=self.increment_code).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="حساب وتسجيل", command=self.calculate).grid(row=0, column=2, padx=5)
        
        # زر التوليد الجماعي
        ttk.Button(btn_frame, text="📦 القائمة المضغوطة (ZIP)", command=self.batch_export).grid(row=1, column=0, columnspan=3, pady=10, sticky="ew")

        # عرض النتائج
        result_frame = tk.LabelFrame(frame, text="النتيجة", bg="white", font=("Segoe UI", 10, "bold"))
        result_frame.pack(fill="x", pady=10, padx=20)
        
        tk.Label(result_frame, text="رقم التحقق (Check Digit):", bg="white").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.check_digit_label = tk.Label(result_frame, text="-", font=("Consolas", 14, "bold"), fg="#e74c3c", bg="white")
        self.check_digit_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        tk.Label(result_frame, text="الباركود الكامل (GTIN-13):", bg="white").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.full_code_entry = ttk.Entry(result_frame, width=20, justify='center', font=("Consolas", 12))
        self.full_code_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # زر الحفظ
        self.save_btn = ttk.Button(frame, text="💾 حفظ صورة الباركود (SVG)", command=self.save_svg, state="disabled")
        self.save_btn.pack(pady=10)
        
        # عرض آخر الأرقام
        self.recent_label = tk.Label(frame, text="آخر الأرقام المستخدمة: ...", bg="#e0e0e0", fg="#555")
        self.recent_label.pack(side="bottom", fill="x", pady=10)

    def setup_history_ui(self, container):
        # Using a Treeview for history
        columns = ('date', 'input', 'check', 'full')
        self.tree = ttk.Treeview(container, columns=columns, show='headings')
        
        self.tree.heading('date', text='التاريخ')
        self.tree.heading('input', text='المدخل')
        self.tree.heading('check', text='التحقق')
        self.tree.heading('full', text='الكامل')
        
        self.tree.column('date', width=150, anchor='center')
        self.tree.column('input', width=100, anchor='center')
        self.tree.column('check', width=50, anchor='center')
        self.tree.column('full', width=150, anchor='center')
        
        slider = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=slider.set)
        
        slider.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        # زر حذف المحدد
        btn_frame = tk.Frame(container)
        btn_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame, text="حذف المحدد (Delete Selected)", command=self.delete_selected).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="حذف الكل (Delete All)", command=self.clear_history).pack(side="left", padx=5)

    def load_history(self):
        # تنظيف الجدول
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        if not os.path.exists("barcode_history.csv"):
            return

        recent_items = []
        try:
            with open("barcode_history.csv", "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
                # Filter valid rows
                valid_rows = [r for r in rows if len(r) == 4]
                # Sort by input code (index 1) descending (Largest at top)
                # Convert to int for proper numeric sort, though string sort works for fixed length
                valid_rows.sort(key=lambda x: str(x[1]), reverse=True)

                for row in valid_rows:
                    self.tree.insert('', 'end', values=row)
                    if len(recent_items) < 3:
                        recent_items.append(row[1])
        except Exception as e:
            pass
            
        # تحديث شريط الحالة
        if recent_items:
            self.recent_label.config(text=f"آخر الأرقام: {' - '.join(recent_items)}")

    def get_recent_inputs(self, count=1):
        recent_items = []
        if os.path.exists("barcode_history.csv"):
             with open("barcode_history.csv", "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
                for row in rows[-count:]:
                    if len(row) > 1:
                        recent_items.append(row[1])
        return recent_items

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
        with open("barcode_history.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, input_code, check_digit, full_gtin])

    def delete_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("تنبيه", "الرجاء تحديد سجل واحد على الأقل للحذف.")
            return
            
        if not messagebox.askyesno("تأكيد", f"هل أنت متأكد من حذف {len(selected_items)} سجل/سجلات؟"):
            return

        # Get values of selected rows to identify them
        items_to_delete = []
        for item in selected_items:
            # values is a tuple of strings corresponding to columns
            values = self.tree.item(item, 'values')
            # (date, input, check, full)
            if values:
                items_to_delete.append(values)

        # Read all existing rows
        if not os.path.exists("barcode_history.csv"):
            return

        new_rows = []
        with open("barcode_history.csv", "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                # Check if this row is in our delete list
                # row structure: [date, input, check, full]
                # We need to match all fields to be safe
                is_deleted = False
                for del_item in items_to_delete:
                    # Convert match to list for comparison if tuple
                    if list(row) == list(del_item):
                        is_deleted = True
                        break
                
                if not is_deleted:
                    new_rows.append(row)

        # Write back
        with open("barcode_history.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(new_rows)

        self.load_history()
        messagebox.showinfo("تم", "تم حذف السجلات المحددة بنجاح.")

    def clear_history(self):
        if not messagebox.askyesno("تأكيد", "هل أنت متأكد من حذف السجل كاملاً؟"):
            return
            
        if os.path.exists("barcode_history.csv"):
            os.remove("barcode_history.csv")
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
        total_width = (len(binary_string) + 14) * module_width 
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
                    # 1. Prepare Code
                    current_code_str = str(current_val).zfill(12)
                    
                    # 2. Check Digit
                    reversed_digits = current_code_str[::-1]
                    total = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed_digits))
                    check_digit = (10 - (total % 10)) % 10
                    full_gtin = current_code_str + str(check_digit)
                    
                    # 3. Generate content
                    svg_content = self.get_ean13_svg_content(full_gtin)
                    
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