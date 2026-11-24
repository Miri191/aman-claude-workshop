---
name: aman-digital-hld
description: 'מסמכי HLD של אמן דיגיטל בתבנית הבית: Word ממותג מימין לשמאל עם שער מעוצב (לוגו אמן משמאל, לוגו הלקוח מימין), מבנה פרקים אחיד על בסיס ה־HLD של BSI, מיפוי תהליכים לפי מערכות, ספריית נוסחים (אבטחת מידע, הנחות יסוד, אחריות, בדיקות, SLA, פרטיות), תרשימים ובדיקות לשון, מספור וכיווניות. Use whenever the user asks for an HLD, מסמך HLD, High Level Design, אפיון על or אפיון ברמה גבוהה, or for a document describing a whole project (vision, scope, participating systems, responsibilities, business processes, interfaces, architecture, security, work plan), even if they only paste meeting notes, an RFP, a quote or a requirements document and say "תכין HLD". Also use it to update an existing HLD, move it to the house format, or check an HLD before it goes to the client. For a detailed spec of one API, screen or database, use aman-tech-spec instead.'
---

# Aman Digital HLD documents (מסמכי HLD של אמן דיגיטל)

An HLD describes a whole project at the level a client signs off on: why the client is doing it,
what is in and out of scope, which systems take part and who is responsible for what, the business
processes, the data that flows between systems, the architecture, security, delivery and the work
plan. It is read by the client's management, product, IT, architects and CISO, and is often
attached to the agreement, so every statement has to be accurate and every gap visible.

The skill produces a `.docx` in the house design (logo header, title block, change log, real Word TOC,
numbered chapters, blue/navy tables, diagrams, page X of Y), built from a JSON description by the
same engine as aman-tech-spec, with everything that can be checked checked before delivery:

- **Language** — Hebrew by default, technical terms and product names in English. Every string is
  spell-checked (hspell) and checked for confusable words, gender agreement, register and AI-sounding
  phrases; errors stop the build.
- **Direction** — every paragraph, table and run right-to-left, English isolated so Word keeps its
  word order.
- **Consistency** — chapter, figure and table numbers and every cross reference are computed; the
  version on the title page is the last change-log row.
- **The file** — validated against the OOXML schema, then QA'd independently from the finished docx.

All scripts are in this skill's folder (the folder containing this SKILL.md) — `SKILL_DIR` below.
Work in `/home/claude/work/`; the skill folder may be read-only.

## Pick the mode

| The user… | Mode |
|---|---|
| asks for a new HLD (from notes, a transcript, an RFP, a requirements document, a quote, a presentation) | **A. New HLD** |
| uploads an existing HLD and wants it updated / in the house format / translated | **B. Rebuild** |
| asks to check / review an HLD ("תבדוק את ה־HLD") | **C. QA only** |
| asks for changes to an HLD you built earlier in this conversation | edit the JSON, add a change-log row, proofread, rebuild (A.5–A.8) |

## A. New HLD

### 1. Read everything
Attachments, pasted text, earlier messages, past chats about this client or project. For each source
note what it covers (vision, systems, processes, interfaces, architecture, dates, commitments). An
agreement or quote is the source for assumptions, responsibilities, dates and SLA — read it closely.

### 2. Ask before writing (mandatory)
An HLD is only as accurate as its scope and sources, so settle them first. Ask only what the materials
don't already answer. In the chat app use the tappable-options tool (one call, up to three questions)
with a one-line intro such as "כדי שה־HLD יצא מדויק, כמה שאלות קצרות:". Ask in Hebrew:

1. **אילו פרקים אופציונליים לכלול?** (multi-select) — משתמשים והרשאות · מסכים וחבילות עבודה ·
   מיגרציית נתונים · נספח השוואה למסמך הדרישות / להסכם
2. **על מה ה־HLD מתבסס?** (multi-select) — מסמך דרישות / RFP · הסכם או הצעת מחיר · סיכומי פגישות ·
   תרשים ארכיטקטורה קיים
3. A question that is critical for this HLD when there is one: the client's short name as it should
   appear, the author's name for the change log if you don't know it, the phase (MVP / שלב א׳), or
   whether the work plan should include dates.

Ask for the **client's logo** (PNG / JPEG) in the same message if it wasn't attached — it goes on the
right of the cover and of every page header (`meta.client_logo`). Don't cut a logo out of a screenshot
or a document; without a proper file the right side simply stays empty.

