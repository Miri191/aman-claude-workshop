#!/usr/bin/env python3
"""
qa_spec.py — QA for technical specifications in Word (Aman Digital)

    python3 qa_spec.py <file.docx> [--spec spec.json] [--lang he|en] [--json]

Works on any spec — ones built by this skill and hand-written ones. Checks:
  כיווניות   Hebrew docs: every Hebrew paragraph RTL, no left/right-swapped alignment, tables in RTL
             column order, English multi-word runs not marked RTL, code/JSON not inside RTL paragraphs,
             reversed parentheses. English docs: nothing marked RTL that has no Hebrew.
  מבנה       heading numbering gaps/duplicates, empty sections, stale table of contents, change log present,
             version on the title page = last change-log version, change-log dates in order.
  הפניות     "סעיף 7.2" / "section 7.2" → must exist; "תרשים 3" / "Figure 3" → must exist.
  JSON       examples must parse; fields in a JSON example that appear in no field table (e.g. a key
             renamed in the example but not in the table) are reported.
  טבלאות     same field twice in a field table, long tables whose header row does not repeat.
  סימונים    TBD / TODO / ??? / לבירור — counted; warns if there is no open-issues section.
  מיתוג      logo in header, page numbers in footer, foreign contact details.
Exit code 1 when errors are found.
"""
import argparse
import json
import re
import sys
import zipfile

try:
    import docx  # python-docx
except ImportError:
    print("python-docx חסר: pip install python-docx --break-system-packages")
    sys.exit(2)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import he_lint  # noqa: E402
HEB = re.compile(r"[\u05D0-\u05EA]")
LAT = re.compile(r"[A-Za-z]")
IDENT = re.compile(r"^[A-Za-z_$][\w$]*(?:\[\])?(?:\.[A-Za-z_$][\w$]*(?:\[\])?)*$")
MONO = ("consolas", "courier", "mono", "menlo", "lucida console")


def short(t, n=60):
    t = re.sub(r"\s+", " ", (t or "")).strip()
    t = re.sub(r"[\u200E\u200F\u2060]", "", t)
    return t if len(t) <= n else t[: n - 1] + "…"


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cat, msg):
        self.items.append((level, cat, msg))

    def err(self, c, m): self.add("error", c, m)
    def warn(self, c, m): self.add("warning", c, m)
    def note(self, c, m): self.add("note", c, m)
    def good(self, c, m): self.add("ok", c, m)

    def count(self, level):
        return sum(1 for x in self.items if x[0] == level)


def on(el, tag):
    """boolean OOXML property present and not switched off"""
    if el is None:
        return None
    x = el.find(W + tag)
    if x is None:
        return None
    return x.get(W + "val") not in ("0", "false", "off")


