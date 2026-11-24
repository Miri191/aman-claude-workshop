#!/usr/bin/env python3
"""
he_lint.py — language checks for spec texts (Hebrew first, English too)

    python3 he_lint.py <spec.json>            lint every text field of a spec (exit 1 on errors)
    python3 he_lint.py --text "..." [--lang en]

Layers (each finding has a level: error / warning):
  confusable   correctly-spelled words that are wrong in context — תחולה↔תכולה (error)
  spelling     known misspellings (עידכון, טבלא, פונקציונאלי…) (error) and, when hspell is available,
               a full Hebrew spell check with a whitelist of technical transliterations (error in a spec,
               warning in QA of an existing document)
  agreement    subject–verb gender agreement for common spec nouns: "המערכת מחזיר", "הממשק מחזירה" (error)
  ai-style     phrases that make a text read as machine-written ("חשוב לציין", "seamless", "leverage") (warning)
  register     bureaucratic / discouraged forms: הינו, במידה ו, על מנת, דוגמא… (warning)
  terms        technical terms translated into Hebrew that developers keep in English: נקודת קצה, אסימון,
               עימוד… (warning)
  hygiene      repeated words, space before punctuation, dash overuse (warning)

Ignore list: "spell_ignore": ["ולידציה", ...] at the top level of a spec (or meta.spell_ignore) — words
that are correct for this document; also silences confusable / terms rules for those exact words.
"""
import json
import os
import re
import shutil
import subprocess
import sys

HEB = "\u05D0-\u05EA"
WORD_RE = re.compile(rf"[{HEB}][{HEB}\"'״׳]*[{HEB}]['׳]?|[{HEB}]['׳]?")
PREFIXES = ("ו", "ה", "ב", "ל", "מ", "ש", "כ")

# ───────────────────────────── rule tables ─────────────────────────────
# technical words in Hebrew letters that are correct even though hspell doesn't know them
TECH_WHITELIST = set("""
ולידציה ולידציות אותנטיקציה אוטוריזציה קונפיגורציה קונפיגורציות אינטגרציה אינטגרציות סנכרון סינכרוני אסינכרוני
פופ אפ פופאפ פופ־אפ פופים מגירה מגירות טוגל טוגלים קומפוננטה קומפוננטות פיצר פיצ׳ר פיצ׳רים פיצרים
דשבורד דשבורדים לוגין לוגאוט אונבורדינג באנר באנרים סליידר טאב טאבים קרוסלה צ׳קבוקס דרופדאון
סקרול סקרולינג גלילה ספינר לואדר אייקון אייקונים טולטיפ סנקבר נוטיפיקציה נוטיפיקציות פוש
פרונט פרונטאנד בקאנד בקנד פולסטאק דיפלוי פרודקשן סטייג׳ינג סטייג׳ינג ריליס ריליסים באג באגים
סקריפט סקריפטים פריימוורק ספריות קוד מודול מודולים אובייקט אובייקטים מתודה מתודות אינסטנס
פרמטר פרמטרים מפתח מפתחות טוקן טוקנים קוקי קוקיז סשן סשנים הדר הדרים לוג לוגים לוגינג
קאש קאשינג פולינג פולינג שרת שרתים קליינט קליינטים דאטה דאטאבייס סכמה סכמות אינדקס אינדקסים
טריגר טריגרים פרוצדורה פרוצדורות ג׳וב ג׳ובים קרון סקדולר וובהוק וובהוקים ממשקים אנדפוינט
מיפוי מיפויים פארסינג פרסור סריאליזציה דסריאליזציה אנקודינג הצפנה קידוד ריטריי טיימאאוט
אנליטיקס אנליטיקה טרקינג פיקסל קמפיין קמפיינים לנדינג אפסייל קרוס פרסונליזציה סגמנט סגמנטים
פוליסה פוליסות מבוטח מבוטחת מבוטחים ביטוח רשומה רשומות שליפה שליפות שיוך שיוכים מנורמלות מנורמל נרמול
השטחה השטחת הקסדצימלי הקסדצימלית צ׳ק אאוט אין צ׳ק־אין צ׳ק־אאוט אמן דיגיטל ממשקי פוסט גט פאץ׳ דליט
ריפקטור רפקטורינג מיגרציה מיגרציות סקייל סקיילינג לואד באלאנסר קונטיינר קונטיינרים קוברנטיס דוקר
אינטראקציה אינטראקטיבי מוקאפ פיגמה ויירפריים פרוטוטייפ
תכן תכנים תכני
אמיתי אמיתית אמיתיים אמיתיות בוליאני בוליאנית
אנדרואיד אייפון אייפד וואטסאפ אנדרואידי ווב וובי אתרים מובייל אפליקציה אפליקציות
אפליקטיבי אפליקטיבית אפליקטיביים אפליקטיביות תשתיתי תשתיתית תשתיתיים תשתיתיות ספרינט ספרינטים דיסקברי
התממשקות להתממשק תתממשק יתממשק מתממשק מתממשקת מתממשקים ממשוק פיילוט הייפרקר בנצ׳מרק ספאם סייבר
סיסמה סיסמות סיסמאות אדמין אדמינים קאשבק מיגרציית סייט סייטים ליד לידים קופון קופונים מיקרו קופי אומניצ׳אנל ארכיטקט ארכיטקטים ארכיטקטוני ארכיטקטונית מאפיין מאפיינת
""".split())

