#!/usr/bin/env python3
"""
run_tests.py — regression suite for the aman-digital-hld skill (shared engine with aman-tech-spec)

    python3 tests/run_tests.py [--quick]      (--quick skips the four full example builds)

A. Full builds: every example + the bidi stress test → build OK, QA 0 errors, OOXML schema valid.
B. XML invariants on every built file: RTL/LTR at paragraph, run and table level, code always LTR,
   no unresolved {{refs}} or TOC markers, unique bookmark ids, real TOC field, tokens never split.
C. Negative tests: broken specs must fail with a clear message (and write no file).
D. QA mutation tests: break a good file in known ways → QA must catch each one.
Exit code = number of failed tests.
"""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
EXAMPLES = os.path.join(SKILL, "examples")
OUT = os.path.join(tempfile.gettempdir(), "aman_spec_tests")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
HEB = re.compile(r"[\u05D0-\u05EA]")

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("  ✓ " if ok else "  ✗ ") + name + ("" if ok else f"  →  {detail}"))


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ───────────────────────────── A + B ─────────────────────────────
def build(spec, name):
    out = os.path.join(OUT, name + ".docx")
    r = run([sys.executable, os.path.join(SCRIPTS, "make_spec.py"), spec, out, "--no-preview",
             "--work", os.path.join(OUT, ".build_" + name)])
    return out, r


def xml_invariants(docx, lang, name):
    from lxml import etree
    with zipfile.ZipFile(docx) as z:
        raw = z.read("word/document.xml").decode("utf8")
    root = etree.fromstring(raw.encode("utf8"))
    ns = {"w": W}
    text_all = "".join(root.itertext())
    check(f"{name}: אין הפניות/משתנים שלא נפתרו", "{{" not in text_all, re.findall(r"\{\{[^}]*\}\}", text_all)[:3])
    check(f"{name}: אין סמני תוכן עניינים שנשארו", "@@TOC_" not in raw)
    ids = re.findall(r'<w:bookmarkStart[^>]*w:id="(\d+)"', raw)
    check(f"{name}: מזהי סימניות ייחודיים", len(ids) == len(set(ids)), f"{len(ids)} / {len(set(ids))}")
    bad_para, bad_code, latin_in_rtl, split_tokens, rtl_tables = [], [], [], [], 0
    for p in root.iter(f"{{{W}}}p"):
        ppr = p.find("w:pPr", ns)
        bidi = ppr.find("w:bidi", ns) if ppr is not None else None
        bidi_on = bidi is not None and bidi.get(f"{{{W}}}val") not in ("0", "false")
        runs = p.findall(".//w:r", ns)
        text = "".join("".join(t.text or "" for t in r.iter(f"{{{W}}}t")) for r in runs)
        fonts = [(r.find("w:rPr/w:rFonts", ns).get(f"{{{W}}}ascii") if r.find("w:rPr/w:rFonts", ns) is not None else "") for r in runs if "".join(t.text or "" for t in r.iter(f"{{{W}}}t")).strip()]
        is_code_para = bool(fonts) and all(f == "Consolas" for f in fonts) and ppr is not None and ppr.find("w:shd", ns) is not None
        if is_code_para:
            if bidi_on:
                bad_code.append(text)
            continue
        if lang == "he" and HEB.search(text) and not bidi_on:
            bad_para.append(text)
        if lang == "en" and bidi_on:
            bad_para.append(text)
        prev = None
        for r in runs:
            t = "".join(x.text or "" for x in r.iter(f"{{{W}}}t"))
            rtl = r.find("w:rPr/w:rtl", ns)
            rtl_on = rtl is not None and rtl.get(f"{{{W}}}val") not in ("0", "false")
            if rtl_on and re.search(r"[A-Za-z]", t):
                latin_in_rtl.append(t)
            if prev is not None and prev[1] and not rtl_on and re.search(r"[0-9][0-9:._\-]*$", prev[0]) and re.match(r"[A-Za-z]", t):
                split_tokens.append(prev[0][-6:] + "|" + t[:8])
            if t:
                prev = (t, rtl_on)
    check(f"{name}: כיוון פסקאות ({'RTL' if lang == 'he' else 'LTR'}) בכל הפסקאות", not bad_para, bad_para[:2])
    check(f"{name}: בלוקי קוד תמיד LTR", not bad_code, bad_code[:2])
    if lang == "he":
        check(f"{name}: אין אותיות לטיניות בתוך run מסומן RTL", not latin_in_rtl, latin_in_rtl[:3])
        check(f"{name}: אף טוקן שמתחיל בספרות לא נחתך (12:A3…, 10MB)", not split_tokens, split_tokens[:3])
    for tbl in root.iter(f"{{{W}}}tbl"):
        bv = tbl.find("w:tblPr/w:bidiVisual", ns)
        if bv is not None and bv.get(f"{{{W}}}val") not in ("0", "false"):
            rtl_tables += 1
    n_tbl = len(list(root.iter(f"{{{W}}}tbl")))
    if lang == "he":
        check(f"{name}: כל {n_tbl} הטבלאות בסדר עמודות מימין לשמאל", rtl_tables == n_tbl, f"{rtl_tables}/{n_tbl}")
    else:
        check(f"{name}: אף טבלה לא בסדר RTL", rtl_tables == 0, f"{rtl_tables}/{n_tbl}")
    return raw


