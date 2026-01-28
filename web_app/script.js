
// ==========================================
// إعدادات SUPABASE - يجب تعبئة هذه الحقول
// ==========================================
const SUPABASE_URL = 'https://jgzepchquakdocjzjrkv.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpnemVwY2hxdWFrZG9janpqcmt2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1ODI5ODMsImV4cCI6MjA4NTE1ODk4M30.CluRqnJv2ibc69esuQTtp50saS6oD8SIxKlKtSASYXE';

// تهيئة العميل
let _supabase = null;
if (SUPABASE_URL !== 'YOUR_SUPABASE_URL_HERE') {
    // التأكد من أن المكتبة تم تحميلها
    if (typeof supabase !== 'undefined') {
        _supabase = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
    } else {
        console.error("Supabase library not loaded!");
    }
} else {
    console.warn("Supabase keys are missing. Using local mode simulation.");
}

// ==========================================
// تعريف ثوابت التشفير (EAN-13 Patterns)
// ==========================================
const L_CODES = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"];
const G_CODES = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"];
const R_CODES = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001000", "1010000", "1000100", "1001000", "1110100"];
const STRUCTURE = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"];

// ==========================================
// المنطق الأساسي (Logic)
// ==========================================

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));

    document.getElementById(tabId + '-tab').classList.add('active');
    // البحث عن الزر النشط وتفعيله
    const btns = document.querySelectorAll('.tab-btn');
    if (tabId === 'generator') btns[0].classList.add('active');
    else btns[1].classList.add('active');

    if (tabId === 'history') loadHistory();
}

function clearFields() {
    document.getElementById('inputCode').value = '';
    document.getElementById('fullBarcode').value = '';
    document.getElementById('checkDigit').textContent = '-';
    document.getElementById('btnExport').disabled = true;
    document.getElementById('inputCode').focus();
}

async function getLastUsedCode() {
    // 1. محاولة من Supabase
    if (_supabase) {
        const { data, error } = await _supabase
            .from('barcode_history')
            .select('input_code')
            .order('created_at', { ascending: false })
            .limit(1);
        if (data && data.length > 0) return data[0].input_code;
    }
    // 2. محاولة من LocalStorage (احتياطي)
    const local = JSON.parse(localStorage.getItem('barcode_history') || '[]');
    if (local.length > 0) return local[0].input_code;

    return null;
}

async function incrementCode() {
    let currentVal = document.getElementById('inputCode').value.trim();

    if (!currentVal) {
        const last = await getLastUsedCode();
        if (last) currentVal = last;
    }

    if (!currentVal) {
        alert("لا يوجد رقم سابق للزيادة عليه. أدخل رقمًا مبدئيًا.");
        return;
    }

    currentVal = currentVal.replace(/[\s-]/g, '');
    if (!/^\d+$/.test(currentVal)) {
        alert("القيمة الحالية ليست رقمًا صحيحًا.");
        return;
    }

    // التحويل لرقم وزيادة 1 ثم التحويل لنص مرة أخرى مع الحفاظ على الأصفار اليسارية
    // بما أن JS بها حدود في الأرقام الكبيرة، نستخدم BigInt للأمان مع الأرقام الطويلة
    try {
        const nextVal = BigInt(currentVal) + 1n;
        const newCode = nextVal.toString().padStart(12, '0');
        document.getElementById('inputCode').value = newCode;
    } catch (e) {
        alert("خطأ في الرقم");
    }
}

async function calculate() {
    const inputEl = document.getElementById('inputCode');
    const rawCode = inputEl.value.trim().replace(/[\s-]/g, '');
    inputEl.value = rawCode;

    if (!/^\d+$/.test(rawCode) || rawCode.length !== 12) {
        alert("يجب إدخال 12 رقم بالضبط.");
        return;
    }

    // حساب رقم التحقق
    // في بايثون: reversed_digits = raw_code[::-1]
    // الضرب: فردي (من اليمين) * 3، زوجي * 1
    // الاندكس في JS يبدأ من 0 من اليسار. لكي نطابق، نعكس المصفوفة
    const digits = rawCode.split('').reverse().map(Number);
    let total = 0;
    digits.forEach((d, i) => {
        const weight = (i % 2 === 0) ? 3 : 1;
        total += d * weight;
    });

    const checkDigit = (10 - (total % 10)) % 10;
    const fullGtin = rawCode + checkDigit;

    // تحديث الواجهة
    document.getElementById('checkDigit').textContent = checkDigit;
    document.getElementById('fullBarcode').value = fullGtin;
    document.getElementById('btnExport').disabled = false;

    // الحفظ
    await saveRecord(rawCode, checkDigit, fullGtin);
    updateRecentDisplay();
}

async function saveRecord(input, check, full) {
    const record = {
        input_code: input,
        check_digit: String(check),
        full_gtin: full,
        created_at: new Date().toISOString()
    };

    // 1. Supabase
    if (_supabase) {
        const { error } = await _supabase.from('barcode_history').insert([record]);
        if (error) console.error("Supabase Error:", error);
    }

    // 2. LocalStorage (كاش محلي سريع)
    const local = JSON.parse(localStorage.getItem('barcode_history') || '[]');
    local.unshift(record); // إضافة في البداية
    if (local.length > 50) local.pop(); // الاحتفاظ بآخر 50 فقط محلياً
    localStorage.setItem('barcode_history', JSON.stringify(local));
}