FIXED_SPELLING = [  # (regex on the word without prefixes, correct form)
    (r"עידכו(ן|נים|ני|נית|ני)?", "עדכון"), (r"אירגו(ן|נים|ני|נית)", "ארגון"), (r"שירשור", "שרשור"),
    (r"פונקציונאלי(ת|ים|ות)?", "פונקציונלי"), (r"טבלא", "טבלה"), (r"אינטרגציה|אינטרגציות", "אינטגרציה"),
    (r"קונפיגרציה|קונפיגרציות", "קונפיגורציה"), (r"פונקצייה|פונקציות?יה", "פונקציה"),
    (r"אוטנטיקציה", "אותנטיקציה (או: אימות)"), (r"אפליקצייה|אפליקצייות", "אפליקציה"),
    (r"סטאטוס|סטאטוסים", "סטטוס"), (r"פורמאט|פורמאטים", "פורמט"), (r"סטנדארט|סטנדארטי", "סטנדרט"),
    (r"פרמטירים", "פרמטרים"), (r"אינפורמאציה", "אינפורמציה (עדיף: מידע)"), (r"לוגיקא", "לוגיקה"),
]

REGISTER = [  # (regex, message) — warnings
    (r"(?<![א-ת])[וש]?הינ(ו|ה|ם|ן)(?![א-ת])", "\"הינו/הינה\" – כתוב \"הוא/היא\" (או השמט)"),
    (r"(?<![א-ת])[וכש]?במידה ו", "\"במידה ו…\" – כתוב \"אם\""),
    (r"(?<![א-ת])[וש]?במידה ש(?=[א-ת])", "\"במידה ש…\" במשמעות תנאי – כתוב \"אם\""),
    (r"(?<![א-ת])[ו]?על מנת(?![א-ת])", "\"על מנת\" – כתוב \"כדי\""),
    (r"(?<![א-ת])[ו]?בכדי(?![א-ת])", "\"בכדי\" – כתוב \"כדי\""),
    (r"(?<![א-ת])[ובלמה]{0,2}דוגמא(?![א-ת])", "\"דוגמא\" – בתבנית הבית \"דוגמה\""),
    (r"(?<![א-ת])לאור העובדה ש", "\"לאור העובדה ש…\" – כתוב \"מכיוון ש…\""),
    (r"(?<![א-ת])[וש]?(אנו|אנחנו)(?![א-ת])", "גוף ראשון באפיון – כתוב בלשון סתמית (\"המערכת…\", \"יש ל…\")"),
    (r"(?<![א-ת])לעשות שימוש ב", "\"לעשות שימוש ב…\" – כתוב \"להשתמש ב…\""),
    (r"(?<![א-ת])[ו]?מהווה(?![א-ת])|(?<![א-ת])[ו]?מהווים(?![א-ת])", "\"מהווה\" – בדרך כלל עדיף \"הוא/היא\" או ניסוח ישיר"),
]