class Doc:
    def __init__(self, path):
        self.path = path
        self.d = docx.Document(path)
        self.body = self.d.element.body
        self._styles()
        self.paras = []   # dicts in document order (incl. table cells)
        self.blocks = []  # top-level: ("p", para) / ("t", table)
        self._walk()

    def _styles(self):
        st = self.d.styles.element
        self.style = {}
        for s in st.findall(W + "style"):
            sid = s.get(W + "styleId")
            ppr = s.find(W + "pPr")
            based = s.find(W + "basedOn")
            name = s.find(W + "name")
            ol = ppr.find(W + "outlineLvl") if ppr is not None else None
            self.style[sid] = {
                "bidi": on(ppr, "bidi"),
                "based": based.get(W + "val") if based is not None else None,
                "name": (name.get(W + "val") if name is not None else sid) or "",
                "outline": int(ol.get(W + "val")) if ol is not None else None,
            }
        dflt = st.find(f"{W}docDefaults/{W}pPrDefault/{W}pPr")
        self.default_bidi = bool(on(dflt, "bidi"))

    def style_prop(self, sid, prop, depth=0):
        if not sid or sid not in self.style or depth > 12:
            return None
        v = self.style[sid][prop]
        return v if v is not None else self.style_prop(self.style[sid]["based"], prop, depth + 1)

    def _para(self, p, in_table):
        ppr = p.find(W + "pPr")
        ps = ppr.find(W + "pStyle") if ppr is not None else None
        sid = ps.get(W + "val") if ps is not None else "Normal"
        b = on(ppr, "bidi")
        if b is None:
            b = self.style_prop(sid, "bidi")
        if b is None:
            b = self.default_bidi
        jc = ppr.find(W + "jc") if ppr is not None else None
        ol = ppr.find(W + "outlineLvl") if ppr is not None else None
        outline = int(ol.get(W + "val")) if ol is not None else self.style_prop(sid, "outline")
        runs = []
        for r in p.iter(W + "r"):
            rpr = r.find(W + "rPr")
            t = "".join((x.text or "") if x.tag == W + "t" else "\t" for x in r.iter(W + "t", W + "tab"))
            font = ""
            if rpr is not None and rpr.find(W + "rFonts") is not None:
                f = rpr.find(W + "rFonts")
                font = (f.get(W + "ascii") or f.get(W + "hAnsi") or "").lower()
            runs.append({"t": t, "rtl": bool(on(rpr, "rtl")), "font": font,
                         "bold": bool(on(rpr, "b"))})
        text = "".join(x["t"] for x in runs)
        sname = (self.style.get(sid, {}).get("name") or sid).lower()
        mono = bool(text.strip()) and all(any(m in r["font"] for m in MONO) for r in runs if r["t"].strip())
        return {
            "el": p, "text": text, "style": sid, "sname": sname, "bidi": bool(b),
            "jc": jc.get(W + "val") if jc is not None else None, "outline": outline,
            "runs": runs, "in_table": in_table, "numbered": ppr is not None and ppr.find(W + "numPr") is not None,
            "mono": mono, "has_img": p.find(".//" + W + "drawing") is not None,
        }

    def _walk(self):
        for child in self.body.iterchildren():
            if child.tag == W + "p":
                pd = self._para(child, False)
                self.paras.append(pd)
                self.blocks.append(("p", pd))
            elif child.tag == W + "tbl":
                self.blocks.append(("t", child))
                for p in child.iter(W + "p"):
                    self.paras.append(self._para(p, True))
            elif child.tag == W + "sdt":
                for p in child.iter(W + "p"):
                    pd = self._para(p, False)
                    self.paras.append(pd)
                    self.blocks.append(("p", pd))

    @staticmethod
    def table_grid(tbl):
        rows = []
        for tr in tbl.findall(W + "tr"):
            row = []
            for tc in tr.findall(W + "tc"):
                row.append("\n".join("".join(t.text or "" for t in p.iter(W + "t")) for p in tc.findall(W + "p")))
            rows.append(row)
        return rows


# ───────────────────────────── headings ─────────────────────────────
NUM_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(\S.*)$")


def headings(doc):
    out = []
    for kind, p in doc.blocks:
        if kind != "p":
            continue
        text = p["text"].strip()
        if not text:
            continue
        if p["sname"].startswith("toc"):
            continue  # table-of-contents entries are not headings
        lvl = None
        if p["outline"] is not None and p["outline"] < 9:
            lvl = p["outline"] + 1
        elif p["sname"].startswith("heading"):
            m = re.search(r"(\d)", p["sname"])
            lvl = int(m.group(1)) if m else 1
        else:
            # hand-made heading: whole paragraph bold, numbered, short
            m = NUM_RE.match(text)
            if m and len(text) < 90 and p["runs"] and all(r["bold"] for r in p["runs"] if r["t"].strip()) and not p["numbered"]:
                lvl = m.group(1).count(".") + 1
        if lvl is None:
            continue
        m = NUM_RE.match(text)
        out.append({"p": p, "text": text, "level": lvl, "num": m.group(1) if m else None,
                    "title": m.group(2) if m else text})
    return out


def check_structure(doc, hs, rep):
    nums = [h for h in hs if h["num"]]
    if not hs:
        rep.warn("מבנה", "לא נמצאו כותרות (Heading) — אין ניווט ואין תוכן עניינים")
        return set()
    seen, problems = set(), []
    counters = {}
    for h in nums:
        n = h["num"]
        parts = [int(x) for x in n.split(".")]
        if n in seen:
            problems.append(f"\"{n}\" מופיע פעמיים")
        seen.add(n)
        parent = tuple(parts[:-1])
        prev = counters.get(parent, 0)
        if parts[-1] != prev + 1:
            problems.append(f"אחרי {'.'.join(map(str, parent + (prev,))) if prev else ('תחילת ' + ('.'.join(map(str, parent)) or 'המסמך'))} מגיע {n}")
        counters[parent] = parts[-1]
        for k in list(counters):
            if len(k) > len(parent) and k[:len(parent) + 1] != tuple(parts):
                if k[:len(parts)] != tuple(parts):
                    counters.pop(k, None)
    if problems:
        rep.warn("מבנה", f"מספור כותרות לא רציף: {'; '.join(problems[:6])}")
    elif nums:
        rep.good("מבנה", f"{len(nums)} כותרות ממוספרות ברצף")
    # empty sections
    idx = {id(p): i for i, (k, p) in enumerate(doc.blocks) if k == "p"}
    empty = []
    for a, b in zip(hs, hs[1:]):
        ia, ib = idx.get(id(a["p"])), idx.get(id(b["p"]))
        if ia is None or ib is None or b["level"] > a["level"]:
            continue
        if not a["num"] and b["num"]:
            continue  # unnumbered divider ("חלק א", "Part A") followed by a numbered section
        between = [x for x in doc.blocks[ia + 1:ib] if x[0] == "t" or (x[1]["text"].strip() or x[1]["has_img"])]
        if not between:
            empty.append(a["text"])
    if empty:
        rep.warn("מבנה", f"{len(empty)} סעיפים ריקים (כותרת ואחריה מיד כותרת נוספת): " + "; ".join(f"\"{short(x, 40)}\"" for x in empty[:4]))
    return {h["num"] for h in nums}