async function updateRecentDisplay() {
    let recents = [];
    if (_supabase) {
        const { data } = await _supabase
            .from('barcode_history')
            .select('input_code')
            .order('created_at', { ascending: false })
            .limit(2);
        if (data) recents = data.map(r => r.input_code);
    } else {
        const local = JSON.parse(localStorage.getItem('barcode_history') || '[]');
        recents = local.slice(0, 2).map(r => r.input_code);
    }

    const display = recents.length > 0 ? recents.reverse().join(" - ") : "...";
    document.getElementById('recentDisplay').textContent = display;
}

async function loadHistory() {
    const tbody = document.getElementById('historyTableBody');
    tbody.innerHTML = '<tr><td colspan="4">جاري التحميل...</td></tr>';

    let historyData = [];

    if (_supabase) {
        const { data, error } = await _supabase
            .from('barcode_history')
            .select('*')
            .order('created_at', { ascending: false })
            .limit(50);

        if (data) historyData = data;
        else if (error) console.error(error);
    }

    // إذا فشل Supabase أو لم يكن موجوداً نستخدم المحلي
    if (historyData.length === 0) {
        historyData = JSON.parse(localStorage.getItem('barcode_history') || '[]');
    }

    tbody.innerHTML = '';
    historyData.forEach(row => {
        const tr = document.createElement('tr');
        // تنسيق التاريخ
        const dateStr = new Date(row.created_at).toLocaleString('en-GB');
        tr.innerHTML = `
            <td>${dateStr}</td>
            <td>${row.input_code}</td>
            <td>${row.check_digit}</td>
            <td>${row.full_gtin}</td>
        `;
        tbody.appendChild(tr);
    });
}

// ==========================================
// خوارزمية الرسم (Export SVG)
// ==========================================
function encodeEAN13(code) {
    if (code.length !== 13) return null;
    const first = parseInt(code[0]);
    const left = code.substring(1, 7);
    const right = code.substring(7, 13);

    let binary = "101";
    const structure = STRUCTURE[first];

    for (let i = 0; i < 6; i++) {
        const digit = parseInt(left[i]);
        if (structure[i] === 'L') binary += L_CODES[digit];
        else binary += G_CODES[digit];
    }

    binary += "01010"; // Center Guard

    for (let i = 0; i < 6; i++) {
        const digit = parseInt(right[i]);
        binary += R_CODES[digit];
    }

    binary += "101"; // End Guard
    return binary;
}

function exportSVG() {
    const code = document.getElementById('fullBarcode').value;
    if (!code) return;

    const pattern = encodeEAN13(code);
    if (!pattern) return;

    // إعدادات الرسم (نفس قيم Python)
    const moduleWidth = 1.8;
    const shortBarH = 110;
    const longBarH = 123;
    const fontSize = 20;
    const totalWidth = (95 + 14) * moduleWidth; // تقريباً 196
    const totalHeight = longBarH + 10;

    const startX = 9 * moduleWidth;

    let svgContent = `<svg xmlns="http://www.w3.org/2000/svg" width="${totalWidth}" height="${totalHeight}" viewBox="0 0 ${totalWidth} ${totalHeight}">
        <rect width="100%" height="100%" fill="white"/>`;

    // رسم الأعمدة
    for (let i = 0; i < pattern.length; i++) {
        if (pattern[i] === '1') {
            const x = startX + (i * moduleWidth);
            // Guards positions: start(0-2), middle(45-49), end(92-94)
            const isGuard = (i < 3) || (i >= 45 && i < 50) || (i >= 92);
            const h = isGuard ? longBarH : shortBarH;
            svgContent += `<rect x="${x}" y="0" width="${moduleWidth}" height="${h}" fill="black" shape-rendering="crispEdges"/>`;
        }
    }

    const textY = longBarH + 2; // مكان النصوص

    // Digit 1 (Outside left)
    svgContent += `<text x="${startX - 5}" y="${textY}" font-family="Consolas, monospace" font-size="${fontSize}" text-anchor="end">${code[0]}</text>`;

    // Left Group (6 digits)
    let curX = startX + (3 * moduleWidth);
    for (let i = 0; i < 6; i++) {
        const cx = curX + (3.5 * moduleWidth);
        svgContent += `<text x="${cx}" y="${textY}" font-family="Consolas, monospace" font-size="${fontSize}" text-anchor="middle">${code.substring(1, 7)[i]}</text>`;
        curX += 7 * moduleWidth;
    }

    // Right Group (6 digits) - تبدأ بعد الوسط (50 modules from start)
    curX = startX + (50 * moduleWidth);
    for (let i = 0; i < 6; i++) {
        const cx = curX + (3.5 * moduleWidth);
        svgContent += `<text x="${cx}" y="${textY}" font-family="Consolas, monospace" font-size="${fontSize}" text-anchor="middle">${code.substring(7, 13)[i]}</text>`;
        curX += 7 * moduleWidth;
    }

    // علامة > في النهاية
    svgContent += `<text x="${startX + (95 * moduleWidth) + 5}" y="${textY}" font-family="Consolas, monospace" font-size="${fontSize}" text-anchor="start">&gt;</text>`;
    svgContent += `</svg>`;

    // تحميل الملف
    const blob = new Blob([svgContent], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `EAN13_${code}.svg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// Initial Load
updateRecentDisplay();