All other chapters are always included (hld-structure.md). **Then check the materials against the
scope**: something the chapters need that wasn't attached (the agreement for SLA and assumptions, an
architecture drawing, the list of systems) → ask for it. If the user doesn't have it or wants to go on,
say plainly before you build which parts will be less certain — "פרק ה־SLA לא יהיה מדויק כי חסר
ההסכם" — and record it in the document: the `sources` table with status "חסר", a `callout warning`
under it, and open issues with owners. Never fill a gap with invented systems, interfaces, numbers,
dates, people or commitments.

If nobody can answer (an automated run), include the optional chapters the materials support, and
list your assumptions in the sources callout and in the delivery message.

### 3. Plan the chapters
Read `references/hld-structure.md` — the chapter order, what each chapter contains, and which table
preset to use. The order and the chapter names are fixed; that is what makes the department's HLDs
uniform. Whenever more than one system takes part — adjacent systems (מערכות משיקות) included — chapter 2
has the sub-section **מיפוי תהליכי העבודה בחלוקה למערכות**: for each system, the processes that touch
it, what happens there, who owns it and whether it is in the project's scope. It is what draws the
project's boundary, so build it before writing chapter 5 and keep the two consistent.
Chapter 5 (פירוט דרישות) is the heart of the document: one sub-section per business process,
with a flow wherever there is a decision or more than one system.

