
// ==========================================
// عميل الواجهة الخلفية (SQLite عبر REST)
// ==========================================
// الواجهة تُقدَّم من نفس خادم Flask الذي يوفّر /api (same-origin) — لا حاجة لعنوان خارجي.
const API_BASE = '';
const LOCAL_KEY = 'barcode_history';

// طلب REST موحّد؛ يرمي استثناءً عند فشل الشبكة أو رمز حالة غير ناجح.
async function apiRequest(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(API_BASE + path, opts);
    if (!res.ok) {
        let detail = 'HTTP ' + res.status;
        try { const j = await res.json(); if (j && j.error) detail = j.error; } catch (_) { }
        throw new Error(detail);
    }
    if (res.status === 204) return null;
    const text = await res.text();
    return text ? JSON.parse(text) : null;
}

// كاش محلي احتياطي (يُستخدم فقط عند تعذّر الوصول للخادم)
const readLocal = () => JSON.parse(localStorage.getItem(LOCAL_KEY) || '[]');
const writeLocal = (arr) => localStorage.setItem(LOCAL_KEY, JSON.stringify(arr));
const newLocalId = () => (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID() : (Date.now() + '_' + Math.random());

// ==========================================
// تعريف ثوابت التشفير (EAN-13 Patterns)
// ==========================================
const L_CODES = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"];
const G_CODES = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"];
const R_CODES = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"];
const STRUCTURE = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"];

// ==========================================
// المنطق الأساسي (Logic)
// ==========================================

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.remove('active');
        el.setAttribute('aria-selected', 'false');
    });

    document.getElementById(tabId + '-tab').classList.add('active');
    // تفعيل زر التبويب المطابق (يدعم أي عدد من التبويبات)
    const activeBtn = document.getElementById('tab-' + tabId);
    if (activeBtn) {
        activeBtn.classList.add('active');
        activeBtn.setAttribute('aria-selected', 'true');
    }

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
    // 1. من الخادم (المصدر الموثوق)
    try {
        const data = await apiRequest('GET', '/api/history?order=code&limit=1');
        if (Array.isArray(data) && data.length > 0) return data[0].input_code;
        return null; // الخادم متاح لكن لا سجلات
    } catch (e) {
        console.warn('getLastUsedCode: تعذّر الوصول للخادم، سيُستخدم الكاش المحلي', e);
    }
    // 2. احتياطي من LocalStorage عند تعذّر الوصول للخادم
    const local = readLocal();
    if (local.length > 0) {
        // ترتيب تنازلي حسب رقم المنتج (الأصفار البادئة تجعل الترتيب النصي = الرقمي)
        local.sort((a, b) => (a.input_code < b.input_code ? 1 : (a.input_code > b.input_code ? -1 : 0)));
        return local[0].input_code;
    }

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
        if (newCode.length > 12) {
            alert("تم بلوغ الحد الأقصى للرقم (12 خانة).");
            return;
        }
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
        full_gtin: full
    };

    // 1. الخادم (المصدر الموثوق) — يُرجِع السجل بمعرّف وطابع زمني من الخادم
    let saved = null;
    try {
        saved = await apiRequest('POST', '/api/history', record);
    } catch (e) {
        console.error('saveRecord: فشل الحفظ في الخادم', e);
    }

    // 2. كاش محلي سريع/احتياطي
    const local = readLocal();
    local.unshift({
        ...(saved || { ...record, created_at: new Date().toISOString() }),
        local_id: newLocalId()
    }); // إضافة في البداية
    if (local.length > 50) local.pop(); // الاحتفاظ بآخر 50 فقط محلياً
    writeLocal(local);
    return saved;
}

async function updateRecentDisplay() {
    let recents = [];
    try {
        const data = await apiRequest('GET', '/api/history?order=recent&limit=2');
        recents = (data || []).map(r => r.input_code);
    } catch (e) {
        const local = readLocal();
        recents = local.slice(0, 2).map(r => r.input_code);
    }

    const display = recents.length > 0 ? recents.reverse().join(" - ") : "...";
    document.getElementById('recentDisplay').textContent = display;
}