AI_HE = [
    "חשוב לציין", "יש לציין כי", "ראוי לציין", "חשוב להדגיש", "באופן כללי", "בסופו של דבר", "בצורה חלקה",
    "באופן חלק", "חוויה חלקה", "חוויית משתמש חלקה", "פתרון מקיף", "מקיף ומלא", "מגוון רחב של", "בעידן ה",
    "כפי שניתן לראות", "ללא ספק", "נועד להבטיח", "תוך הקפדה על", "בקלות ובמהירות", "בלחיצת כפתור",
    "לסיכום,", "בנוסף לכך,", "יתרה מכך", "חוויה משופרת", "באופן אופטימלי", "בצורה מיטבית", "ערך מוסף",
]
AI_HE_RE = [(re.compile(r"(?<![א-ת])לא רק\b.{1,60}?אלא גם"), "\"לא רק… אלא גם\"")]
AI_EN = [
    "seamless", "seamlessly", "robust", "leverage", "leverages", "leveraging", "comprehensive", "cutting-edge",
    "state-of-the-art", "delve", "it is important to note", "it's worth noting", "it is worth noting",
    "in today's", "plays a crucial role", "plays a key role", "streamline", "empower", "utilize", "utilizes",
    "in order to", "facilitate", "a wide range of", "overall,", "in conclusion", "furthermore,", "moreover,",
    "best-in-class", "world-class", "game-changer", "holistic", "synergy", "unlock the",
]
AI_EN_RE = [(re.compile(r"\bnot only\b.{1,60}?\bbut also\b", re.I), "\"not only … but also\"")]

TERMS = [  # translated technical terms → keep in English
    (r"נקוד(ת|ות) קצה", "Endpoint"), (r"(?<![א-ת])[וה]?אסימו(ן|נים)(?![א-ת])", "Token"), (r"(?<![א-ת])[וה]?עימוד", "Pagination"),
    (r"מטען (ה)?(נתונים|בקשה|תשובה|הודעה)", "Payload"), (r"(?<![א-ת])[וה]?קרס(ים)?(?![א-ת])", "Hook"),
    (r"פסק(י)? זמן", "Timeout"), (r"סביבת (ה)?ייצור", "Production"), (r"(?<![א-ת])[וה]?מטמון", "Cache"),
    (r"ממשק תכנות יישומים", "API"), (r"מזהה ייחודי אוניברסלי", "UUID"), (r"תוכנת ביניים", "Middleware"),
    (r"בקשת משיכה", "Pull Request"),
    (r"(?<![א-ת])[ובלמה]{0,2}דאט(ה ?)?בייס(ים)?(?![א-ת])", "DB / Database"), (r"(?<![א-ת])[ה]?אידמפוטנט\S*", "Idempotency / idempotent"),
    (r"שפת סימון", "Markup"),
]

