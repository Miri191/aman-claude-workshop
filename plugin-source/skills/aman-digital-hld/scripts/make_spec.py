#!/usr/bin/env python3
"""
make_spec.py — one command from spec.json to a finished, verified Word spec (Aman Digital)

    python3 make_spec.py <spec.json> <out.docx> [--work DIR] [--no-preview] [--dpi 60]

Steps:
  1. render the Mermaid diagrams (render_diagrams.py; cached)
  2. build the docx (build_spec.js)
  3. if there is a table of contents: render to PDF with LibreOffice, read the real page of every
     heading from the PDF outline, rebuild with those page numbers, verify they did not move
  4. QA (qa_spec.py --spec) — exit code 1 if QA finds errors
  5. page previews: <work>/preview/page-NN.jpg and contact sheets <work>/preview/sheet-N.jpg
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_diagrams  # noqa: E402
import he_lint  # noqa: E402

DOCX_SOFFICE = "/mnt/skills/public/docx/scripts/office"


def soffice_pdf(docx, outdir):
    os.makedirs(outdir, exist_ok=True)
    args = ["--headless", "--convert-to", "pdf", "--outdir", outdir, docx]
    if os.path.exists(os.path.join(DOCX_SOFFICE, "soffice.py")):
        sys.path.insert(0, os.path.dirname(DOCX_SOFFICE))
        try:
            from office.soffice import run_soffice  # type: ignore
            r = run_soffice(args, capture_output=True, text=True, timeout=300)
        except ImportError:
            r = subprocess.run(["soffice"] + args, capture_output=True, text=True, timeout=300)
    else:
        r = subprocess.run(["soffice"] + args, capture_output=True, text=True, timeout=300)
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(docx))[0] + ".pdf")
    if not os.path.exists(pdf):
        raise RuntimeError("המרה ל־PDF נכשלה: " + (r.stderr or r.stdout)[-800:])
    return pdf


def try_pdf(docx, outdir):
    try:
        return soffice_pdf(docx, outdir)
    except Exception as e:  # LibreOffice missing / failing: keep going without page numbers & previews
        print(f"⚠️  LibreOffice לא זמין ({str(e)[:120]}) — תוכן העניינים בלי מספרי עמודים (ב־Word: קליק ימני → עדכון שדה), ללא תצוגה מקדימה")
        return None


def clean(t):
    t = re.sub(r"[\u200E\u200F\u2060\u202A-\u202E\u2066-\u2069]", "", t or "")
    return re.sub(r"\s+", " ", t).strip()


def outline_pages(pdf):
    from pypdf import PdfReader
    r = PdfReader(pdf)
    out = []

    def walk(o):
        for x in o:
            if isinstance(x, list):
                walk(x)
            else:
                try:
                    out.append((clean(x.title), r.get_destination_page_number(x) + 1))
                except Exception:
                    pass
    walk(r.outline)
    return out, len(r.pages)


def map_pages(headings, outline):
    """Match headings (document order) to outline entries (document order) by text."""
    pages, j, missing = {}, 0, []
    for h in headings:
        want = clean(h["text"])
        k = j
        while k < len(outline) and outline[k][0] != want:
            k += 1
        if k < len(outline):
            pages[h["bookmark"]] = outline[k][1]
            j = k + 1
        else:
            missing.append(h["text"])
    return pages, missing


def node_build(spec, out, manifest, info, pages=None):
    cmd = ["node", os.path.join(HERE, "build_spec.js"), spec, out, "--diagrams", manifest, "--info", info]
    if pages:
        cmd += ["--pages", pages]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r


def contact_sheets(pages, outdir, per=6):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return []
    sheets = []
    for s in range(0, len(pages), per):
        ims = [Image.open(p) for p in pages[s:s + per]]
        w = max(i.width for i in ims)
        h = max(i.height for i in ims)
        cols = 3
        rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w + (cols + 1) * 12, rows * (h + 26) + 12), "#DADDE3")
        d = ImageDraw.Draw(sheet)
        for i, im in enumerate(ims):
            x = 12 + (i % cols) * (w + 12)
            y = 12 + (i // cols) * (h + 26)
            sheet.paste(im, (x, y + 14))
            d.text((x, y), f"page {s + i + 1}", fill="#002148")
        p = os.path.join(outdir, f"sheet-{s // per + 1}.jpg")
        sheet.save(p, quality=85)
        sheets.append(p)
    return sheets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--work")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--dpi", type=int, default=60)
    a = ap.parse_args()

    spec = os.path.abspath(a.spec)
    out = os.path.abspath(a.out)
    stem = os.path.splitext(os.path.basename(out))[0]
    work = os.path.abspath(a.work or os.path.join(os.path.dirname(out), f".build_{stem}"))
    os.makedirs(work, exist_ok=True)
    info_p = os.path.join(work, "info.json")
    pages_p = os.path.join(work, "pages.json")
    for old in glob.glob(os.path.join(work, "preview", "*.jpg")):
        os.remove(old)

    # 0. language (spelling, confusable words, gender agreement, AI-style, translated terms)
    with open(spec, encoding="utf8") as f:
        spec_obj = json.load(f)
    he_lint.ensure_hspell(quiet=False)
    lint = he_lint.lint_spec(spec_obj)
    he_lint.report(lint, "בדיקת לשון")
    if not he_lint.ensure_hspell():
        print("ℹ️  hspell לא זמין – בדיקת איות מלאה לא בוצעה; הגהה ידנית מוגברת נדרשת")
    if any(x[0] == "error" for x in lint):
        print("❌ הבנייה נעצרה בגלל שגיאות לשון – תקן במפרט (או הוסף מונח נכון ל־spell_ignore) והרץ שוב.")
        sys.exit(1)

    # 1. diagrams
    ddir = os.path.join(work, "diagrams")
    manifest, derr = render_diagrams.render_spec(spec, ddir)
    if derr:
        print("❌ רינדור התרשימים נכשל — לא נוצר קובץ.")
        for e in derr:
            print("  - " + e)
        sys.exit(1)
    if manifest:
        print(f"✓ {len(manifest)} תרשימים רונדרו")
    man_p = os.path.join(ddir, "manifest.json")

    # 2. build
    r = node_build(spec, out, man_p, info_p)
    if r.returncode != 0:
        print((r.stdout + r.stderr).strip())
        sys.exit(1)
    info = json.load(open(info_p, encoding="utf8"))

    # 3. TOC page numbers
    pdf = None
    if info.get("toc"):
        pdf = try_pdf(out, work)
    if info.get("toc") and pdf:
        outline, _ = outline_pages(pdf)
        pages, missing = map_pages(info["headings"], outline)
        if missing:
            print(f"⚠️  {len(missing)} כותרות לא נמצאו ב־PDF outline: {missing[:3]}")
        for attempt in range(3):
            json.dump(pages, open(pages_p, "w"), ensure_ascii=False)
            r = node_build(spec, out, man_p, info_p, pages_p)
            if r.returncode != 0:
                print((r.stdout + r.stderr).strip())
                sys.exit(1)
            pdf = try_pdf(out, work)
            if not pdf:
                break
            outline, _ = outline_pages(pdf)
            new_pages, _ = map_pages(info["headings"], outline)
            if new_pages == pages:
                break
            pages = new_pages
        else:
            print("⚠️  מספרי העמודים בתוכן העניינים לא התייצבו אחרי 3 סבבים")
        print(f"✓ תוכן עניינים: {len(pages)} כותרות עם מספרי עמוד")
    print(r.stdout.strip())

    # 3b. OOXML schema validation (when the docx skill's validator is available)
    validator = os.path.join(DOCX_SOFFICE, "validate.py")
    schema_ok = True
    if os.path.exists(validator):
        v = subprocess.run([sys.executable, validator, out], capture_output=True, text=True)
        if "All validations PASSED" in v.stdout:
            print("✓ תקינות קובץ Word מול סכמת OOXML: עבר")
        else:
            schema_ok = False
            print("❌ קובץ ה־Word נכשל בבדיקת סכמת OOXML:")
            print("\n".join("   " + l for l in v.stdout.splitlines() if "FAILED" in l or "Element" in l or "Duplicate" in l)[:2000])

    # 4. QA
    qa = subprocess.run([sys.executable, os.path.join(HERE, "qa_spec.py"), out, "--spec", spec],
                        capture_output=True, text=True)
    print("\n" + qa.stdout.strip())
    if qa.stderr.strip():
        print(qa.stderr.strip()[-1500:])

    # 5. previews
    if not a.no_preview and pdf is None:
        pdf = try_pdf(out, work)
    if not a.no_preview and pdf:
        pdir = os.path.join(work, "preview")
        os.makedirs(pdir, exist_ok=True)
        subprocess.run(["pdftoppm", "-jpeg", "-r", str(a.dpi), pdf, os.path.join(pdir, "page")], check=False)
        pages_img = sorted(glob.glob(os.path.join(pdir, "page-*.jpg")))
        sheets = contact_sheets(pages_img, pdir)
        print(f"\n🖼  {len(pages_img)} עמודים | תצוגה מקדימה: {pdir}")
        for s in sheets:
            print(f"   {s}")
    sys.exit(qa.returncode or (0 if schema_ok else 1))


if __name__ == "__main__":
    main()