### 4. Write the HLD JSON
1. Copy `examples/he_hld_bsi_extra_club.json` (a complete HLD built from the department's BSI HLD) to
   `/home/claude/work/<name>.json` and replace its content chapter by chapter.
2. Read `references/spec-format.md` for blocks, presets, references and the HLD presets
   (`systems`, `data_flows`, `governance`, `schedule`, `sla`…). Use the presets for every standard
   table — they keep column names identical across HLDs.
3. Security, project assumptions, responsibilities, testing, environments, privacy, support and go-live
   start from `references/boilerplate.md`. Adapt each text to this client (name, cloud, identity
   product, industry regulation); take every number, date and commitment from the agreement / quote;
   items marked ⟨לאישור⟩ that the sources don't confirm become open issues.
4. Diagrams (`references/diagrams.md`, "Diagrams in an HLD"): the participating-systems map, one flow
   per business process, the architecture (the client's drawing as `image` when there is one).
5. Refer with `{{sec:id}}` / `{{fig:id}}`, never with typed numbers.
6. Author: the requesting user, in Hebrew ("לילך וייס"), or "צוות אפיון – אמן דיגיטל" if they ask.
7. Write by `references/writing-style.md`. Go through the completeness checklist at the end of
   `hld-structure.md`; gaps become open issues.

### 5. Proofread (mandatory)
Follow `writing-style.md` §4: read every string as an editor — agreement, confusable words
(תכולה ↔ תחולה), prepositions, natural sentences, technical terms left in English, no filler. Chapter 1
is business language but must still say something specific to this client in every bullet.

### 6. Build
```bash
python3 SKILL_DIR/scripts/make_spec.py /home/claude/work/<name>.json /home/claude/work/<file>.docx
```
One command: language check (stops on errors) → diagrams → build → TOC page numbers → OOXML schema →
QA → page previews. Fix the HLD, never the check. Correct words the dictionary doesn't know (client and
product names, domain words) go in `"spell_ignore"`. Treat warnings as things to fix (a diagram shrunk
below 65% → split the flow or change direction; AI-style phrases) unless there is a reason to keep them.

### 7. QA and look
The QA report must show **0 errors**. View the contact sheets the build prints
(`.../preview/sheet-N.jpg`) and any page that needs a closer look (`page-NN.jpg`): Hebrew right-aligned,
English fragments in order, tables not split awkwardly, diagrams legible.

### 8. Deliver
Copy the docx to `/mnt/user-data/outputs/` named `HLD_<לקוח>_<פרויקט>_v<גרסה>.docx` and present it.
Then briefly, in Hebrew:
- what the HLD covers (chapters, number of processes and diagrams);
- the verification line ("נבדקו לשון ואיות, הפניות, מספור וכיווניות – 0 שגיאות");
- **what was missing and which chapters are less certain because of it**;
- the open issues the client needs to answer, and texts from the library marked for approval;
- inconsistencies found between the sources and how they were resolved.

## B. Rebuild an existing HLD
1. Read it (`pandoc -t markdown file.docx`; tables built from text boxes may come out empty — read
   them with python-docx from the XML; for images `unzip` the docx and look at `word/media`).
2. Run QA on the original first (mode C) — its findings are part of what you fix and report.
3. Transcribe into the HLD JSON in the house chapter order: keep the author's content and meaning, fix
   language errors, move typed lists to real lists, tables to presets, empty chapters to open issues.
   Process drawings may be redrawn in Mermaid when they are readable; otherwise keep them as `image`.
   Architecture drawings with logos stay images.
4. Correct technical errors in standard texts with `boilerplate.md` (e.g. encryption at rest is
   AES-256, not MD5 / SHA1) and list every correction. The list of corrections goes in the delivery
   message, not in the document: quoting the original's misspellings inside the HLD would fail the
   language check, and the client doesn't need them.
5. When the original contradicts itself (a systems table vs. the architecture drawing, a number in two
   places), follow the most authoritative source (drawing / agreement), mark the choice "לאישור" and
   add an open issue.
6. Keep the original change log (or start one with the original's version and date) and add a row for
   this version.
7. Continue with A.5–A.8.

## C. QA only
```bash
python3 SKILL_DIR/scripts/qa_spec.py <file>.docx            # add --spec hld.json for an HLD built here
```
Works on any HLD, including hand-written ones: tracked changes and open comments (an error — deleted
text and reviewers' remarks are visible to the client), direction, structure, references and the full
language check. The printed lists are shortened; for the complete spelling list call
`he_lint.lint_texts` on the extracted text. When the file has tracked changes, read it as if they were
accepted (python-docx: skip `w:del`, keep `w:ins`) and report the changes and comments themselves as
the first finding, quoting internal remarks that would reach the client.

Write the report in Hebrew (a `qa_report.md` when the user asks for a file): blockers first (tracked
changes, comments, placeholders on the title page), then errors with the exact text, inconsistencies
between chapters, chapters missing against `hld-structure.md`, language, and what was verified. Add
your own reading against the completeness checklist in `hld-structure.md` (missing chapters, systems
that appear in one place and not another, commitments without a source). Offer to rebuild it in the
house format (mode B).

## What you get without writing it
A designed cover page: Aman Digital's logo on the left and the client's on the right, a navy title band
with "מסמך HLD", the title and the subtitle, and the document details (client, project, version, date,
author, status); the change log and TOC start on page 2. On every other page: a header with both logos
(Aman left, client right), "מסמך HLD", title and version; footer with company, address,
confidentiality note and "עמוד X מתוך Y"; title block, details table, change log, a real Word TOC field
with page numbers; numbered headings (Word Heading styles); blue header rows that repeat on every page,
zebra rows, group rows, numbered rows; callout boxes; real bullet / numbered lists; figure captions.
Brand values live in `assets/brand.json` and `assets/logo.png`, diagram theme in `assets/mermaid/`.

## Files
- `scripts/make_spec.py` — the one command (language → diagrams → build → TOC pages → schema → QA → previews)
- `scripts/he_lint.py` — language check; `python3 he_lint.py hld.json` or `--text "..."` to try a sentence
- `scripts/build_spec.js` — JSON → docx (Node, preinstalled `docx` package); HLD presets and defaults
- `scripts/render_diagrams.py` — Mermaid → PNG with RTL fixes; `--mmd file.mmd out.png` to try one
- `scripts/qa_spec.py` — QA for any docx; `--json` for machines
- `references/hld-structure.md` — chapter order, contents, presets, completeness checklist
- `references/boilerplate.md` — standard texts to adapt (security, assumptions, responsibilities,
  testing, environments, privacy, support, go-live)
- `references/spec-format.md` · `references/writing-style.md` · `references/diagrams.md`
- `examples/he_hld_bsi_extra_club.json` + `examples/assets/` — a complete HLD
- `tests/run_tests.py` — regression suite. Run it after changing anything in `scripts/`.

## Environment notes
Needs Node with `docx`, Python 3 with `python-docx` and `pypdf`, LibreOffice (`soffice`) for page numbers
and previews, `mmdc` (mermaid-cli) with a Chromium for diagrams, and `hspell` for Hebrew spelling — the
build installs hspell with apt-get when it is missing and allowed; otherwise it says so and the manual
proofreading in A.5 carries the full weight. Without LibreOffice the docx is still produced, with TOC
page numbers left for Word (right-click → Update Field).