def section_ab(quick):
    print("\nA+B. בנייה מלאה ובדיקות XML")
    specs = [(os.path.join(HERE, "stress_he.json"), "stress_he", "he"),
             (os.path.join(HERE, "hld_presets_he.json"), "hld_presets_he", "he")]
    if not quick:
        for f in sorted(os.listdir(EXAMPLES)):
            if f.endswith(".json"):
                specs.append((os.path.join(EXAMPLES, f), f[:-5], json.load(open(os.path.join(EXAMPLES, f)))["meta"].get("lang", "he")))
    built = {}
    for spec, name, lang in specs:
        out, r = build(spec, name)
        log = r.stdout + r.stderr
        ok = r.returncode == 0 and os.path.exists(out)
        check(f"{name}: נבנה, QA ללא שגיאות", ok, log[-600:])
        check(f"{name}: עבר בדיקת סכמת OOXML", "סכמת OOXML: עבר" in log or not os.path.exists("/mnt/skills/public/docx/scripts/office/validate.py"), log[-300:])
        if ok:
            raw = xml_invariants(out, lang, name)
            if json.load(open(spec))["meta"].get("toc", True) is not False and "TOC \\o" in raw:
                check(f"{name}: תוכן עניינים הוא שדה Word עם מספרי עמודים", re.search(r"\t?</w:t>|<w:tab/><w:t[^>]*>\d+</w:t>", raw) is not None)
            built[name] = out
    if "stress_he" in built:
        raw = zipfile.ZipFile(built["stress_he"]).read("word/document.xml").decode("utf8")
        runs = re.findall(r"<w:r>(?:(?!</w:r>).)*?<w:t[^>]*>([^<]*)</w:t></w:r>", raw)
        def ltr_run_with(s):
            return re.search(r'<w:rtl w:val="false"/></w:rPr><w:t[^>]*>[^<]*' + re.escape(s), raw) is not None
        for tok in ["12:A3:72:F1:8B:13", "10MB", "3DS", "4XEDD", "2FA", "Kia Media G5", "C#\u200e", "\u200e.NET 8", "Node.js 20", "IPv4: 10.0.0.1:8080", "OAuth 2.0 Bearer Token"]:
            check(f"stress: \"{tok.strip(chr(0x200e))}\" ב־run אחד משמאל לימין", ltr_run_with(tok))
        nums = re.findall(r'<w:numId w:val="(\d+)"/>', raw)
        check("stress: כל רשימה ממוספרת מתחילה מ־1 (numId נפרד)", len(set(nums)) >= 4, sorted(set(nums)))
        check("stress: גרשיים ואות מבחינה עברית (סה״כ, צ׳ק)", "סה״כ" in raw and "צ׳ק" in raw)
    if "en_lld_elal_tourism_bookings" in built:
        raw = zipfile.ZipFile(built["en_lld_elal_tourism_bookings"]).read("word/document.xml").decode("utf8")
        check("LLD: מזהי דרישות FR-01…FR-08 ו־NFR-01…NFR-06", all(f">FR-0{i}<" in raw for i in range(1, 9)) and ">NFR-06<" in raw)
        check("LLD: מזהי החלטות, סיכונים ובדיקות (D-01, R-01, TC-01)", all(x in raw for x in (">D-01<", ">R-01<", ">TC-01<")))
    return built