# gender agreement: common spec nouns (definite) + present-tense verbs / participles
NOUNS_M = """ממשק שירות שרת קליינט לקוח משתמש מסך כפתור שדה ערך קובץ תהליך רכיב טופס קישור מבוטח נוסע צרכן ספק
מנגנון דוח מסמך פקד אייקון באנר תפריט רכב התקן חיבור סשן טוקן ג׳וב""".split()
NOUNS_F = """מערכת אפליקציה טבלה בקשה תשובה רשומה הודעה קריאה פונקציה ספרייה מגירה רשימה שגיאה הזמנה פוליסה טיסה
סוגיה תזכורת התראה עמודה שורה פעולה גרסה סביבה פלטפורמה""".split()
VERBS = [  # (masculine, feminine)
    ("מחזיר", "מחזירה"), ("שולח", "שולחת"), ("מקבל", "מקבלת"), ("מציג", "מציגה"), ("מבצע", "מבצעת"),
    ("בודק", "בודקת"), ("שומר", "שומרת"), ("יוצר", "יוצרת"), ("מעדכן", "מעדכנת"), ("מאפשר", "מאפשרת"),
    ("תומך", "תומכת"), ("מופיע", "מופיעה"), ("מוצג", "מוצגת"), ("נשמר", "נשמרת"), ("נוצר", "נוצרת"),
    ("נשלח", "נשלחת"), ("מתעדכן", "מתעדכנת"), ("כולל", "כוללת"), ("מכיל", "מכילה"), ("נדרש", "נדרשת"),
    ("קורא", "קוראת"), ("מסנן", "מסננת"), ("שולף", "שולפת"), ("מפעיל", "מפעילה"), ("מחשב", "מחשבת"),
    ("ממיר", "ממירה"), ("נטען", "נטענת"), ("נסגר", "נסגרת"), ("נפתח", "נפתחת"), ("מוחזר", "מוחזרת"),
    ("מוגדר", "מוגדרת"), ("נשלף", "נשלפת"), ("קיים", "קיימת"), ("זמין", "זמינה"), ("תקין", "תקינה"),
    ("פעיל", "פעילה"), ("מחובר", "מחוברת"), ("משויך", "משויכת"), ("מנוהל", "מנוהלת"), ("מחייב", "מחייבת"),
]
CLAUSE_OPENERS = set("""אם כאשר כש ש אז גם רק כי אך אבל לכן ואז בנוסף אחרי לאחר לפני ברגע כל עוד כיוון מכיוון
וכאשר ואם כשה שה אזי בעת בזמן""".split())


def _verb_maps():
    m2f, f2m = {}, {}
    for m, f in VERBS:
        m2f[m] = f
        f2m[f] = m
    return m2f, f2m


M2F, F2M = _verb_maps()
_NOUN_ALT = "|".join(sorted(NOUNS_M + NOUNS_F, key=len, reverse=True))
_VERB_ALT = "|".join(sorted(list(M2F) + list(F2M), key=len, reverse=True))
AGREE_RE = re.compile(rf"(^|[\s(:;,–\-.\"״])([ו]?(?:ש|כש)?)ה({_NOUN_ALT})\s+(?:לא\s+)?({_VERB_ALT})(?![{HEB}])")


# ───────────────────────────── helpers ─────────────────────────────
def strip_code(text):
    """remove `inline code`, {{refs}}, URLs, emails and paths — they are not prose"""
    t = re.sub(r"`[^`]*`", "CODE", text)          # placeholders, not spaces: keeps punctuation checks honest
    t = re.sub(r"\{\{[^}]*\}\}", "7", t)
    t = re.sub(r"https?://\S+|[\w.\-]+@[\w.\-]+|/[\w/{}\-.?=&]+", "URL", t)
    t = t.replace("**", "")
    return t


def mermaid_labels(line):
    """only the human-readable label text of a Mermaid line"""
    out = []
    m = re.match(r"\s*participant\s+\S+\s+as\s+(.+)$", line)
    if m:
        return [m.group(1)]
    m = re.match(r"\s*state\s+\"([^\"]+)\"", line)
    if m:
        return [m.group(1)]
    if re.search(r"-[-.]?>>?|--[x)]|Note\s|-->\s*\S+\s*:|\s:\s", line) and ":" in line:
        out.append(line.split(":", 1)[1])
    for rx in (r"\[\(?\"?([^\]\"]+)\"?\)?\]", r"\{\{?([^}]+)\}?\}", r"\(\[?\(?\"?([^)\]\"]+)\"?\)?\]?\)", r"\|([^|]+)\|", r"--\s+([^>-][^>]*?)\s+-->"):
        out += re.findall(rx, line)
    return [re.sub(r"<br\s*/?>", " ", x) for x in out]


