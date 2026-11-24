# HLD JSON format

(The engine is shared with aman-tech-spec, so the file is still called a "spec" below.)

The spec is the single source of the document. Write it as UTF-8 JSON; the builder turns it into the
branded Word file. Anything the builder can compute (section / figure / table numbers, references,
version, dates, TOC) is computed — never typed.

Contents: 1. Top level · 2. meta · 3. changelog · 4. sections · 5. blocks · 6. tables and presets ·
7. text features · 8. checks · 9. language check · 10. errors you will see

## 1. Top level

```json
{
  "meta":      { ... },          // required
  "vars":      { "svc": "UpdateCarBluetooth" },   // optional, {{svc}} anywhere in text
  "changelog": [ ... ],          // required, at least one row
  "sections":  [ ... ],          // required
  "checks":    [ ... ],          // optional (strongly recommended for API specs)
  "spell_ignore": [ ... ]        // optional: correct words the Hebrew dictionary doesn't know
}
```

## 2. meta

| key | | |
|---|---|---|
| `lang` | `"he"` (default) or `"en"` | `he` → everything right-to-left; `en` → everything left-to-right |
| `title` | required | big title on page 1 and in the page header |
| `doc_type` | optional | small label above the title and in the page header. Default "מסמך HLD" / "High-Level Design (HLD)". Leave the default |
| `subtitle` | optional | one line under the title (shown in the cover band) |
| `client_logo` | optional | path (relative to the JSON, or absolute) to the client's logo, PNG / JPEG. Shown on the right of the cover and of every page header; Aman Digital's logo is always on the left. Without it the right side stays empty |
| `client`, `project` | optional | details table |
| `authors` | string or array | "נכתב ע״י" – in the document's language (Hebrew names in a Hebrew spec; the build fails otherwise) |
| `status` | optional | e.g. טיוטה / לסקירת הלקוח / מאושר לפיתוח |
| `version`, `date` | optional | default: last changelog row. If given, `version` must equal the last row |
| `details` | `[["label", "value"], ...]` | extra rows in the details table |
| `toc` | `true` / `false` / omitted | omitted = automatic (≥ 5 top-level sections or ≥ 10 sections in total) |
| `toc_levels` | 1–3, default 2 | heading levels shown in the TOC |
| `header_note`, `footer_note` | optional | override the page-header text / the confidentiality note |

## 3. changelog

```json
"changelog": [
  { "version": "1.0", "date": "2026-05-25", "author": "דפנה ניר", "changes": "גרסה ראשונית – יצירת המסמך." },
  { "version": "1.1", "date": "2026-05-27", "author": "דפנה ניר", "changes": "הוספת dateBasis – ראה סעיף {{sec:logic}}." }
]
```
Dates are ISO (`YYYY-MM-DD`); they are printed as `25.05.2026` (he) / `25 May 2026` (en).
`author` is in the document's language – a Hebrew name in a Hebrew spec. Versions
must increase. A new spec starts with one row: version 1.0, today's date, "גרסה ראשונית".
When you revise a spec, **add** a row (never edit old rows) describing what changed and where.

## 4. sections

```json
{ "id": "logic", "title": "לוגיקה", "blocks": [ ... ], "sections": [ ... ] }
```
- Numbered automatically by position: 1, 1.1, 1.1.1 (max 3 levels). Don't type numbers in titles.
- `id` (latin letters, digits, `_` `-`) lets text refer to the section: `{{sec:logic}}` → "4".
- A section needs blocks or sub-sections; an empty section is a build error (put "יושלם בהמשך" items
  in the open-issues table instead).
- `part`: on a top-level section, a navy banner before it ("חלק א – שירות שליפה"). Parts appear in the
  TOC but don't affect numbering. Use for specs with several services.
- `page_break_before: true` — start the section on a new page.

## 5. blocks

| type | fields | notes |
|---|---|---|
| `p` | `text` | paragraph. Inline `**bold**`, `` `code` ``, refs |
| `sub` | `text` | small bold sub-heading, not numbered, not in TOC ("רכיבי המסך", "דוגמת קלט") |
| `note` | `text` | small grey text |
| `callout` | `text`, `kind`, `label` | boxed. kind: `note` (הערה), `info` (לידיעה), `warning` (שים לב), `decision` (החלטה), `open` (סוגיה פתוחה). `label` overrides the prefix; `"label": false` removes it |
| `bullets` | `items` | strings or `{ "text": "...", "sub": ["...", "..."] }` |
| `numbered` | `items` | same; numbering restarts at 1 in every block; sub-items are 1.1, 1.2 |
| `table` | see §6 | |
| `kv` | `rows` or `preset` + `data` | two-column label/value table |
| `code` | `json` (object) **or** `text` / `lines`, `language`, `title`, `id` | always left-to-right, monospace |
| `diagram` | `id`, `mermaid`, `caption`, `scale`, `width_pct`, `max_height_cm` | Mermaid → PNG; see diagrams.md |
| `image` | `path` or `paths`, `caption`, `height_cm` / `width_cm`, `id` | screenshots / designs; several paths = side by side (first one on the right in Hebrew) |
| `page_break` | | |

