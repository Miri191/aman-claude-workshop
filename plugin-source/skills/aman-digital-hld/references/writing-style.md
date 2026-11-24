# Writing style

An HLD is read by the client's management, product owners, IT, architects, the CISO and sometimes the
legal team — and it is often attached to the agreement. It must read like a senior system analyst and
project manager wrote it: correct, precise, short — never like generated text. Chapter 1 (vision,
principles, value) is business language, but still concrete: every bullet says something specific to
this client; a sentence that would fit any project is deleted. A single
wrong word ("תחולה" where "תכולה" was meant) undermines the whole document.

## 1. Language and terminology (Hebrew specs — the default)

Hebrew prose, with the technical vocabulary developers actually use **kept in English**. Never translate
a technical term into Hebrew that nobody says out loud.

**Stays in English** (as is, no translation, no transliteration):
API, Endpoint, Request, Response, Payload, Header, Query String, Path, Body, Token, JWT, OAuth, Scope,
Pagination, Limit / Offset, Webhook, Queue, Topic, Event, Retry, Timeout, Cache, Batch, Job, Cron,
Schema, Enum, Boolean, String, Integer, DateTime, Null / Nullable, JSON, XML, CSV, HTTP status codes,
GET / POST / PUT / PATCH / DELETE, CRUD, SDK, Swagger / OpenAPI, Logging, Monitoring, Alert, SLA, Rate
Limit, Idempotency, CDC, ETL, DB, PK / FK, Index, View, Stored Procedure, Migration, Deploy, Production /
Staging / Test, CI/CD, Feature Flag, Push Notification, Deep Link, Pop-up (or פופ־אפ), Drawer, Toggle,
Tab, CTA, Loader, Empty State, Error State, Onboarding, Analytics, field names, table and column names,
service names, product names.

**Natural Hebrew is right** for everyday concepts: ממשק, שירות, שרת, לקוח, משתמש, מסך, כפתור, שדה,
טבלה, רשומה, עמודה, בקשה / תשובה in running prose, הרשאה, אימות, הצפנה, שגיאה, סביבה, תהליך, תזכורת.

**Don't** write: נקודת קצה (→ Endpoint), אסימון (→ Token), עימוד (→ Pagination), מטען נתונים
(→ Payload), פסק זמן (→ Timeout), מטמון (→ Cache), סביבת ייצור (→ Production), קרס (→ Hook),
פריסה (→ Deploy). The language check flags these.

## 2. Hebrew that reads as written by a person

- **Short, concrete sentences.** One fact or rule per sentence. Subject → verb → object.
  ✗ "המערכת תאפשר ביצוע שליפה של נתוני ההזמנות באופן יעיל ומהיר"
  ✓ "השירות מחזיר את ההזמנות של המבוטח, ממוינות לפי תאריך."
- **Verbs, not nominalizations**: "לעדכן" not "לבצע עדכון"; "להשתמש" not "לעשות שימוש".
- **Impersonal, present tense**: "השירות מחזיר", "יש לסנן", "מוצגת הודעה". No "אנו", no "נבצע".
- **Rules start with the condition**: "אם התקבל `dateFrom` – …". State the default ("אם לא נשלח – LY").
- **No filler or marketing**: avoid "חשוב לציין", "יש לציין כי", "בצורה חלקה", "פתרון מקיף",
  "חוויית משתמש משופרת", "לא רק … אלא גם", "מגוון רחב של", "באופן אופטימלי", "ערך מוסף",
  "בנוסף לכך", "יתרה מכך". If a sentence still says the same without the phrase — delete the phrase.
- **Few dashes.** A dash per sentence at most. Three dashes in a paragraph is the most recognisable sign
  of generated text — split into sentences instead.
- **Not every bullet starts with "**כותרת:**"**. Use that pattern only for real definition lists.
- **Register**: "הוא/היא" not "הינו/הינה"; "אם" not "במידה ו"; "כדי" not "על מנת" / "בכדי";
  "מכיוון ש" not "לאור העובדה ש"; "דוגמה" not "דוגמא" (plural: דוגמאות).

## 3. Grammar checklist (read every sentence against it)

- **Gender agreement** between subject and verb / adjective — the most frequent error in generated
  Hebrew. מערכת, אפליקציה, טבלה, בקשה, תשובה, רשומה, הודעה, קריאה, פונקציה, שגיאה, רשימה, הזמנה,
  פוליסה → feminine ("המערכת מחזירה", "הטבלה מכילה"). ממשק, שירות, שרת, מסך, כפתור, שדה, קובץ, תהליך,
  רכיב, ערך → masculine ("הממשק מחזיר", "השדה מוצג").