def strip_prefix(w, known):
    if w in known:
        return w
    for i in range(1, 4):
        if len(w) - i >= 2 and all(c in PREFIXES for c in w[:i]) and w[i:] in known:
            return w[i:]
    return None


def _ctx(text, s, e, n=28):
    a, b = max(0, s - n), min(len(text), e + n)
    return ("…" if a else "") + text[a:b].replace("\n", " ") + ("…" if b < len(text) else "")


# ───────────────────────────── hspell ─────────────────────────────
_HSPELL = None


def ensure_hspell(install=True, quiet=True):
    """hspell (Hebrew spell checker). Installed on demand with apt-get when we are root."""
    global _HSPELL
    if _HSPELL is not None:
        return _HSPELL
    if not shutil.which("hspell") and install and shutil.which("apt-get") and hasattr(os, "geteuid") and os.geteuid() == 0:
        if not quiet:
            print("… מתקין בודק איות עברי (hspell)")
        for cmd in (["apt-get", "install", "-y", "-q", "hspell"], ["apt-get", "update", "-q"],
                    ["apt-get", "install", "-y", "-q", "hspell"]):
            try:
                subprocess.run(cmd, capture_output=True, timeout=180)
            except Exception:
                break
            if shutil.which("hspell"):
                break
    _HSPELL = bool(shutil.which("hspell"))
    return _HSPELL


def hspell_unknown(words):
    """return the subset of words hspell does not accept"""
    if not words or not ensure_hspell():
        return set()
    norm = {}
    for w in words:
        n = w.replace("״", '"').replace("׳", "'")
        norm.setdefault(n, set()).add(w)
    data = "\n".join(norm).encode("iso-8859-8", errors="replace")
    try:
        r = subprocess.run(["hspell"], input=data, capture_output=True, timeout=60)
    except Exception:
        return set()
    out = set()
    for line in r.stdout.decode("iso-8859-8", errors="replace").splitlines():
        line = line.strip()
        if not line or "שנמצאו" in line:  # hspell prints a heading line before the list
            continue
        for orig in norm.get(line, ()):
            out.add(orig)
    return out