**code blocks**
- Give JSON examples as a real object: `"json": { ... }` — they are pretty-printed and always valid.
- `"text"` with `"language": "json"` is parsed and the build fails if it is invalid. If the example
  deliberately elides parts (`[ ... ]`), add `"lenient": true`.
- Other languages (`http`, `sql`, `xml`, `text`) are shown as-is. Give `id` to JSON examples that a
  check compares to a table.

**diagram / image**
- `caption` → "תרשים 3 – ..." numbered automatically; `{{fig:id}}` refers to it. Without a caption the
  figure is not numbered.
- `image.path` is relative to the spec file, or absolute (`/mnt/user-data/uploads/screen.png`). PNG/JPEG.
- Screens: `height_cm` 7.5–8 is the house size; up to 3 screens side by side.

## 6. tables and presets

```json
{ "type": "table", "id": "resp_fields", "columns": "api_response",
  "rows": [
    { "group": "identification – זיהוי טיסה" },
    { "name": "identification.airlineCode", "desc": "קוד חברת תעופה", "type": "String", "example": "LY", "notes": "Master_Flights.Airline" },
    [ "identification.flightNumber", "מספר טיסה", "String", "315", "Master_Flights.FlightNo" ]
  ],
  "caption": "...", "note": "...", "hide": ["example"], "labels": { "notes": "מקור" }, "numbered": true, "font_size": 17 }
```
- `columns`: a preset name (below) or an explicit list
  `[{ "key": "name", "label": "שם השדה", "width": 1.5, "code": true, "center": false, "bold": false }]`
  (`width` is a relative weight; `code` = monospace LTR; strings like `"שם"` are also accepted).
- Rows: object by key, or array in column order. `{ "group": "..." }` = full-width group row.
- Cell values: string (`\n` = new line), **array → bullet list inside the cell**, `true/false` → כן/לא
  (Yes/No), number. Inline markup and refs work in cells.
- Header row repeats on every page; tables up to 14 rows are kept on one page.
- `caption` → "טבלה N – ..." and `{{tbl:id}}`. Don't caption every table — only ones you refer to.

**Column presets** (labels follow `meta.lang`; keys are what you use in row objects)

| preset | keys → labels (he) |
|---|---|
| `api_request` | name שם השדה · desc תיאור · type סוג · req חובה · example דוגמה · notes הערות |
| `api_response` | name שם השדה · desc תיאור · type סוג · example דוגמה · notes מקור נתונים / הערות |
| `screen_components` | field שדה · desc תיאור רכיב · type סוג רכיב · source מקור נתונים · notes הערות |
| `db_table` | name שם השדה · type סוג נתונים · req חובה · key מפתח · desc תיאור · notes הערות |
| `errors` | code קוד · desc תיאור · when מתי מוחזר · action פעולה מומלצת |
| `glossary` | term מונח · desc הסבר |
| `mapping` | source שדה מקור · target שדה יעד · notes הערות / המרה |
| `params` | name שם הפרמטר · value ערך |
| `environments` | env סביבה · url כתובת |
| `nfr` | topic נושא · requirement דרישה · notes הערות |
| `states` | state מצב · condition תנאי · behavior תצוגה / התנהגות |
| `open_issues` | issue סוגיה · owner באחריות · status סטטוס (numbered 1, 2, 3) |
| `test_cases` | scenario תרחיש · steps צעדים · expected תוצאה צפויה (IDs TC-01…) |
| `sources` | source מקור · status סטטוס · notes הערות (Used / Partial / Missing – בעברית: בשימוש / חלקי / חסר) |
| `requirements` | requirement דרישה · priority עדיפות · source מקור / הערות (IDs REQ-01…, set `"numbered": "FR"` / `"NFR"`) |
| `components` | component רכיב · responsibility אחריות · technology טכנולוגיה · owner באחריות |
| `decisions` | decision החלטה · rationale נימוק · alternatives חלופות שנבחנו (IDs D-01…) |
| `risks` | risk סיכון · impact השפעה · likelihood סבירות · mitigation דרך התמודדות (IDs R-01…) |
| `error_handling` | failure כשל · detection זיהוי · handling טיפול · retry Retry |
| `monitoring` | signal מדד / אירוע · condition תנאי / סף · severity חומרה · action פעולה |
| `config` | key מפתח · type סוג · default ברירת מחדל · desc תיאור |
| `events` | event אירוע · producer מפיק · consumer צרכן · notes תוכן / הערות |

**HLD presets** (hld-structure.md says where each one is used)