def check_toc(doc, hs, rep):
    toc = [p for p in doc.paras if p["sname"].startswith("toc")]
    instr = "".join(x.text or "" for x in doc.body.iter(W + "instrText"))
    if not toc:
        if len([h for h in hs if h["level"] == 1]) >= 6:
            rep.note("מבנה", "אין תוכן עניינים במסמך עם 6 סעיפים ראשיים ומעלה")
        return
    pages = []
    for p in toc:
        m = re.search(r"\t\s*(\d+)\s*$", p["text"]) or re.search(r"(\d+)\s*$", p["text"])
        if m:
            pages.append(int(m.group(1)))
    if len(pages) >= 4 and len(set(pages)) == 1:
        rep.warn("מבנה", f"תוכן העניינים לא עודכן — כל {len(pages)} הרשומות מצביעות על עמוד {pages[0]}")
    elif len(toc) >= 2 and len(pages) < len(toc) // 2:
        rep.warn("מבנה", "בתוכן העניינים חסרים מספרי עמודים")
    if pages and any(b < a for a, b in zip(pages, pages[1:])):
        rep.warn("מבנה", "מספרי העמודים בתוכן העניינים אינם עולים — כנראה לא עודכן")
    if "TOC" not in instr:
        rep.note("מבנה", "תוכן העניינים אינו שדה Word — לא יתעדכן אוטומטית")
    titles = {re.sub(r"\s+", " ", re.sub(r"[\u200E\u200F]", "", h["text"])) for h in hs}
    entries = [re.sub(r"\s+", " ", re.sub(r"[\u200E\u200F]|\t.*$|\s*\d+\s*$", "", p["text"])).strip() for p in toc]
    stale = [e for e in entries if e and e not in titles and not any(t.startswith(e) for t in titles)]
    if stale:
        rep.warn("מבנה", f"{len(stale)} רשומות בתוכן העניינים לא תואמות לכותרות: " + "; ".join(f"\"{short(x, 40)}\"" for x in stale[:3]))


def tables(doc):
    return [b for k, b in doc.blocks if k == "t"]


def check_changelog(doc, rep, spec):
    log = None
    details = {}
    for tbl in tables(doc):
        g = Doc.table_grid(tbl)
        if not g:
            continue
        head = " | ".join(g[0])
        if re.search(r"גרסה|גירסה|Version", head, re.I) and re.search(r"תאריך|Date", head, re.I) and log is None:
            log = g
        for row in g:
            if len(row) == 2 and row[0].strip() in ("גרסה", "Version", "מספר גרסה"):
                details["version"] = row[1].strip()
    if log is None:
        rep.warn("מבנה", "לא נמצאה טבלת מעקב שינויים (גרסה / תאריך / תיאור)")
        return
    head = log[0]
    vi = next((i for i, h in enumerate(head) if re.search(r"גרסה|גירסה|Version", h, re.I)), None)
    di = next((i for i, h in enumerate(head) if re.search(r"תאריך|Date", h, re.I)), None)
    rows = [r for r in log[1:] if any(c.strip() for c in r)]
    rep.good("מבנה", f"טבלת מעקב שינויים: {len(rows)} שורות")
    if vi is not None and rows:
        last = rows[-1][vi].strip() if vi < len(rows[-1]) else ""
        if details.get("version") and last and details["version"] != last:
            rep.err("מבנה", f"הגרסה בפרטי המסמך ({details['version']}) שונה מהגרסה האחרונה במעקב השינויים ({last})")
    if di is not None:
        def parse(s):
            m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", s)
            if m:
                y = int(m.group(3)); y = y + 2000 if y < 100 else y
                return (y, int(m.group(2)), int(m.group(1)))
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
            if m:
                return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            m = re.search(r"(\d{1,2}) ([A-Z][a-z]+) (\d{4})", s)
            if m:
                months = "January February March April May June July August September October November December".split()
                if m.group(2) in months:
                    return (int(m.group(3)), months.index(m.group(2)) + 1, int(m.group(1)))
            return None
        ds = [parse(r[di]) for r in rows if di < len(r)]
        ds = [d for d in ds if d]
        if any(b < a for a, b in zip(ds, ds[1:])):
            rep.warn("מבנה", "תאריכים במעקב השינויים אינם בסדר כרונולוגי")