# ───────────────────────────── linting ─────────────────────────────
def lint_texts(items, lang="he", spell=True, ignore=(), spell_level="error"):
    """items: [(location, text)] → [(level, category, location, message)]"""
    ignore = set(ignore)
    find = []
    words_at = {}
    flagged = set()  # words already reported by a specific rule – not reported again by hspell
    for loc, raw in items:
        if not raw or not isinstance(raw, str):
            continue
        text = strip_code(raw)
        if lang == "he" or re.search(rf"[{HEB}]", text):
            # confusable: תחולה (applicability) vs תכולה (scope)
            for m in re.finditer(rf"(?<![{HEB}])([ובלמהש]{{0,3}})תחול(ה|ת)(?![{HEB}])", text):
                if "תחולה" in ignore or "תחולת" in ignore:
                    continue
                before = text[max(0, m.start() - 14):m.start()]
                after = text[m.end():m.end() + 16]
                if re.search(r"(תאריך|מועד|יום|תקופת|תנאי|הוראות|דיני|כללי)\s*$", before) or \
                   re.search(r"^\s*(ה)?(חוק|תקנות|תקנה|הוראה|הוראות|הסכם|פוליסה|ביטוח|כיסוי|הנחה|תעריף|שינוי|רטרואקטיבית|מיום)", after):
                    continue
                find.append(("error", "confusable", loc, f"\"{m.group(0)}\" – תחולה = כניסה לתוקף / היקף החלה. "
                             f"לתחום העבודה (scope) כותבים \"{m.group(1)}תכול{m.group(2)}\": {_ctx(text, m.start(), m.end())}"))
            # fixed misspellings
            for w in WORD_RE.findall(text):
                base = w
                n_before = len(find)
                for i in range(0, 4):
                    cand = w[i:]
                    if i and not all(c in PREFIXES for c in w[:i]):
                        break
                    for rx, good in FIXED_SPELLING:
                        if re.fullmatch(rx, cand) and cand not in ignore and w not in ignore:
                            find.append(("error", "spelling", loc, f"\"{w}\" – כתיב נכון: {good}"))
                            break
                    else:
                        continue
                    break
                if len(find) > n_before:
                    flagged.add(base)
                words_at.setdefault(base, set()).add(loc)
            # agreement
            for m in AGREE_RE.finditer(text):
                noun, verb = m.group(3), m.group(4)
                pre = text[:m.start(2)].rstrip()
                prev = re.findall(rf"[{HEB}]+$", pre)
                if m.group(1).strip() == "" and prev and prev[0] not in CLAUSE_OPENERS and not re.search(r"[:;,.–\-(\"]\s*$", text[:m.start(2)]):
                    continue  # probably construct state ("כפתור המערכת מוצג") – not the subject
                fem = noun in NOUNS_F
                if fem and verb in M2F:
                    find.append(("error", "agreement", loc, f"התאמת מין: \"ה{noun} {verb}\" – {noun} נקבה, צריך \"{M2F[verb]}\": {_ctx(text, m.start(3), m.end())}"))
                elif not fem and verb in F2M:
                    find.append(("error", "agreement", loc, f"התאמת מין: \"ה{noun} {verb}\" – {noun} זכר, צריך \"{F2M[verb]}\": {_ctx(text, m.start(3), m.end())}"))
            for rx, msg in REGISTER:
                for m in re.finditer(rx, text):
                    flagged.update(WORD_RE.findall(m.group(0)))
                    find.append(("warning", "register", loc, f"{msg}: {_ctx(text, m.start(), m.end())}"))
            for ph in AI_HE:
                i = text.find(ph)
                if i >= 0:
                    find.append(("warning", "ai-style", loc, f"\"{ph}\" נשמע כמו טקסט שנכתב ע״י AI – נסח ישיר וענייני: {_ctx(text, i, i + len(ph))}"))
            for rx, name in AI_HE_RE:
                m = rx.search(text)
                if m:
                    find.append(("warning", "ai-style", loc, f"{name} – מבנה אופייני לטקסט AI: {_ctx(text, m.start(), m.end())}"))
            if lang == "he":
                for rx, en in TERMS:
                    for m in re.finditer(rx, text):
                        if m.group(0).strip() in ignore:
                            continue
                        flagged.update(WORD_RE.findall(m.group(0)))
                        find.append(("warning", "terms", loc, f"\"{m.group(0)}\" – מונח טכני מתורגם; בצוות כותבים {en}: {_ctx(text, m.start(), m.end())}"))
        if lang == "en":
            low = text.lower()
            for ph in AI_EN:
                for m in re.finditer(rf"(?<![a-z]){re.escape(ph)}(?![a-z])", low):
                    find.append(("warning", "ai-style", loc, f"\"{ph}\" reads as AI / marketing language – be specific: {_ctx(text, m.start(), m.end())}"))
            for rx, name in AI_EN_RE:
                m = rx.search(text)
                if m:
                    find.append(("warning", "ai-style", loc, f"{name} – typical AI construction: {_ctx(text, m.start(), m.end())}"))
        # hygiene
        for m in re.finditer(rf"(?<![{HEB}\w])([{HEB}]{{2,}}|[A-Za-z]{{3,}})\s+\1(?![{HEB}\w])", text):
            find.append(("warning", "hygiene", loc, f"מילה כפולה \"{m.group(1)} {m.group(1)}\": {_ctx(text, m.start(), m.end())}"))
        for m in re.finditer(rf"[{HEB}A-Za-z]\s+[,.;:](?=\s|$)", text):
            find.append(("warning", "hygiene", loc, f"רווח לפני סימן פיסוק: {_ctx(text, m.start(), m.end())}"))
        if len(re.findall(r"\s[–—]\s", text)) >= 3:
            find.append(("warning", "ai-style", loc, f"{len(re.findall(r'[–—]', text))} מקפים בפסקה אחת – פרק למשפטים קצרים (ריבוי מקפים מסגיר כתיבת AI): {_ctx(text, 0, 60)}"))
    # spell check (one hspell call for the whole document)
    if spell and words_at:
        candidates = set()
        for w in words_at:
            if w in flagged or w in ignore or w in TECH_WHITELIST or strip_prefix(w, TECH_WHITELIST | ignore):
                continue
            if len(w) < 2 or re.search(r"[\"'״׳]", w):  # acronyms (ע״י, סה״כ) – hspell knows most, skip the rest
                continue
            candidates.add(w)
        for w in sorted(hspell_unknown(candidates)):
            locs = sorted(words_at[w])
            find.append((spell_level, "spelling", locs[0], f"\"{w}\" – לא נמצא במילון העברי (hspell). תקן, או אם זה מונח נכון הוסף ל־spell_ignore"
                         + (f" (מופיע ב־{len(locs)} מקומות)" if len(locs) > 1 else "")))
    # de-duplicate
    seen, out = set(), []
    for f in find:
        k = (f[0], f[1], f[2], f[3])
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


