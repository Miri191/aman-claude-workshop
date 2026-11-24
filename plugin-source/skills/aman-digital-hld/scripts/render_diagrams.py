#!/usr/bin/env python3
"""
render_diagrams.py — render the Mermaid diagrams of a spec to PNG (Aman Digital tech-spec skill)

    python3 render_diagrams.py <spec.json> <out_dir>      → writes <out_dir>/<id>.png + manifest.json
    python3 render_diagrams.py --mmd file.mmd out.png      → render one file (for trying a diagram out)

- Hebrew labels are laid out right-to-left (assets/mermaid/rtl.css), English labels left-to-right.
- Brand colours / fonts come from assets/mermaid/config.json.
- Results are cached by content hash, so re-building a spec only re-renders changed diagrams.
- On a syntax error the diagram id, the Mermaid error and the offending line are printed; exit code 1.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MERMAID_DIR = os.path.join(SKILL_DIR, "assets", "mermaid")
CONFIG = os.path.join(MERMAID_DIR, "config.json")
CSS = os.path.join(MERMAID_DIR, "rtl.css")
SCALE = 2          # PNG pixel density (natural size × 2 → crisp in Word and in print)
RENDER_VERSION = "5"
CACHE_DIR = os.path.join(tempfile.gettempdir(), "aman_spec_mermaid_cache")

HEB = r"\u05D0-\u05EA"


class DiagramError(Exception):
    pass


def find_mmdc():
    cands = [shutil.which("mmdc"), os.path.expanduser("~/.npm-global/bin/mmdc"),
             "/home/claude/.npm-global/bin/mmdc", "/usr/local/bin/mmdc"]
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise DiagramError(
        "mermaid-cli (mmdc) לא נמצא. התקנה: npm install -g @mermaid-js/mermaid-cli "
        "(אם אין רשת — לא ניתן לייצר תרשימים בסביבה הזו; ראה SKILL.md)")


def find_browser():
    """Locate a Chromium for mermaid-cli. Container images move it around (chrome-linux → chrome-linux64,
    new version folders), so look in several ways before giving up."""
    env = os.environ.get("MERMAID_CHROME") or os.environ.get("PUPPETEER_EXECUTABLE_PATH")
    if env and os.access(env, os.X_OK):
        return env
    home = os.path.expanduser("~")
    pats = [
        f"{home}/.cache/puppeteer/chrome/*/chrome-linux*/chrome",
        "/root/.cache/puppeteer/chrome/*/chrome-linux*/chrome",
        "/opt/pw-browsers/chromium-*/chrome-linux*/chrome",
        "/opt/pw-browsers/chromium_headless_shell-*/chrome-linux*/*headless_shell",
        f"{home}/.cache/ms-playwright/chromium-*/chrome-linux*/chrome",
        "/opt/google/chrome/chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
    ]
    for p in pats:
        for hit in sorted(glob.glob(p), reverse=True):
            if os.access(hit, os.X_OK):
                return hit
    for root in ("/opt/pw-browsers", f"{home}/.cache/ms-playwright", f"{home}/.cache/puppeteer"):
        if os.path.isdir(root):
            for dirpath, _, files in os.walk(root):
                for name in ("chrome", "headless_shell", "chrome-headless-shell"):
                    if name in files and os.access(os.path.join(dirpath, name), os.X_OK):
                        return os.path.join(dirpath, name)
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        w = shutil.which(name)
        if w:
            return w
    try:  # Python Playwright knows where its own browser is
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exe = pw.chromium.executable_path
            if exe and os.access(exe, os.X_OK):
                return exe
    except Exception:
        pass
    return None  # let puppeteer try its own default


RLM = "\u200F"
# where a label starts: [ ( { | " : <br/> -- and "participant X as"
_LABEL_START = r'(?:[\[\(\{\|":]|<br\s*/?>|--|\bas\b)'


def prepare_source(src, lang="he"):
    """Small text fixes that make Hebrew labels wrap and read correctly."""
    s = src.replace("\r\n", "\n").strip("\n") + "\n"
    # keep a Hebrew prefix glued to the English/number after it (ב-App_Cars, ה-API): word joiner
    s = re.sub(rf"([{HEB}])([-\u05BE])(?=[A-Za-z0-9_])", "\\1\\2\u2060", s)
    out = []
    for line in s.split("\n"):
        if re.search(rf"[{HEB}]", line):
            # in Hebrew labels, symbols glued to an English word stay on its side (OPS+, C#, .NET, @user)
            line = re.sub(r"([A-Za-z0-9_])([+#%*°™®]+)", "\\1\\2\u200E", line)
            line = re.sub(r"(^|[\s(\[\"'])([@#$.])(?=[A-Za-z])", "\\1\u200E\\2", line)
            if lang == "he":
                # a Hebrew label that starts with an English word ("Bluetooth פעיל?", "GET /v1 עם מסננים")
                # must still be laid out right-to-left: anchor it with RLM
                line = re.sub(rf"({_LABEL_START})(\s*)(?=[A-Za-z0-9][^\]\}}\|\"\n<>\[]*[{HEB}])",
                              lambda m: m.group(1) + m.group(2) + RLM, line)
        out.append(line)
    return "\n".join(out)


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise DiagramError(f"{path} אינו PNG")
    return struct.unpack(">II", head[16:24])


def _cache_key(src):
    h = hashlib.sha256()
    for part in (RENDER_VERSION, str(SCALE), open(CONFIG, encoding="utf8").read(),
                 open(CSS, encoding="utf8").read(), src):
        h.update(part.encode("utf8"))
    return h.hexdigest()[:24]


def _explain(stderr, src, did):
    msg = stderr.strip()
    m = re.search(r"(Parse error on line (\d+):[\s\S]*?)(?:\n\s+at |\Z)", msg)
    lines = src.split("\n")
    if m:
        ln = int(m.group(2))
        k = min(ln, len(lines))
        while k > 1 and not lines[k - 1].strip():
            k -= 1
        bad = lines[k - 1] if 0 < k <= len(lines) else ""
        detail = m.group(1).strip().split("\n")
        hint = ""
        if re.search(r"[\[\{]\s*[^\"\]\}]*[()]", bad):
            hint = ("\n    רמז: תווית עם סוגריים / תווים מיוחדים חייבת להיות במרכאות כפולות, "
                    "למשל A[\"שליחה ל-API (POST)\"]")
        return (f"תרשים \"{did}\": שגיאת תחביר Mermaid בשורה {ln}: {bad.strip()!r}\n    "
                + "\n    ".join(detail[:4]) + hint)
    first = [l for l in msg.split("\n") if l.strip() and not l.strip().startswith("at ")]
    return f"תרשים \"{did}\": Mermaid נכשל — " + " | ".join(first[:4])[:600]


def render(src, out_png, did="diagram", lang="he"):
    """Render one Mermaid source to out_png. Returns (natural_width, natural_height) in CSS px."""
    src = prepare_source(src, lang)
    if not src.strip():
        raise DiagramError(f"תרשים \"{did}\": קוד Mermaid ריק")
    key = _cache_key(src)
    os.makedirs(CACHE_DIR, exist_ok=True)
    cached = os.path.join(CACHE_DIR, key + ".png")
    if not os.path.exists(cached):
        mmdc = find_mmdc()
        with tempfile.TemporaryDirectory(prefix="mmd_") as td:
            inp = os.path.join(td, "in.mmd")
            with open(inp, "w", encoding="utf8") as f:
                f.write(src)
            pconf = os.path.join(td, "puppeteer.json")
            browser = find_browser()
            pc = {"args": ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]}
            if browser:
                pc["executablePath"] = browser
            with open(pconf, "w") as f:
                json.dump(pc, f)
            tmp_out = os.path.join(td, "out.png")
            cmd = [mmdc, "-i", inp, "-o", tmp_out, "-s", str(SCALE), "-b", "white", "-w", "1800",
                   "-c", CONFIG, "-C", CSS, "-p", pconf, "-q"]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            except subprocess.TimeoutExpired:
                raise DiagramError(f"תרשים \"{did}\": הרינדור לא הסתיים תוך 180 שניות")
            if r.returncode != 0 or not os.path.exists(tmp_out):
                err = r.stderr or r.stdout
                if "Could not find Chrome" in err or "Failed to launch" in err:
                    raise DiagramError(
                        f"תרשים \"{did}\": לא נמצא דפדפן Chromium לרינדור Mermaid. "
                        "אפשר להגדיר נתיב ב־MERMAID_CHROME=/path/to/chrome")
                raise DiagramError(_explain(err, src, did))
            shutil.copyfile(tmp_out, cached)
    shutil.copyfile(cached, out_png)
    w, h = png_size(out_png)
    return round(w / SCALE), round(h / SCALE)


def section_numbers(spec):
    """Same numbering as build_spec.js: 1, 1.1, 1.1.1 by position."""
    nums = {}

    def rec(lst, prefix):
        for i, s in enumerate(lst or []):
            n = f"{prefix}.{i + 1}" if prefix else f"{i + 1}"
            if isinstance(s, dict):
                if s.get("id"):
                    nums[s["id"]] = (n, s.get("title", ""))
                rec(s.get("sections"), n)
    rec(spec.get("sections"), "")
    return nums


def resolve_refs(src, nums, vars_, did):
    """{{sec:id}} → section number, {{title:id}} → title, {{var}} → vars (only if defined:
    Mermaid itself uses {{...}} for hexagon nodes, so unknown names are left alone)."""
    def rep(m):
        kind, key = m.group(1), m.group(2)
        if not kind:
            return str(vars_[key]) if key in vars_ else m.group(0)
        if kind in ("sec", "title"):
            if key not in nums:
                raise DiagramError(f"תרשים \"{did}\": הפניה לסעיף \"{key}\" שלא קיים ({m.group(0)})")
            return nums[key][0] if kind == "sec" else nums[key][1]
        raise DiagramError(f"תרשים \"{did}\": בתוך תרשים נתמכות רק הפניות sec / title ({m.group(0)})")
    return re.sub(r"\{\{\s*(?:([a-z]+):)?([A-Za-z0-9_\-]+)\s*\}\}", rep, src)


def walk_blocks(spec):
    def rec(sections):
        for s in sections or []:
            for b in s.get("blocks") or []:
                yield b
            yield from rec(s.get("sections"))
    yield from rec(spec.get("sections"))


def render_spec(spec_path, out_dir):
    with open(spec_path, encoding="utf8") as f:
        spec = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    manifest, errors = {}, []
    spec_dir = os.path.dirname(os.path.abspath(spec_path))
    nums = section_numbers(spec)
    vars_ = spec.get("vars") or {}
    for b in walk_blocks(spec):
        if b.get("type") != "diagram":
            continue
        did = b.get("id")
        if not did or not re.match(r"^[A-Za-z][A-Za-z0-9_\-]*$", did):
            errors.append(f"לכל בלוק diagram חייב להיות id לטיני (התקבל {did!r})")
            continue
        src = b.get("mermaid")
        if src is None and b.get("mermaid_file"):
            p = b["mermaid_file"]
            p = p if os.path.isabs(p) else os.path.join(spec_dir, p)
            with open(p, encoding="utf8") as f:
                src = f.read()
        if isinstance(src, list):
            src = "\n".join(src)
        if not src:
            errors.append(f"תרשים \"{did}\": חסר mermaid (מחרוזת או מערך שורות)")
            continue
        out_png = os.path.join(out_dir, f"{did}.png")
        try:
            src = resolve_refs(src, nums, vars_, did)
            w, h = render(src, out_png, did, (spec.get("meta") or {}).get("lang", "he"))
            manifest[did] = {"png": out_png, "width": w, "height": h}
        except DiagramError as e:
            errors.append(str(e))
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest, errors


def main():
    a = sys.argv[1:]
    if len(a) == 3 and a[0] == "--mmd":
        with open(a[1], encoding="utf8") as f:
            src = f.read()
        try:
            w, h = render(src, a[2], os.path.basename(a[1]))
        except DiagramError as e:
            print("❌ " + str(e))
            sys.exit(1)
        print(f"✓ {a[2]} ({w}×{h} px)")
        return
    if len(a) != 2:
        print(__doc__)
        sys.exit(2)
    manifest, errors = render_spec(a[0], a[1])
    for k, v in manifest.items():
        print(f"✓ תרשים {k}: {v['width']}×{v['height']} px")
    if errors:
        print("❌ תרשימים שנכשלו:")
        for e in errors:
            print("  - " + e)
        sys.exit(1)


if __name__ == "__main__":
    main()