# ───────────────────────────── C. negative tests ─────────────────────────────
BASE = {
    "meta": {"lang": "he", "title": "בדיקה"},
    "changelog": [{"version": "1.0", "date": "2026-10-29", "author": "צוות בדיקות", "changes": "גרסה ראשונה"}],
    "sections": [
        {"id": "a", "title": "סעיף א", "blocks": [
            {"type": "p", "text": "טקסט"},
            {"type": "table", "id": "t1", "columns": "api_response", "rows": [{"name": "x", "desc": "d", "type": "String", "example": "1", "notes": ""}]},
            {"type": "code", "id": "j1", "json": {"x": 1}}
        ]}
    ]
}


def neg(name, mutate, expect, renderer=False):
    spec = copy.deepcopy(BASE)
    mutate(spec)
    d = tempfile.mkdtemp(prefix="neg_")
    sp = os.path.join(d, "spec.json")
    json.dump(spec, open(sp, "w"), ensure_ascii=False)
    out = os.path.join(d, "out.docx")
    if renderer:
        r = run([sys.executable, os.path.join(SCRIPTS, "render_diagrams.py"), sp, os.path.join(d, "dg")])
    else:
        man = os.path.join(d, "m.json")
        json.dump({}, open(man, "w"))
        r = run(["node", os.path.join(SCRIPTS, "build_spec.js"), sp, out, "--diagrams", man])
    msg = r.stdout + r.stderr
    ok = r.returncode != 0 and expect in msg and not os.path.exists(out)
    check(f"נכשל כצפוי: {name}", ok, msg.strip()[-300:])
    shutil.rmtree(d, ignore_errors=True)


def S(spec):
    return spec["sections"][0]["blocks"]


def check_logos(built):
    """Aman logo on the left, client logo on the right: LTR header paragraph, left-aligned, right tab stop."""
    src = built.get("hld_presets_he")
    if not src:
        return
    with zipfile.ZipFile(src) as z:
        hdrs = [z.read(n).decode("utf8") for n in z.namelist() if re.match(r"word/header\d+\.xml", n)]
        doc = z.read("word/document.xml").decode("utf8")
    with_logo = [h for h in hdrs if "client_logo" in h]
    check("לוגואים: כותרת עליונה עם לוגו אמן ולוגו לקוח", bool(with_logo), f"{len(hdrs)} headers")
    for h in with_logo:
        ppr = h[h.find("<w:p>"):h.find("<w:drawing")]
        check("לוגואים: פסקת הלוגו משמאל לימין, צמודה לשמאל, טאב ימני ללוגו הלקוח",
              'w:bidi w:val="false"' in ppr and 'w:jc w:val="left"' in ppr and 'w:tab w:val="right"' in ppr, ppr[:200])
    check("שער: לוגו אמן ולוגו לקוח בעמוד השער", 'name="cover_logo"' in doc and 'name="cover_client_logo"' in doc)
    check("שער: מעקב השינויים מתחיל בעמוד חדש", "<w:pageBreakBefore/>" in doc[: doc.find("מעקב שינויים") + 1] or "pageBreakBefore" in doc[doc.find("מעקב שינויים") - 600: doc.find("מעקב שינויים")])