# ───────────────────────────── direction ─────────────────────────────
def looks_code(p):
    t = p["text"].strip()
    if p["mono"]:
        return True
    return bool(re.match(r'^([{}\[\]]|"[\w$@.\-]+"\s*:|(GET|POST|PUT|PATCH|DELETE) /|Authorization:|Accept:|Host:)', t)) and not HEB.search(t)


def check_direction(doc, rep, lang):
    no_bidi, swapped, latin_rtl, code_rtl, typed, rev_par, ltr_he = [], [], [], [], [], [], []
    bad_ltr_para, bad_tbl_dir = [], 0
    for p in doc.paras:
        text = p["text"]
        if not text.strip():
            continue
        code = looks_code(p)
        if lang == "he":
            if HEB.search(text) and not p["bidi"] and not code:
                no_bidi.append(text)
            if p["bidi"] and p["jc"] in ("right", "end") and HEB.search(text):
                swapped.append(text)
            if code and p["bidi"] and not (p["in_table"] and p["mono"]):  # mono table cells = our LTR code cells
                code_rtl.append(text)
            for r in p["runs"]:
                if r["rtl"] and re.search(r"[A-Za-z][A-Za-z0-9.#+\-]*\s+[A-Za-z]", r["t"]):
                    latin_rtl.append(r["t"])
        else:
            if p["bidi"] and not HEB.search(text):
                bad_ltr_para.append(text)
            for r in p["runs"]:
                if r["rtl"] and LAT.search(r["t"]) and not HEB.search(r["t"]):
                    latin_rtl.append(r["t"])
        if not p["numbered"] and re.match(r"^\s*[•◦▪●·]\s", text):
            typed.append(text)
        if p["numbered"] and re.match(r"^\s*\d+[.)]\s", text):
            typed.append(text)
        if re.search(r"\)[\u0590-\u05FF][^()]{0,60}\(", text) or re.search(r"\([A-Za-z][^()]{0,40}\)\s*\)", text):
            rev_par.append(text)

    def ex(lst, n=3):
        return "; ".join(f"\"{short(x, 45)}\"" for x in lst[:n])

    if lang == "he":
        if no_bidi:
            rep.err("כיווניות", f"{len(no_bidi)} פסקאות בעברית בלי כיוון מימין לשמאל — יוצגו מיושרות לשמאל ובסדר שגוי. לדוגמה: {ex(no_bidi)}")
        else:
            rep.good("כיווניות", "כל הפסקאות בעברית מוגדרות מימין לשמאל")
        if swapped:
            rep.warn("כיווניות", f"{len(swapped)} פסקאות בעברית מיושרות בפועל לשמאל (right/end בפסקת RTL = שמאל ב־Word). לדוגמה: {ex(swapped)}")
        if code_rtl:
            rep.warn("כיווניות", f"{len(code_rtl)} שורות קוד/JSON בתוך פסקאות מימין לשמאל — סוגריים ומרכאות עלולים להתהפך ב־Word. לדוגמה: {ex(code_rtl)}")
        if latin_rtl:
            rep.warn("כיווניות", f"{len(latin_rtl)} קטעי אנגלית (כמה מילים) מסומנים RTL — Word עלול להפוך את סדר המילים. לדוגמה: {ex(latin_rtl)}")
    else:
        if bad_ltr_para:
            rep.err("כיווניות", f"{len(bad_ltr_para)} פסקאות באנגלית מוגדרות מימין לשמאל. לדוגמה: {ex(bad_ltr_para)}")
        else:
            rep.good("כיווניות", "כל הפסקאות באנגלית מוגדרות משמאל לימין")
        if latin_rtl:
            rep.err("כיווניות", f"{len(latin_rtl)} קטעי אנגלית מסומנים RTL. לדוגמה: {ex(latin_rtl)}")
    if typed:
        rep.warn("עיצוב", f"{len(typed)} תבליטים/מספרים מוקלדים ידנית (• או \"1.\" בתוך רשימה) — לא רשימה אמיתית. לדוגמה: {ex(typed)}")
    if rev_par:
        rep.err("כיווניות", f"{len(rev_par)} מקומות עם סוגריים הפוכים. לדוגמה: {ex(rev_par)}")

    n_tbl = 0
    for tbl in tables(doc) + [t for t in doc.body.iter(W + "tbl") if t.getparent() is not doc.body]:
        text = "".join(t.text or "" for t in tbl.iter(W + "t"))
        tpr = tbl.find(W + "tblPr")
        rtl_tbl = on(tpr, "bidiVisual")
        n_tbl += 1
        if lang == "he" and HEB.search(text) and not rtl_tbl:
            bad_tbl_dir += 1
        if lang == "en" and rtl_tbl and not HEB.search(text):
            bad_tbl_dir += 1
    if bad_tbl_dir:
        if lang == "he":
            rep.err("כיווניות", f"{bad_tbl_dir} טבלאות בעברית בסדר עמודות משמאל לימין (חסר bidiVisual) — העמודה הראשונה מופיעה משמאל")
        else:
            rep.err("כיווניות", f"{bad_tbl_dir} טבלאות באנגלית בסדר עמודות מימין לשמאל")
    elif n_tbl:
        rep.good("כיווניות", f"{n_tbl} טבלאות — סדר עמודות תקין")