async function loadHistory() {
    const tbody = document.getElementById('historyTableBody');
    tbody.innerHTML = '<tr><td colspan="5">جاري التحميل...</td></tr>';

    let historyData = [];
    let usedApi = false;

    try {
        historyData = await apiRequest('GET', '/api/history?order=code&limit=50') || [];
        usedApi = true;
    } catch (e) {
        console.error('loadHistory: تعذّر الوصول للخادم، سيُستخدم الكاش المحلي', e);
    }

    // نلجأ للكاش المحلي فقط عند تعذّر الوصول للخادم (النتيجة الفارغة من الخادم ليست خطأ)
    if (!usedApi) {
        historyData = readLocal();
        // Sort by input_code descending
        historyData.sort((a, b) => {
            if (a.input_code < b.input_code) return 1;
            if (a.input_code > b.input_code) return -1;
            return 0;
        });
    }

    tbody.innerHTML = '';
    historyData.forEach((row, index) => {
        const tr = document.createElement('tr');
        // تنسيق التاريخ
        const dateStr = new Date(row.created_at).toLocaleString('en-GB');

        // معرّف الصف: id من قاعدة البيانات، وإلا local_id المحلي، وإلا الطابع الزمني (توافق قديم)
        const rowId = row.id ? row.id : (row.local_id || row.created_at);

        // بناء الخلايا عبر DOM APIs حتى لا تُفسَّر القيم كـ HTML (حماية من XSS المخزَّن)
        const tdChk = document.createElement('td');
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'row-checkbox';
        cb.value = rowId;
        cb.dataset.isDb = String(!!row.id);
        cb.setAttribute('aria-label', 'تحديد السجل ' + (row.input_code || ''));
        tdChk.appendChild(cb);

        // خلية نصية خاملة (textContent) لا تُفسَّر كترميز
        const mk = (v) => { const td = document.createElement('td'); td.textContent = (v === undefined || v === null) ? '' : v; return td; };
        tr.append(tdChk, mk(dateStr), mk(row.input_code), mk(row.check_digit), mk(row.full_gtin));
        tbody.appendChild(tr);
    });
}

function toggleSelectAll() {
    const mainCheck = document.getElementById('selectAll');
    const rows = document.querySelectorAll('.row-checkbox');
    rows.forEach(cb => cb.checked = mainCheck.checked);
}

async function deleteSelected() {
    const checkboxes = document.querySelectorAll('.row-checkbox:checked');
    if (checkboxes.length === 0) {
        alert("الرجاء تحديد سجل واحد على الأقل.");
        return;
    }

    if (!confirm(`هل أنت متأكد من حذف ${checkboxes.length} سجل؟`)) return;

    const btn = document.querySelector('button[onclick="deleteSelected()"]');
    const oldText = btn.innerText;
    btn.innerText = "جاري الحذف...";
    btn.disabled = true;

    try {
        const dbIds = [];
        const localKeys = [];
        const gtins = [];

        checkboxes.forEach(cb => {
            const tr = cb.closest('tr');
            const gtin = tr && tr.children[4] ? tr.children[4].textContent : null;
            if (gtin) gtins.push(gtin);
            if (cb.dataset.isDb === "true") dbIds.push(cb.value);
            else localKeys.push(cb.value);
        });

        // 1. حذف من الخادم عبر المعرّفات
        if (dbIds.length > 0) {
            await apiRequest('DELETE', '/api/history', { ids: dbIds });
        }

        // 2. مزامنة الكاش المحلي: احذف بالمعرّف المحلي وبالباركود الكامل
        let local = readLocal();
        local = local.filter(item =>
            !localKeys.includes(item.local_id || item.created_at) &&
            !gtins.includes(item.full_gtin));
        writeLocal(local);

        await loadHistory();
        updateRecentDisplay();
        document.getElementById('selectAll').checked = false;
        alert("تم الحذف بنجاح ✅");

    } catch (e) {
        console.error(e);
        alert("حدث خطأ: " + e.message);
    } finally {
        btn.innerText = oldText;
        btn.disabled = false;
    }
}