def section_c():
    print("\nC. מפרטים שגויים חייבים להיכשל עם הודעה ברורה")
    neg("JSON לא תקין בבלוק code", lambda s: S(s).append({"type": "code", "language": "json", "text": "{\"a\": 1,}"}), "דוגמת JSON לא תקינה")
    neg("הפניה לסעיף שלא קיים", lambda s: S(s).append({"type": "p", "text": "ראה סעיף {{sec:nope}}"}), "שלא קיים")
    neg("משתנה לא מוגדר", lambda s: S(s).append({"type": "p", "text": "ערך {{foo}}"}), "משתנה לא מוגדר")
    neg("מזהה כפול", lambda s: S(s).append({"type": "table", "id": "t1", "columns": "glossary", "rows": [["a", "b"]]}), "כבר בשימוש")
    neg("סעיף ריק", lambda s: s["sections"].append({"title": "ריק"}), "ריק")
    neg("מספר ערכים בשורה לא תואם לעמודות", lambda s: S(s).append({"type": "table", "columns": "glossary", "rows": [["a", "b", "c"]]}), "ערכים אבל")
    neg("שדה ב־JSON שלא בטבלה (json_fields)", lambda s: (S(s).__setitem__(2, {"type": "code", "id": "j1", "json": {"x": 1, "y": 2}}), s.__setitem__("checks", [{"type": "json_fields", "json": "j1", "table": "t1"}])), "ואינם בטבלה")
    neg("שדה בטבלה שחסר בדוגמה (require_all=error)", lambda s: (S(s)[1]["rows"].append({"name": "z", "desc": "", "type": "", "example": "", "notes": ""}), s.__setitem__("checks", [{"type": "json_fields", "json": "j1", "table": "t1", "require_all": "error"}])), "שחסרים בדוגמה")
    neg("סוג בלוק לא מוכר", lambda s: S(s).append({"type": "paragraph", "text": "x"}), "סוג בלוק לא מוכר")
    neg("גרסה לא עולה במעקב שינויים", lambda s: s["changelog"].append({"version": "0.9", "date": "2026-10-30", "author": "QA", "changes": "x"}), "אינה גדולה")
    neg("meta.version שונה מהגרסה האחרונה", lambda s: s["meta"].__setitem__("version", "2.0"), "שונה מהגרסה האחרונה")
    neg("שפה לא נתמכת", lambda s: s["meta"].__setitem__("lang", "fr"), "meta.lang")
    neg("תמונה שלא קיימת", lambda s: S(s).append({"type": "image", "path": "nope.png"}), "לא נמצא")
    neg("preset עמודות לא מוכר", lambda s: S(s).append({"type": "table", "columns": "nope", "rows": [["a"]]}), "preset עמודות לא מוכר")
    neg("תאריך בפורמט שגוי", lambda s: s["changelog"][0].__setitem__("date", "29/10/2026"), "YYYY-MM-DD")
    neg("עומק סעיפים 4", lambda s: s["sections"][0].__setitem__("sections", [{"title": "2", "sections": [{"title": "3", "sections": [{"title": "4", "blocks": [{"type": "p", "text": "x"}]}]}]}]), "עומק מקסימלי")
    neg("מעקב שינויים חסר", lambda s: s.pop("changelog"), "changelog חסר")
    neg("שדה לא מוכר ב־kv interface", lambda s: S(s).append({"type": "kv", "preset": "interface", "data": {"nme": "x"}}), "שדה לא מוכר")
    neg("תרשים בלי רינדור", lambda s: S(s).append({"type": "diagram", "id": "d1", "mermaid": "flowchart TD\n A-->B"}), "חסר ב־manifest")
    neg("שגיאת תחביר Mermaid + רמז למרכאות", lambda s: S(s).append({"type": "diagram", "id": "d1", "mermaid": "flowchart TD\n  A[שליחה ל-API (POST)] --> B"}), "במרכאות כפולות", renderer=True)
    neg("שם מחבר באנגלית באפיון בעברית", lambda s: s["changelog"][0].__setitem__("author", "Matan Sharon"), "שם המחבר נכתב בעברית")
    neg("שם מחבר בעברית באפיון באנגלית", lambda s: (s["meta"].__setitem__("lang", "en"), s["changelog"][0].__setitem__("author", "מתן שרון")), "written in English")
    neg("קידומת מזהה לא חוקית בטבלה", lambda s: S(s).append({"type": "table", "columns": "requirements", "numbered": "F R", "rows": [["x", "Must", ""]]}), "קידומת מזהה")
    neg("הפניה בתרשים לסעיף שלא קיים", lambda s: S(s).append({"type": "diagram", "id": "d1", "mermaid": "flowchart TD\n  A[סעיף {{sec:zzz}}] --> B"}), "לא קיים", renderer=True)