# ───────────────────────────── references & placeholders ─────────────────────────────
def check_refs(doc, nums, rep, lang):
    text_paras = [p for p in doc.paras if not p["sname"].startswith("toc") and not looks_code(p)]
    bad = []
    pat = re.compile(r"(?:(?<![\u05D0-\u05EA])[בלמשה]?(?:סעיף|סעיפים)|[Ss]ections?)\s+(\d+(?:\.\d+)*)(?!\.\d)")
    for p in text_paras:
        t = p["text"]
        for m in pat.finditer(t):
            n = m.group(1).rstrip(".")
            ctx = t[max(0, m.start() - 40): m.end() + 10]
            if re.search(r"סטנדרט|תקן|מסמך ה|standard|RFC|ISO", ctx, re.I):
                continue  # reference to an external document
            if nums and n not in nums:
                bad.append(f"{m.group(0)} (\"{short(ctx, 50)}\")")
    if bad:
        rep.warn("הפניות", f"{len(bad)} הפניות לסעיפים שלא קיימים במסמך: " + "; ".join(bad[:5]))
    elif nums:
        rep.good("הפניות", "כל ההפניות לסעיפים מצביעות על סעיפים קיימים")
    caps = [p for p in doc.paras if re.match(r"^\s*(תרשים|איור|Figure)\s+\d+\s*[–\-:]", p["text"])]
    fig_nums = {int(re.search(r"\d+", p["text"]).group()) for p in caps}
    if fig_nums:
        badf = []
        for p in text_paras:
            if p in caps:
                continue
            for m in re.finditer(r"(?:תרשים|איור|Figure)\s+(\d+)", p["text"]):
                if int(m.group(1)) not in fig_nums:
                    badf.append(m.group(0))
        if badf:
            rep.warn("הפניות", f"הפניות לתרשימים שלא קיימים: {', '.join(badf[:5])}")
    imgs = [p for p in doc.paras if p["has_img"] and not p["in_table"]]
    if imgs:
        rep.note("תמונות", f"{len(imgs)} פסקאות עם תמונות/תרשימים, {len(caps)} כיתובים ממוספרים. מספרים וטקסט בתוך תמונות לא נבדקים.")


def check_placeholders(doc, hs, rep):
    pat = re.compile(r"\bTBD\b|\bTODO\b|\bXXX\b|\?\?\?|לבירור|להשלים|יושלם בהמשך|lorem ipsum", re.I)
    hits = []
    for p in doc.paras:
        for m in pat.finditer(p["text"]):
            hits.append((m.group(0), p["text"]))
    if not hits:
        return
    kinds = sorted({h[0] for h in hits})
    open_sec = any(re.search(r"פתוח|לבירור|open issue|open question|החלטות", h["text"], re.I) for h in hs)
    msg = f"{len(hits)} סימני השלמה ({', '.join(kinds)}). לדוגמה: \"{short(hits[0][1], 60)}\""
    if open_sec:
        rep.note("השלמות", msg + " — ודא שכולם מופיעים בסעיף הסוגיות הפתוחות")
    else:
        rep.warn("השלמות", msg + " — ואין סעיף סוגיות/החלטות פתוחות")