async function clearHistory() {
    if (!confirm("هل أنت متأكد من رغبتك في حذف جميع السجلات؟\nلا يمكن استرجاع البيانات بعد الحذف!")) return;

    const btn = document.querySelector('button[onclick="clearHistory()"]');
    const originalText = btn.innerText;
    btn.innerText = "جاري الحذف...";
    btn.disabled = true;

    try {
        // حذف كل السجلات من الخادم
        await apiRequest('DELETE', '/api/history/all');

        // مسح الكاش المحلي أيضاً
        localStorage.removeItem(LOCAL_KEY);

        // تحديث العرض
        await loadHistory();
        updateRecentDisplay();
        alert("تم حذف السجل بنجاح ✅");

    } catch (e) {
        console.error(e);
        alert("حدث خطأ أثناء الحذف: " + e.message);
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
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
    const totalWidth = (9 + 95 + 7) * moduleWidth; // 9 يسار + 95 قضيباً + 7 يمين = 111 (منطقة هادئة كافية)
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
    return svgContent; // Return content for batch usage
}

// ==========================================
// وظيفة التوليد الجماعي (Batch Generation)
// ==========================================
async function generateBatch() {
    const inputEl = document.getElementById('inputCode');
    const startCodeStr = inputEl.value.trim().replace(/[\s-]/g, '');
    let count = parseInt(document.getElementById('batchCount').value);

    // Validation
    if (!/^\d+$/.test(startCodeStr) || startCodeStr.length !== 12) {
        alert("يجب إدخال 12 رقم صحيح في خانة المنتج.");
        return;
    }
    if (isNaN(count) || count < 1) count = 1;
    if (count > 100) {
        if (!confirm("لقد طلبت عدداً كبيراً (" + count + "). قد يستغرق ذلك بعض الوقت. هل تود الاستمرار؟")) return;
    }

    const zip = new JSZip();
    const recordsToInsert = [];
    let currentBigInt = BigInt(startCodeStr);

    // واجهة التحميل البدائية
    const btn = document.getElementById('btnBatch');
    const originalText = btn.innerText;
    btn.innerText = "جاري العمل... ⏳";
    btn.disabled = true;

    try {
        for (let i = 0; i < count; i++) {
            // 1. Calculate Code
            const currentCode = currentBigInt.toString().padStart(12, '0');

            // Calculate Check Digit
            const digits = currentCode.split('').reverse().map(Number);
            let total = 0;
            digits.forEach((d, idx) => {
                total += d * ((idx % 2 === 0) ? 3 : 1);
            });
            const checkDigit = (10 - (total % 10)) % 10;
            const fullGtin = currentCode + checkDigit;

            // 2. Generate SVG Content (Custom logic needed here since exportSVG downloads immediately)
            // We need a helper function that returns the SVG string without downloading.
            // I modified exportSVG above to return the content, but let's reimplement a clean helper to avoid DOM deps
            const svgString = createSVGString(fullGtin);

            // 3. Add to ZIP
            zip.file(`EAN13_${fullGtin}.svg`, svgString);

            // 4. Prepare DB Record
            recordsToInsert.push({
                input_code: currentCode,
                check_digit: String(checkDigit),
                full_gtin: fullGtin,
                created_at: new Date().toISOString() // Note: slight offset in time is fine
            });

            // Increment
            currentBigInt += 1n;
        }

        // 5. Generate ZIP File
        const content = await zip.generateAsync({ type: "blob" });
        saveAs(content, `Barcodes_Batch_${startCodeStr}_x${count}.zip`);

        // 6. إدراج جماعي في الخادم
        let inserted = null;
        try {
            inserted = await apiRequest('POST', '/api/history/batch', {
                items: recordsToInsert.map(r => ({
                    input_code: r.input_code, check_digit: r.check_digit, full_gtin: r.full_gtin
                }))
            });
        } catch (e) {
            console.error('Batch insert failed', e);
        }

        // كاش محلي (الأحدث/أعلى رقم عند الفهرس 0)
        const local = readLocal();
        const source = (Array.isArray(inserted) && inserted.length) ? inserted : recordsToInsert;
        source.forEach(r => local.unshift({ ...r, local_id: newLocalId() }));
        if (local.length > 50) local.splice(50);
        writeLocal(local);

        // Update UI
        updateRecentDisplay();
        document.getElementById('inputCode').value = currentBigInt.toString().padStart(12, '0'); // Show next available
        alert(`تم توليد ${count} باركود وتحميلهم بنجاح! ✅`);

    } catch (e) {
        console.error(e);
        alert("حدث خطأ أثناء العملية: " + e.message);
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

// Low-level SVG Helper for Batch (No DOM dependency)
function createSVGString(code) {
    const pattern = encodeEAN13(code);
    if (!pattern) return "";

    const moduleWidth = 1.8;
    const shortBarH = 110;
    const longBarH = 123;
    const fontSize = 20;
    const totalWidth = (9 + 95 + 7) * moduleWidth; // 9 يسار + 95 قضيباً + 7 يمين = 111 (منطقة هادئة كافية)
    const totalHeight = longBarH + 10;
    const startX = 9 * moduleWidth;

    let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${totalWidth}" height="${totalHeight}" viewBox="0 0 ${totalWidth} ${totalHeight}">
        <rect width="100%" height="100%" fill="white"/>`;

    for (let i = 0; i < pattern.length; i++) {
        if (pattern[i] === '1') {
            const x = startX + (i * moduleWidth);
            const isGuard = (i < 3) || (i >= 45 && i < 50) || (i >= 92);
            const h = isGuard ? longBarH : shortBarH;
            svg += `<rect x="${x}" y="0" width="${moduleWidth}" height="${h}" fill="black" shape-rendering="crispEdges"/>`;
        }
    }

    const textY = longBarH + 2;
    svg += `<text x="${startX - 5}" y="${textY}" font-family="Consolas, monospace" font-size="${fontSize}" text-anchor="end">${code[0]}</text>`;

    let curX = startX + (3 * moduleWidth);
    for (let i = 0; i < 6; i++) {
        const cx = curX + (3.5 * moduleWidth);
        svg += `<text x="${cx}" y="${textY}" font-family="Consolas, monospace" font-size="${fontSize}" text-anchor="middle">${code.substring(1, 7)[i]}</text>`;
        curX += 7 * moduleWidth;
    }

    curX = startX + (50 * moduleWidth);
    for (let i = 0; i < 6; i++) {
        const cx = curX + (3.5 * moduleWidth);
        svg += `<text x="${cx}" y="${textY}" font-family="Consolas, monospace" font-size="${fontSize}" text-anchor="middle">${code.substring(7, 13)[i]}</text>`;
        curX += 7 * moduleWidth;
    }

    svg += `<text x="${startX + (95 * moduleWidth) + 5}" y="${textY}" font-family="Consolas, monospace" font-size="${fontSize}" text-anchor="start">&gt;</text>`;
    svg += `</svg>`;

    return svg;
}

// ==========================================
// التحقق العكسي (فكّ وتحقّق من باركود كامل)
// ==========================================
function gs1Country(prefix3) {
    const p = parseInt(prefix3, 10);
    if (isNaN(p)) return null;
    const ranges = [
        [0, 19, 'الولايات المتحدة/كندا'], [30, 39, 'الولايات المتحدة'], [300, 379, 'فرنسا'],
        [400, 440, 'ألمانيا'], [450, 459, 'اليابان'], [460, 469, 'روسيا'], [500, 509, 'المملكة المتحدة'],
        [619, 620, 'تونس'], [621, 621, 'سوريا'], [622, 622, 'مصر'], [625, 625, 'الأردن'],
        [626, 626, 'إيران'], [627, 627, 'الكويت'], [628, 628, 'السعودية'], [629, 629, 'الإمارات'],
        [690, 699, 'الصين'], [729, 729, 'إسرائيل'], [868, 869, 'تركيا'], [870, 879, 'هولندا'], [890, 890, 'الهند']
    ];
    for (const [lo, hi, name] of ranges) if (p >= lo && p <= hi) return name;
    return null;
}

function verifyCode() {
    const inputEl = document.getElementById('verifyInput');
    const raw = inputEl.value.trim().replace(/[\s-]/g, '');
    inputEl.value = raw;
    const box = document.getElementById('verifyResult');
    const barcodeEl = document.getElementById('verifyBarcode');
    box.innerHTML = '';
    barcodeEl.innerHTML = '';
    box.style.display = 'block';

    if (!/^\d{13}$/.test(raw)) {
        const w = document.createElement('div');
        w.className = 'verify-status invalid';
        w.textContent = '⚠ يجب إدخال 13 رقماً بالضبط.';
        box.appendChild(w);
        return;
    }

    const first12 = raw.slice(0, 12);
    const entered = raw[12];
    const digits = first12.split('').reverse().map(Number);
    let total = 0;
    digits.forEach((d, i) => { total += d * ((i % 2 === 0) ? 3 : 1); });
    const computed = String((10 - (total % 10)) % 10);
    const valid = (computed === entered);
    const country = gs1Country(raw.slice(0, 3)) || 'غير محدّد';

    const status = document.createElement('div');
    status.className = 'verify-status ' + (valid ? 'valid' : 'invalid');
    status.textContent = valid ? '✅ باركود صالح' : ('❌ غير صالح — رقم التحقق الصحيح: ' + computed);
    box.appendChild(status);

    const mkRow = (label, value) => {
        const r = document.createElement('div');
        r.className = 'result-row';
        const l = document.createElement('span');
        l.textContent = label;
        const v = document.createElement('span');
        v.className = 'verify-value';
        v.textContent = value;
        r.append(l, v);
        return r;
    };
    box.appendChild(mkRow('نظام الترقيم (أول رقم):', raw[0]));
    box.appendChild(mkRow('بادئة GS1:', raw.slice(0, 3) + '  (' + country + ')'));
    box.appendChild(mkRow('رمز المنتج (12 خانة):', first12));
    box.appendChild(mkRow('رقم التحقق (مُدخل / محسوب):', entered + ' / ' + computed));

    // رسم الباركود (SVG مولّد داخلياً، أرقام فقط — آمن)
    barcodeEl.innerHTML = createSVGString(raw);
}

// Initial Load
updateRecentDisplay();