# ───────────────────────────── spec walking ─────────────────────────────
PRESET_CODE_KEYS = {  # columns that hold code / identifiers, not prose
    "api_request": {"name", "example"}, "api_response": {"name", "example"}, "db_table": {"name", "type"},
    "errors": {"code"}, "mapping": {"source", "target"}, "params": {"name"}, "environments": {"url"},
    "config": {"key", "default"}, "events": {"event"},
}
def spec_texts(spec):
    """(location, text) for every prose string in a spec; code, field names and examples are skipped"""
    items = []
    meta = spec.get("meta") or {}
    for k in ("title", "subtitle", "doc_type", "status", "client", "project", "header_note", "footer_note"):
        if isinstance(meta.get(k), str):
            items.append((f"meta.{k}", meta[k]))
    for d in meta.get("details") or []:
        if isinstance(d, list) and len(d) > 1:
            items.append(("meta.details", f"{d[0]} {d[1]}"))
    for i, r in enumerate(spec.get("changelog") or []):
        items.append((f"מעקב שינויים שורה {i + 1}", r.get("changes", "")))

    def cell_texts(v):
        if isinstance(v, list):
            return [str(x) for x in v if isinstance(x, (str, int, float))]
        return [v] if isinstance(v, str) else []

    def walk(secs, prefix):
        for i, s in enumerate(secs or []):
            if not isinstance(s, dict):
                continue
            num = f"{prefix}.{i + 1}" if prefix else f"{i + 1}"
            where = f"סעיף {num} (\"{s.get('title', '')}\")"
            items.append((where + " כותרת", s.get("title", "")))
            if s.get("part"):
                items.append((where + " part", s["part"]))
            for bi, b in enumerate(s.get("blocks") or []):
                if not isinstance(b, dict):
                    continue
                loc = f"{where} בלוק {bi + 1} ({b.get('type')})"
                t = b.get("type")
                for k in ("text", "caption", "note", "title", "alt"):
                    if isinstance(b.get(k), str) and not (t == "code" and k == "text"):
                        items.append((loc, b[k]))
                if t == "callout" and isinstance(b.get("label"), str):
                    items.append((loc, b["label"]))
                if t in ("bullets", "numbered"):
                    for it in b.get("items") or []:
                        if isinstance(it, str):
                            items.append((loc, it))
                        elif isinstance(it, dict):
                            items.append((loc, it.get("text", "")))
                            for sub in it.get("sub") or []:
                                items.append((loc, sub if isinstance(sub, str) else (sub or {}).get("text", "")))
                if t == "table":
                    cols = b.get("columns")
                    code_keys = set()
                    if isinstance(cols, list):
                        code_keys = {c.get("key") for c in cols if isinstance(c, dict) and c.get("code")}
                        for c in cols:
                            items.append((loc + " כותרת עמודה", c.get("label", "") if isinstance(c, dict) else str(c)))
                    elif isinstance(cols, str):
                        code_keys = PRESET_CODE_KEYS.get(cols, set())
                    for ri, r in enumerate(b.get("rows") or []):
                        rl = f"{loc} שורה {ri + 1}"
                        if isinstance(r, dict) and "group" in r:
                            items.append((rl, str(r["group"])))
                        elif isinstance(r, dict):
                            for k, v in r.items():
                                if k not in code_keys:
                                    for x in cell_texts(v):
                                        items.append((rl, x))
                        elif isinstance(r, list):
                            for x in r:
                                for y in cell_texts(x):
                                    if not re.fullmatch(r"[\w.\[\]$@:/\-]+", y or ""):
                                        items.append((rl, y))
                if t == "kv":
                    for r in b.get("rows") or []:
                        if isinstance(r, list):
                            for x in r[:2]:
                                for y in cell_texts(x):
                                    items.append((loc, y))
                    for k, v in (b.get("data") or {}).items():
                        if k not in ("service", "operation_id", "endpoint", "method"):
                            for y in cell_texts(v):
                                items.append((loc, y))
                if t == "diagram":
                    src = b.get("mermaid")
                    lines = src if isinstance(src, list) else str(src or "").split("\n")
                    for ln in lines:
                        if re.search(rf"[{HEB}]", ln):
                            for lab in mermaid_labels(ln):
                                items.append((loc + " (תרשים)", lab))
            walk(s.get("sections"), num)
    walk(spec.get("sections"), "")
    return items