# ───────────────────────────── JSON & field tables ─────────────────────────────
def json_blocks(doc):
    """Group consecutive paragraphs into JSON documents (balanced braces) and parse them."""
    out = []
    ps = doc.paras
    i = 0
    while i < len(ps):
        t = ps[i]["text"].strip()
        if t and t[0] in "{[" and not HEB.search(t[:2]):
            buf, depth, j, instr = [], 0, i, False
            while j < len(ps) and j - i < 600:
                line = ps[j]["text"]
                buf.append(line)
                k = 0
                while k < len(line):
                    ch = line[k]
                    if instr:
                        if ch == "\\":
                            k += 1
                        elif ch == '"':
                            instr = False
                    elif ch == '"':
                        instr = True
                    elif ch in "{[":
                        depth += 1
                    elif ch in "}]":
                        depth -= 1
                    k += 1
                instr = False
                if depth <= 0:
                    break
                j += 1
            raw = "\n".join(buf)
            ctx = next((ps[k]["text"].strip() for k in range(i - 1, max(-1, i - 4), -1) if ps[k]["text"].strip()), "")
            if depth == 0 and len(raw) > 2 and ('"' in raw or raw.strip() in ("{}", "[]")):
                try:
                    out.append({"ok": True, "data": json.loads(raw), "first": buf[0], "raw": raw, "ctx": ctx})
                except json.JSONDecodeError as e:
                    out.append({"ok": False, "err": str(e), "first": buf[0], "raw": raw, "ctx": ctx})
                i = j + 1
                continue
        i += 1
    return out


def flatten(v, prefix="", out=None):
    out = set() if out is None else out
    if isinstance(v, list):
        p = prefix
        if p:
            out.add(p)
        for el in v:
            flatten(el, p, out)
    elif isinstance(v, dict):
        if prefix:
            out.add(prefix)
        for k, x in v.items():
            flatten(x, f"{prefix}.{k}" if prefix else k, out)
    elif prefix:
        out.add(prefix)
    return out


FIELD_HEAD = re.compile(r"^(path|field|field name|name|column|parameter|שם השדה|שם שדה|שם לועזי|שם שדה בממשק|שם בשירות|שם הפרמטר|שם העמודה)\b", re.I)


def field_identifiers(doc):
    ids = set()
    tbl_dupes = []
    for tbl in tables(doc) + [t for t in doc.body.iter(W + "tbl") if t.getparent() is not doc.body]:
        g = Doc.table_grid(tbl)
        if len(g) < 2:
            continue
        cols = [i for i, h in enumerate(g[0]) if FIELD_HEAD.match(h.strip().replace("Path (camelCase)", "Path"))]
        for ci in cols:
            canon = bool(re.match(r"^(path|field|field name|column|שם השדה|שם שדה|שם העמודה|שם הפרמטר)$", re.sub(r"\(.*?\)", "", g[0][ci]).strip(), re.I))
            seen = {}
            for ri, row in enumerate(g[1:], 2):
                if ci >= len(row) or len(row) < len(g[0]):
                    continue  # merged group row
                cell = re.sub(r"[\u200E\u200F]", "", row[ci]).strip().split("\n")[0].strip()
                tok = cell.split()[0] if cell.split() else ""
                if IDENT.match(tok):
                    ids.add(tok.replace("[]", ""))
                    if tok in seen and canon:
                        tbl_dupes.append(tok)
                    seen[tok] = ri
    return ids, tbl_dupes