- **Number agreement**: "הנתונים נשמרים", "השדות הבאים".
- **Construct state**: the article goes on the last noun – "תאריך היציאה", "שם השדה", not "התאריך יציאה".
- **Prepositions**: "תלוי ב…", "בהתאם ל…", "מתבסס על…", "שונה מ…".
- **Hebrew prefix before English / numbers**: ב־API, ל־Endpoint, מ־Arbitrip, כ־600,000 (maqaf or hyphen,
  no space).
- **Gershayim / geresh**: ע״י, סה״כ, מע״מ, צ׳ק־אין (typed `"` / `'` inside a word are converted).
- **Spelling (כתיב מלא per the Academy)**: עדכון, ארגון, שרשור, תעדוף, מסים, פונקציונלי, טבלה, סטטוס,
  פורמט, סטנדרט, אינטגרציה, קונפיגורציה.

### Confusable words — check every occurrence

| write | when you mean | not |
|---|---|---|
| **תכולה** (תכולת הפרויקט, מחוץ לתכולה) | scope, what is included | תחולה |
| **תחולה** (תאריך תחולה, תחולת הפוליסה) | applicability / effective date | תכולה |
| **תכנות** | programming | תכנון (= planning) |
| **הרשאה** | permission / authorization | הרשמה (= registration) |
| **אימות** | verification / authentication | אישור (= approval) |
| **מוצג** | displayed | מוצע (= offered) |
| **שליפה** | retrieval / fetch | שליחה (= sending) |
| **מסמך** / **מסך** | document / screen | – check you typed the one you mean |

## 4. Proofreading procedure (mandatory before every build)

1. Read every string in the spec JSON as an editor would: titles, paragraphs, table cells, captions,
   diagram labels, change-log text.
2. For each sentence ask: is it correct Hebrew (agreement, prepositions, construct state)? Is every word
   the one meant (confusables table)? Would a senior analyst write it this way, or does it sound generated?
3. Fix, then build. The build runs the automatic language check (spelling with hspell, confusable words,
   gender agreement, register, AI-style phrases, translated terms) and **stops on language errors**.
   A word that is correct but unknown to the dictionary (a product or client name, a new tech term) goes
   to `"spell_ignore"` in the spec – only after you are sure it is spelled right.
4. After the build, read two or three preview pages end to end as the reader will.

The automatic check is a net, not a substitute: it cannot judge meaning. Step 2 is where documents
become correct.

## 5. Author names

The change log and "נכתב ע״י" use **the document's language**: Hebrew names in a Hebrew spec
("מתן שרון", "צוות אפיון – אמן דיגיטל"), English names in an English spec. The author is the person
who requested the spec unless they name someone else; if their name isn't known, ask. The build fails on
a Latin-letter author in a Hebrew spec.

## 6. English HLDs

An HLD in English (only when the user asks) keeps the same chapters, translated, and this register:

- **Normative language (RFC 2119)**: MUST / MUST NOT for mandatory behaviour, SHOULD for recommended,
  MAY for optional. Use them in requirements and rules, not in descriptive text.
- **Traceable requirements** (when the HLD lists requirements): an ID (FR-01, NFR-01) and one testable statement
  with a measurable value ("within 3 seconds (p95)", not "fast"). Tests and risks refer to the IDs.
- **Present tense, active voice, third person**: "The webhook validates the body", not "The body will
  be validated by the webhook".
- **One term per concept**, defined once in "Definitions and acronyms"; acronyms expanded on first use.
- **Exact names in code style**: services, endpoints, tables, columns, fields, config keys, values.
- **Quantities with units and conditions**: "100 events in 5 minutes", "14 days after `RunTime`".
- **Decisions with rationale and rejected alternatives**; proposals labelled "Proposed" until approved;
  unknowns as "TBD" with an entry in Open issues.
- **No filler or marketing**: avoid seamless, robust, leverage, comprehensive, cutting-edge, streamline,
  utilize (→ use), in order to (→ to), facilitate, "it is important to note", "not only … but also".
- Sentence-case headings; dates in prose as "15 November 2026", ISO in examples.

## 7. Naming the file

`HLD_<לקוח>_<פרויקט>_v<גרסה>.docx`, e.g. `HLD_מנורה_אפליקציית_לקוחות_v1.0.docx`.
English: `HLD_<Client>_<Project>_v<version>.docx`. Underscores, no spaces, version = last change-log row.

## 8. What never goes into a spec

- Invented facts: endpoints, field names, table names, limits, SLAs, error codes, people. If the sources
  don't say it, it is an open issue (or a clearly labelled proposal).
- Prices, rates and effort estimates (those belong in a הצעת מחיר). Dates, phases and milestones do belong in the HLD.
- SLA times, response times and contractual commitments that are not in the agreement / quote — write
  "לפי ההסכם" and open an issue.
- People who are not named in the sources (team tables list only real names and roles).
- Credentials, real tokens, real personal data in examples – use obviously fake values.