# ───────────────────────────── E. language check ─────────────────────────────
def section_e():
    print("\nE. בדיקת לשון – חייבת לתפוס שגיאות ולא להתריע על טקסט תקין")
    sys.path.insert(0, SCRIPTS)
    import he_lint
    has_hspell = he_lint.ensure_hspell()
    must = [  # (text, level, category, lang)
        ("תחולת הפרויקט כוללת שני מסכים.", "error", "confusable", "he"),
        ("מחוץ לתחולה: ממשקי ניהול.", "error", "confusable", "he"),
        ("המערכת מחזיר את רשימת ההזמנות.", "error", "agreement", "he"),
        ("אם הממשק מחזירה שגיאה – מוצגת הודעה.", "error", "agreement", "he"),
        ("הטבלה מכיל את כל השדות.", "error", "agreement", "he"),
        ("לאחר עידכון הרשומה נשלחת הודעה.", "error", "spelling", "he"),
        ("השדה נשמר בטבלא הראשית.", "error", "spelling", "he"),
        ("דרישות פונקציונאליות.", "error", "spelling", "he"),
        ("חשוב לציין כי השירות מחזיר רשימה.", "warning", "ai-style", "he"),
        ("השירות זמין בצורה חלקה ומהירה.", "warning", "ai-style", "he"),
        ("הקריאה נשלחת לנקודת קצה ייעודית.", "warning", "terms", "he"),
        ("השרת מחזיר אסימון לאחר האימות.", "warning", "terms", "he"),
        ("הנתונים מוחזרים עם עימוד.", "warning", "terms", "he"),
        ("השדה הינו שדה חובה.", "warning", "register", "he"),
        ("במידה והשדה ריק מוחזרת שגיאה.", "warning", "register", "he"),
        ("ראה דוגמא בסעיף 7.", "warning", "register", "he"),
        ("השירות – מחזיר – רשימה – ממוינת – לפי תאריך.", "warning", "ai-style", "he"),
        ("The service provides a seamless and robust experience.", "warning", "ai-style", "en"),
        ("We leverage the queue in order to retry.", "warning", "ai-style", "en"),
    ]
    if has_hspell:
        must.append(("המשתתמש שולח בקשה.", "error", "spelling", "he"))
    for text, lvl, cat, lang in must:
        found = he_lint.lint_texts([("t", text)], lang=lang)
        check(f"לשון תופס [{cat}]: {text[:40]}", any(f[0] == lvl and f[1] == cat for f in found), found)
    clean = [
        "תאריך תחולת הפוליסה נשמר בטבלה.", "תכולת הפרויקט כוללת שני מסכים.", "כפתור המערכת מוצג בראש המסך.",
        "השירות מחזיר את רשימת ההזמנות, ממוינת לפי תאריך.", "הטבלה מכילה את כל השדות.",
        "אם הממשק מחזיר שגיאה, מוצגת הודעה למשתמש.", "הקריאה ל־Endpoint כוללת Token בכותרת Authorization.",
        "ההזמנות, הרשומות והטיסות נשמרות בבסיס הנתונים.", "מסלול הנסיעה וכו' מוצגים במסך.",
    ]
    for text in clean:
        found = [f for f in he_lint.lint_texts([("t", text)], lang="he") if f[0] == "error"]
        check(f"לשון לא מתריע על טקסט תקין: {text[:40]}", not found, found)
    if not has_hspell:
        print("  (hspell לא זמין – בדיקות האיות המלאות דולגו)")
    # the build itself stops on language errors
    spec = copy.deepcopy(BASE)
    S(spec).append({"type": "p", "text": "תחולת העבודה כוללת מסך אחד."})
    d = tempfile.mkdtemp(prefix="lint_")
    sp = os.path.join(d, "spec.json")
    json.dump(spec, open(sp, "w"), ensure_ascii=False)
    r = run([sys.executable, os.path.join(SCRIPTS, "make_spec.py"), sp, os.path.join(d, "o.docx"), "--no-preview"])
    check("הבנייה נעצרת על שגיאת לשון (תחולה/תכולה)", r.returncode != 0 and "שגיאות לשון" in r.stdout and not os.path.exists(os.path.join(d, "o.docx")), r.stdout[-300:])
    shutil.rmtree(d, ignore_errors=True)