def check_json(doc, rep, strict=False, lenient_allowed=0):
    blocks = json_blocks(doc)
    if not blocks:
        return
    bad = [b for b in blocks if not b["ok"]]
    good = [b for b in blocks if b["ok"]]
    if bad and len(bad) <= lenient_allowed:
        rep.note("JSON", f"{len(bad)} דוגמאות JSON עם השמטות מכוונות (מסומנות lenient במפרט) — לא נבדקו תחבירית")
    elif bad:
        f = rep.err if strict else rep.warn
        f("JSON", f"{len(bad)} דוגמאות JSON לא תקינות: " + "; ".join(f"אחרי \"{short(b['ctx'], 30)}\" — {b['err']}" for b in bad[:3]))
    if good:
        rep.good("JSON", f"{len(good)} דוגמאות JSON תקינות תחבירית")
    ids, dupes = field_identifiers(doc)
    if dupes:
        rep.warn("טבלאות", f"שדות שמופיעים פעמיים באותה טבלת שדות: {', '.join(sorted(set(dupes))[:8])}")
    if not ids:
        return
    dotted = sum(1 for x in ids if "." in x) >= 3
    envelope = ("pagination", "_links", "links", "errors")
    agg, checked = {}, 0
    def covered(p):
        if dotted:
            return any(t == p or p.startswith(t + ".") or t.startswith(p + ".") for t in ids)
        return p.split(".")[-1] in ids or any(t == p or p.startswith(t + ".") or t.startswith(p + ".") for t in ids)

    for b in good:
        # tables may document paths with or without the "data" envelope – use whichever fits better
        variants = [b["data"]]
        if isinstance(b["data"], dict) and isinstance(b["data"].get("data"), (list, dict)):
            variants.append(b["data"]["data"])
        best = None
        for data in variants:
            paths = [p for p in flatten(data) if p and not p.split(".")[0] in envelope and not p.endswith(".href")]
            if len(paths) < 4:
                continue
            und = [p for p in paths if not covered(p)]
            ratio = 1 - len(und) / len(paths)
            if best is None or ratio > best[0]:
                best = (ratio, und)
        if best is None or best[0] < 0.4:
            continue  # this JSON is not an example of a documented structure (error body, etc.)
        und = best[1]
        checked += 1
        top = sorted(p for p in und if not any(q != p and p.startswith(q + ".") for q in und))
        for p in top:
            agg.setdefault(p, []).append(short(b["ctx"], 30))
    if agg:
        items = sorted(agg.items(), key=lambda kv: -len(kv[1]))
        desc = "; ".join(f"{p} (ב־{len(v)} דוגמאות, למשל אחרי \"{v[0]}\")" if len(v) > 1 else f"{p} (אחרי \"{v[0]}\")" for p, v in items[:8])
        rep.warn("JSON↔טבלה", f"{len(agg)} שדות בדוגמאות JSON שלא מופיעים באף טבלת שדות — בדרך כלל שם שדה ששונה רק באחד המקומות: {desc}")
    elif checked:
        rep.good("JSON↔טבלה", f"כל השדות ב־{checked} דוגמאות JSON מתועדים בטבלאות השדות")


def check_tables(doc, rep):
    long_no_hdr = 0
    for tbl in tables(doc):
        trs = tbl.findall(W + "tr")
        if len(trs) > 12 and len(trs[0].findall(W + "tc")) >= 3:
            trpr = trs[0].find(W + "trPr")
            if trpr is None or trpr.find(W + "tblHeader") is None:
                long_no_hdr += 1
    if long_no_hdr:
        rep.warn("טבלאות", f"{long_no_hdr} טבלאות ארוכות שבהן שורת הכותרת לא חוזרת בכל עמוד")


def check_revisions(doc, rep):
    """Tracked changes and comments left in a document that is about to go to a client."""
    body = doc.body
    ins = sum(1 for _ in body.iter(W + "ins"))
    dels = sum(1 for _ in body.iter(W + "del"))
    moves = sum(1 for _ in body.iter(W + "moveFrom")) + sum(1 for _ in body.iter(W + "moveTo"))
    comments = len({c.get(W + "id") for c in body.iter(W + "commentReference")})
    if ins or dels or moves:
        rep.err("מעקב שינויים", f"במסמך {ins + dels + moves} שינויים במעקב שלא אושרו ({ins} הוספות, {dels} מחיקות)"
                " — הטקסט שנמחק עדיין גלוי למי שפותח את הקובץ. יש לקבל או לדחות את כל השינויים לפני שליחה")
    if comments:
        rep.err("מעקב שינויים", f"במסמך {comments} הערות פתוחות — יש לטפל בהן ולמחוק אותן לפני שליחה ללקוח")


