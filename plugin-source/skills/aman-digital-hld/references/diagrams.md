# Diagrams

Diagrams are written in Mermaid inside the spec (`"type": "diagram"`) and rendered to PNG in the brand
colours by `render_diagrams.py` (called by `make_spec.py`). Hebrew labels are laid out right-to-left
automatically — English words, parentheses, `OPS+`, `C#`, a label that *starts* with an English word
("Bluetooth פעיל?") all land on the correct side.

## When to add a diagram

Add one when it saves the reader from reconstructing a picture in their head — not as decoration.

| situation | diagram |
|---|---|
| A calls B calls C (any interface, any integration) | `sequenceDiagram` |
| a user journey across screens / pop-ups | `flowchart TD` with section refs in the nodes |
| several systems, queues, databases | `flowchart TD` architecture (DBs as `[( )]`, queues as `[[ ]]`, external systems as `([ ])`, groups as `subgraph`) |
| an entity with statuses | `stateDiagram-v2` + a `states` table |
| 3+ related tables | `erDiagram` |
| a batch job with decisions | `flowchart TD` |

Typical counts in an HLD: one context map, one architecture, and one flow per business process in chapter 5
(BSI had ~15). Always give a `caption` and refer to it in the text
(`תרשים {{fig:arch}}`).

## Diagrams in an HLD

An HLD has three kinds, in this order of importance:

| where | diagram | how |
|---|---|---|
| 2.2 תרשים המערכות המשתתפות | context map | `flowchart TD`; the systems built in the project in one `subgraph`, every participating system as `(["name – role"])`, data stores as `[( )]`, a short label on every arrow saying what passes (`<-- "צבירה ופריקה" -->` for two-way). Same names as the `systems` table |
| chapter 5, each process | business process flow (BSI style) | `flowchart RL` for up to ~7 nodes in a row, `flowchart TD` beyond that; start / end as `([ ])`, decisions as `{ ? }` with כן / לא on the edges, a system step as `[(System – action)]` or with the system name in the node |
| 9.1 ארכיטקטורת הפתרון | architecture | the client's / architect's drawing as `image` when there is one (it carries vendor logos and network zones); otherwise `flowchart TD` with `subgraph`s per zone (WORLD, WAF, CLOUD, DATA, third parties) |

Many systems: a context map with more than ~10 systems is too wide for a page. Group them with
`subgraph`s (the client's systems / built in the project / third parties / infrastructure) and keep
one arrow per pair, or split into two maps (core flow, and supporting systems). The `systems` table
carries the full list; the map carries the relationships.

Mixed labels: in a Hebrew diagram a label that starts with English is still laid out right to left —
"Front Door ו־WAF" is drawn as "WAF־ו Front Door" when you scan it left to right, which is the correct
Hebrew reading order. A label that is mostly English reads better entirely in English ("Front Door + WAF").

Width and height: a page fits about 6 nodes across in `RL` and about 6 levels down in `TD` (diamonds are tall). A longer process is split into two flows (e.g. identification and payment / accrual) rather than shrunk.

The project schedule is a `schedule` **table**, not a Mermaid `gantt`: gantt has no right-to-left
support (Hebrew task names with English words come out reversed) and draws a "today" line.

## Rules that keep diagrams readable

- **Size**: keep the long axis ≤ ~8 nodes. The builder warns when a diagram has to shrink below 65% (labels would be under ~7pt) —
  then shorten labels, merge steps, or split into two diagrams. Don't just ignore the warning.
- **Direction**: `TD` by default. For a horizontal flow in a Hebrew doc use `RL` (reads right-to-left);
  in `stateDiagram-v2` use `direction RL` for Hebrew, `LR` for English.
- **Labels with special characters must be quoted**: `A["שליחה ל-API (POST)"]` – parentheses, brackets,
  braces, `|`, `#`, `;` inside an unquoted `[...]` are Mermaid syntax errors.
- **Line breaks** in a node: `<br/>`.
- **Decision diamonds** grow with their text – keep them to 2–4 words (`{JobRunTime מלא?}`) and explain
  the rest in the caption or the numbered steps.
- **Sequence diagrams**: ≤ 5 participants, short messages; `participant API as GetFlightsSchedule` to
  keep ids short; `alt / else / end` for error paths; `Note over A,B: ...`; don't use `autonumber`
  (the numbers collide with the labels).
- **Section references** inside diagrams: `סעיף {{sec:popup_offer}}` works (also `{{title:id}}` and
  `{{vars}}`). Mermaid hexagons `{{text}}` are left alone.
- **Colours / fonts**: don't set them per diagram; the theme in `assets/mermaid/config.json` applies.

## Snippets

```text
sequenceDiagram
    participant C as מערכת צרכנית (OPS+)
    participant API as GetFlightsSchedule
    participant DB as Master_Schedule
    C->>API: GET /v1/flights-schedule עם מסננים
    API->>API: אימות JWT וולידציה
    alt פרמטר לא חוקי
        API-->>C: 400 – Problem Details
    else תקין
        API->>DB: שליפה לפי הסינון
        DB-->>API: רשומות + totalCount
        API-->>C: 200 OK
    end
```

```text
flowchart TD
    A([כניסה לאפליקציה]) --> B[פופ-אפ הצעת חיבור – סעיף {{sec:popup_offer}}]
    B -- לא כרגע --> H([דף הבית])
    B -- המשך --> C{Bluetooth פעיל?}
    C -- לא --> D[פופ-אפ Bluetooth כבוי]
    D -- רענון --> C
    C -- כן --> E[(UpdateCarBluetooth)]
```

```text
stateDiagram-v2
    direction RL
    state "לא משויך" as N
    state "משויך" as P
    [*] --> N
    N --> P: בחירת התקן
    P --> N: הסרת שיוך
```

```text
erDiagram
    Hotels ||--o{ MainTourismBookings : "HotelId"
    MainTourismBookings ||--o{ PaymentMethods : "ReservationId"
    MainTourismBookings {
        NVARCHAR IdempotencyKey PK
        NVARCHAR HotelId FK
    }
```
Keep attributes only on the central tables of an ERD; the full columns go in the `db_table` tables.

## Trying a diagram on its own

```bash
python3 SKILL_DIR/scripts/render_diagrams.py --mmd diagram.mmd out.png   # then view out.png
```

## Screens and designs (images)

Use the user's uploaded screenshots (`/mnt/user-data/uploads/...`) with `"type": "image"`. Several
states of one screen side by side: `"paths": [...]`, `height_cm` 7.5–8, caption that names the states
in reading order ("מימין לשמאל: ..."). Don't redraw screens as diagrams.

## If rendering fails

- *Syntax error* — the message gives the diagram id, the line and a hint; fix the Mermaid.
- *No Chromium / mmdc* — `render_diagrams.py` looks for Chromium in the usual places; set
  `MERMAID_CHROME=/path/to/chrome` if it is elsewhere, or `npm i -g @mermaid-js/mermaid-cli` when mmdc is
  missing. If neither is possible in this environment, tell the user, and build without the diagram
  rather than drawing it some other way.