| preset | keys → labels (he) |
|---|---|
| `systems` | system מערכת · product מוצר / טכנולוגיה · vendor חברה / ספק · role תפקיד בפתרון (numbered; use `group` rows: מערכות \<הלקוח\>, מערכות שיפותחו בפרויקט, צד ג׳, תשתיות, DevOps) |
| `process_map` | process תהליך · activity מה מתבצע במערכת · owner באחריות · scope בתכולת הפרויקט (`true`/`false` → כן/לא). One `group` row per system |
| `user_roles` | role סוג משתמש / תפקיד · count מס׳ משתמשים · permissions פעולות והרשאות · restrictions ללא גישה |
| `kpis` | kpi מדד · target יעד · measure אופן מדידה |
| `data_flows` | data נתונים / ממשק · from ממערכת · to למערכת · mode אופן העברה · frequency תדירות · notes הערות (numbered) |
| `screen_index` | package חבילה · screen מסך · process תהליך / רכיב במסך · system מערכת · interface ממשק · interface_name שם ממשק |
| `work_packages` | package חבילה · dates מועדים · contents תכולה (array → list in the cell) · milestone תוצר / אבן דרך |
| `schedule` | task משימה / שלב · owner באחריות · start התחלה · end סיום · deliverable תוצר (numbered) |
| `governance` | forum פורום · lead בראשות · members משתתפים · purpose מטרה · frequency תדירות |
| `team` | name שם · role תפקיד בפרויקט · org ארגון · notes אחריות עיקרית |
| `traceability` | req_ref סעיף במסמך הדרישות / בהסכם · hld_ref סעיף ב־HLD (use `{{sec:id}}`) · notes הערות |
| `hld_environments` | env סביבה · purpose ייעוד · hosting תשתית / אירוח · owner באחריות · data נתונים |
| `test_levels` | level סוג בדיקה · scope מה נבדק · owner באחריות · env סביבה · exit תנאי סיום |
| `sla` | severity חומרה · definition הגדרה · response זמן תגובה · resolution זמן פתרון / עקיפה |
| `migration` | entity נתונים / ישות · source מערכת מקור · volume היקף · method אופן ההסבה · owner באחריות |

Reused from the general list: `glossary`, `sources`, `open_issues`, `nfr`, `components`, `decisions`,
`risks`, `requirements`. Scenario tables with a column per party (BSI "תהליכי התחשבנות") use explicit
`columns`.

**Row numbering**: `"numbered": true` adds a # column (1, 2, 3); `"numbered": "FR"` adds an ID column
(FR-01, FR-02 …) – use it for anything that is referred to elsewhere (requirements, tests, risks,
decisions). `"numbered": false` turns a preset's default numbering off.

`hide: ["example"]` drops a column; `labels: {...}` renames one (e.g. `"source": "שדה בדרישת OPS+"`).

**kv preset `interface`** — the interface card. Keys (any subset, printed in this order):
`name` שם הממשק · `service` שם השירות · `operation_id` · `description` · `source` מערכת מקור ·
`target` מערכת יעד / צרכן · `format` · `mode` אופן הפעלה · `frequency` · `architecture` · `method` ·
`endpoint` · `auth` אימות והרשאות. Extra rows: `"rows": [["label", "value"]]`.

## 7. text features

- `**bold**`, `` `code` `` (monospace, always LTR — use for field names, paths, values in prose).
- References: `{{sec:id}}` section number · `{{title:id}}` section title · `{{fig:id}}` figure number ·
  `{{tbl:id}}` table number · `{{name}}` a value from `vars`. Unknown ids fail the build.
- Write Hebrew naturally with English inside it — the builder isolates English runs so Word keeps their
  word order, attaches `C#`, `.NET`, `OPS+`, `12:A3:…`, `10MB` correctly, converts `"`/`'` inside
  Hebrew words to ״/׳, and turns ` - ` into ` – `.
- Never type bullets (•) or numbers ("1.") at the start of list items — the lists are real Word lists.

## 8. checks

```json
"checks": [
  { "type": "json_fields", "json": "resp_example", "table": "resp_fields", "root": "data[]", "require_all": true, "msg": "Response ↔ טבלה" }
]
```
Compares the keys of a JSON example (`code` block id) with the field-name column of a table (first
column, or `column`). Paths are compared without `[]`; a table row documents its sub-tree.
- A key in the JSON that is not in the table → **build error** (the classic "renamed in one place").
- `require_all: true` → table fields missing from the example are warnings; `"error"` → errors.
- `root`: only the part of the JSON under it (`"data[]"` for collection responses).
- `ignore`: `["_links", "pagination"]` — prefixes to skip.
Add one check for every pair of (example, field table): request body ↔ request table,
response ↔ response table, pagination ↔ pagination table.

## 9. language check and `spell_ignore`

`make_spec.py` lints every prose string before building (spelling with hspell, confusable words such as
תחולה/תכולה, gender agreement, register, AI-style phrases, translated technical terms) and stops on
errors. Client, project and author names are ignored automatically. A word that is correct but unknown
to the dictionary goes into the spec's top-level list:
```json
"spell_ignore": ["הקסדצימלי", "מנורמלות"]
```
Never add a word there to silence a real mistake.

## 10. errors you will see

The build stops (no file is written) and lists every problem with its location
(`סעיף 4 ("לוגיקה") בלוק 3 (table) שורה 2`). Typical ones: invalid JSON, unknown reference, duplicate
id, empty section, row length ≠ columns, unknown column key, JSON field not in table, changelog
version not increasing, image not found. Fix the spec — never weaken a check to make it pass.
Warnings (build succeeds) worth acting on: a diagram shrunk below 65% (unreadable), duplicate field
names in a table, typed bullets, TODO/XXX left in the text.