def check_branding(doc, rep):
    hdr_img = 0
    page_field = False
    for s in doc.d.sections:
        for part in (s.header, s.first_page_header):
            try:
                hdr_img += sum(1 for _ in part._element.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip"))
            except Exception:
                pass
        for part in (s.footer, s.first_page_footer):
            try:
                x = part._element
                instr = "".join(i.text or "" for i in x.iter(W + "instrText"))
                if "PAGE" in instr or x.find(".//" + W + "fldSimple") is not None:
                    page_field = True
            except Exception:
                pass
    if not hdr_img:
        rep.warn("מיתוג", "אין לוגו בכותרת העליונה")
    if not page_field:
        rep.warn("מיתוג", "אין מספרי עמודים בכותרת התחתונה")
    with zipfile.ZipFile(doc.path) as z:
        foreign = set()
        for name in z.namelist():
            if re.match(r"word/(header|footer)\d*\.xml$", name):
                t = re.sub(r"<[^>]+>", " ", z.read(name).decode("utf8", "ignore"))
                for m in re.findall(r"[\w.\-]+@[\w.\-]+\.\w+|https?://\S+|www\.\S+", t):
                    if "aman" not in m.lower():
                        foreign.add(m)
    for f in sorted(foreign):
        rep.err("מיתוג", f"בכותרת/פוטר מופיעים פרטי קשר שאינם של אמן: {f}")


def check_language(doc, rep, lang, spec=None):
    """spelling, confusable words, gender agreement, AI-style and translated terms (he_lint)"""
    items = []
    for i, p in enumerate(doc.paras):
        if p["sname"].startswith("toc") or looks_code(p):
            continue
        text = "".join(("CODE" if r["t"].strip() else r["t"]) if any(m in r["font"] for m in MONO) else r["t"] for r in p["runs"])
        if text.strip():
            items.append((f"\"{short(text, 40)}\"", text))
    ignore = set()
    if spec:
        ignore |= set(spec.get("spell_ignore") or []) | set((spec.get("meta") or {}).get("spell_ignore") or [])
        m = spec.get("meta") or {}
        names = [m.get("client"), m.get("project")] + (m.get("authors") if isinstance(m.get("authors"), list) else [m.get("authors")])
        names += [r.get("author") for r in spec.get("changelog") or [] if isinstance(r, dict)]
        for n in names:
            if isinstance(n, str):
                ignore |= set(he_lint.WORD_RE.findall(n))
    found = he_lint.lint_texts(items, lang=lang, spell=True, ignore=ignore, spell_level="warning" if not spec else "error")
    by = {}
    for lvl, cat, loc, msg in found:
        by.setdefault((lvl, cat), []).append(f"{msg}")
    names = {"confusable": "מילה שגויה בהקשר", "spelling": "איות", "agreement": "התאמת מין", "ai-style": "סגנון AI",
             "register": "משלב לשון", "terms": "מונח מתורגם", "hygiene": "ניקיון טקסט"}
    for (lvl, cat), msgs in sorted(by.items()):
        f = rep.err if lvl == "error" else rep.warn
        uniq = list(dict.fromkeys(msgs))
        f("לשון", f"{names.get(cat, cat)} ({len(uniq)}): " + " | ".join(uniq[:6]) + (" …" if len(uniq) > 6 else ""))
    if not found:
        rep.good("לשון", "איות, התאמת מין, מילים מתחלפות וסגנון – תקין" + ("" if he_lint.ensure_hspell(install=False) else " (ללא hspell)"))


def detect_lang(doc):
    he = sum(len(HEB.findall(p["text"])) for p in doc.paras if not looks_code(p))
    la = sum(len(LAT.findall(p["text"])) for p in doc.paras if not looks_code(p))
    return "he" if he >= 0.2 * (he + la) else "en"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--spec")
    ap.add_argument("--lang", choices=["he", "en"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    spec = None
    if a.spec:
        with open(a.spec, encoding="utf8") as f:
            spec = json.load(f)
    doc = Doc(a.docx)
    lang = a.lang or (spec or {}).get("meta", {}).get("lang") or detect_lang(doc)
    rep = Report()
    hs = headings(doc)
    check_direction(doc, rep, lang)
    nums = check_structure(doc, hs, rep)
    check_toc(doc, hs, rep)
    check_revisions(doc, rep)
    check_changelog(doc, rep, spec)
    check_refs(doc, nums, rep, lang)
    check_placeholders(doc, hs, rep)
    lenient = 0
    if spec:
        def walk(secs):
            n = 0
            for s in secs or []:
                n += sum(1 for b in s.get("blocks") or [] if isinstance(b, dict) and b.get("type") == "code" and b.get("lenient"))
                n += walk(s.get("sections"))
            return n
        lenient = walk(spec.get("sections"))
    check_json(doc, rep, strict=bool(spec), lenient_allowed=lenient)
    check_tables(doc, rep)
    check_branding(doc, rep)
    check_language(doc, rep, lang, spec)

    if a.json:
        print(json.dumps([{"level": l, "category": c, "message": m} for l, c, m in rep.items], ensure_ascii=False, indent=2))
    else:
        icon = {"error": "❌", "warning": "⚠️ ", "note": "ℹ️ ", "ok": "✓ "}
        title = {"error": "שגיאות", "warning": "אזהרות", "note": "הערות", "ok": "נבדק ותקין"}
        print(f"QA — {a.docx}  (שפה: {'עברית' if lang == 'he' else 'אנגלית'}, {len(hs)} כותרות)")
        for level in ("error", "warning", "note", "ok"):
            items = [x for x in rep.items if x[0] == level]
            if not items:
                continue
            print(f"\n{title[level]} ({len(items)}):")
            for _, c, m in items:
                print(f"  {icon[level]} [{c}] {m}")
        print(f"\nסיכום: {rep.count('error')} שגיאות, {rep.count('warning')} אזהרות")
    sys.exit(1 if rep.count("error") else 0)


if __name__ == "__main__":
    main()