# ───────────────────────────── D. QA mutation tests ─────────────────────────────
def mutate_docx(src, dst, fn):
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == "word/document.xml":
                data = fn(data.decode("utf8")).encode("utf8")
            zo.writestr(item, data)


def qa_mut(name, src, fn, expect, level="❌"):
    d = tempfile.mkdtemp(prefix="mut_")
    dst = os.path.join(d, "m.docx")
    mutate_docx(src, dst, fn)
    r = run([sys.executable, os.path.join(SCRIPTS, "qa_spec.py"), dst])
    hit = [l for l in r.stdout.splitlines() if expect in l and level in l]
    check(f"QA תופס: {name}", bool(hit), r.stdout[-500:])
    shutil.rmtree(d, ignore_errors=True)


def section_d(built):
    print("\nD. QA מזהה שבירות ידועות בקובץ תקין")
    src = built.get("he_hld_bsi_extra_club")
    if not src:
        check("QA mutation tests", False, "אין קובץ בסיס")
        return
    r = run([sys.executable, os.path.join(SCRIPTS, "qa_spec.py"), src])
    check("QA על הקובץ המקורי: 0 שגיאות", r.returncode == 0, r.stdout[-400:])

    def drop_bidi(x):  # a Hebrew body paragraph is switched to LTR explicitly
        i = x.find("<w:bidi/>", x.find("<w:body>") + 2000)
        return x[:i] + '<w:bidi w:val="false"/>' + x[i + len("<w:bidi/>"):]
    qa_mut("פסקה עברית בלי RTL", src, drop_bidi, "בלי כיוון מימין לשמאל")
    qa_mut("טבלה בלי סדר עמודות RTL", src, lambda x: x.replace("<w:bidiVisual/>", "", 1), "bidiVisual")
    qa_mut("גרסה בפרטי המסמך ≠ מעקב שינויים", src, lambda x: re.sub(r"(>גרסה</w:t>(?:(?!</w:tr>).)*?<w:t[^>]*>)1\.1(</w:t>)", r"\g<1>9.9\2", x, count=1, flags=re.S), "שונה מהגרסה האחרונה")
    qa_mut("תוכן עניינים לא מעודכן", src, lambda x: re.sub(r"(<w:tab/><w:t[^>]*>)\d+(</w:t>)", r"\g<1>1\2", x), "לא עודכן", level="⚠️")
    qa_mut("הפניה לסעיף שלא קיים", src, lambda x: x.replace("פרק זה מתאר את המערכות המשתתפות", "לפי סעיף 99, פרק זה מתאר את המערכות המשתתפות", 1), "שלא קיימים", level="⚠️")
    qa_mut("שגיאת התאמת מין בטקסט", src, lambda x: x.replace("מקבלי החלטות מוסמכים לאורך הפרויקט ואישור התוצרים.", "המערכת שולף רשומות.", 1), "התאמת מין")
    qa_mut("תחולה במקום תכולה", src, lambda x: x.replace("פרק זה מתאר את המערכות המשתתפות", "תחולת העבודה כוללת את המערכות המשתתפות", 1), "מילה שגויה בהקשר")
    qa_mut("סוגריים הפוכים (אחרי המרה מ־PDF)", src, lambda x: x.replace("(עתידי)", ")עתידי(", 1), "סוגריים הפוכים")
    qa_mut("שינויים במעקב שלא אושרו", src, lambda x: x.replace("</w:p>", '<w:ins w:id="9901" w:author="QA" w:date="2024-01-01T00:00:00Z"/></w:p>', 1), "שינויים במעקב")
    qa_mut("הערה פתוחה", src, lambda x: x.replace("</w:p>", '<w:r><w:commentReference w:id="9902"/></w:r></w:p>', 1), "הערות פתוחות")


def main():
    quick = "--quick" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    built = section_ab(quick)
    check_logos(built)
    section_c()
    section_e()
    if not quick:
        section_d(built)
    failed = [r for r in results if not r[1]]
    print(f"\nסה״כ: {len(results)} בדיקות, {len(results) - len(failed)} עברו, {len(failed)} נכשלו")
    for n, _, d in failed:
        print(f"  ✗ {n}: {str(d)[:200]}")
    sys.exit(len(failed))


if __name__ == "__main__":
    main()