def lint_spec(spec, spell=True):
    meta = spec.get("meta") or {}
    lang = meta.get("lang", "he")
    ignore = set(spec.get("spell_ignore") or []) | set(meta.get("spell_ignore") or [])
    # names are not dictionary words: client, project, authors and change-log authors
    names = [meta.get("client"), meta.get("project")]
    names += meta.get("authors") if isinstance(meta.get("authors"), list) else [meta.get("authors")]
    names += [r.get("author") for r in spec.get("changelog") or [] if isinstance(r, dict)]
    for n in names:
        if isinstance(n, str):
            for w in WORD_RE.findall(n):
                ignore.add(w)
                for i in range(1, 3):
                    if w[:i] and all(c in PREFIXES for c in w[:i]):
                        ignore.add(w[i:])
    return lint_texts(spec_texts(spec), lang=lang, spell=spell, ignore=ignore, spell_level="error")


def report(findings, title="בדיקת לשון"):
    errs = [f for f in findings if f[0] == "error"]
    warns = [f for f in findings if f[0] == "warning"]
    if not findings:
        print(f"✓ {title}: תקין")
        return
    if errs:
        print(f"❌ {title} – {len(errs)} שגיאות:")
        for _, c, loc, m in errs:
            print(f"  - [{c}] {loc}: {m}")
    if warns:
        print(f"⚠️  {title} – {len(warns)} אזהרות:")
        for _, c, loc, m in warns:
            print(f"  - [{c}] {loc}: {m}")


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if a else 2)
    if a[0] == "--text":
        lang = a[a.index("--lang") + 1] if "--lang" in a else "he"
        f = lint_texts([("טקסט", a[1])], lang=lang)
    else:
        spec = json.load(open(a[0], encoding="utf8"))
        f = lint_spec(spec)
    report(f)
    sys.exit(1 if any(x[0] == "error" for x in f) else 0)


if __name__ == "__main__":
    main()
