# HLD structure — chapter order, what goes in each chapter, completeness checklist

The house HLD follows the department's **BSI / Extra+ HLD (October 2023)**, which is the reference
document. The Menora and Horizon HLDs add a few chapters (users and permissions, project assumptions,
screen and interface index, agreement ↔ HLD comparison). Eight more chapters that are standard in an
HLD were added at the department's request: glossary, non-functional requirements, environments and
DevOps, testing and acceptance, data migration, go-live, support and SLA, privacy and regulation, and
architecture decisions and alternatives.

Keep the chapter **names** below exactly — the same names in every HLD is what makes them uniform. The
order is fixed; chapters marked *(optional)* are included only when the project needs them, and the
clarifying questions (SKILL.md step 2) decide which. Never leave an empty chapter: what is not known yet
goes to the open-issues table of chapter 1 with an owner.

`doc_type` is "מסמך HLD" (default). Title: the project / product name ("מועדון Extra+"), `client`: the
client's name, `subtitle`: one line on what is being built.

---

## 1. יעדים ומטרות

The business picture. Written for the client's management as much as for IT: concrete, no slogans.

| sub-section | content | blocks |
|---|---|---|
| 1.1 **כללי** | who the client is (2–3 sentences: group, size, field), what they want to build and why, for whom, on which channels | `p` × 2–3 |
| 1.2 **תפיסת החזון** | the vision in one line (`sub` with the vision's name in quotes) and 4–7 bullets that explain it | `sub` + `bullets` (bold lead + one sentence) |
| 1.3 **עקרונות מנחים עיקריים** | the principles that steer design decisions: channel strategy, single source of truth, identity, data, security | `bullets` |
| 1.4 **הצעת ערך ללקוח** | what the end customer gains, one bullet per benefit | `bullets` |
| 1.5 *(optional)* domain value chapter | a second stakeholder's value, e.g. "תפיסת בית העסק כמכפיל כוח" in a loyalty club, "הצעת ערך לסוכן" in insurance | `bullets` |
| 1.6 **קהלי יעד עיקריים** | each audience with its size when known; who is explicitly *not* a target in this phase | `bullets` with `sub` |
| 1.7 *(optional)* **בעיות במצב הקיים** | 1.7.1 בעיות שהמערכת תפתור · 1.7.2 בעיות שהמערכת לא תפתור | `bullets` |
| 1.8 *(optional)* **מדדי הצלחה** | measurable KPIs with a target | `table` preset `kpis` |
| 1.9 **מילון מונחים** | every domain word and acronym used in the document (NBA, BFF, CDC, כרטיס נטען…) | `table` preset `glossary` |
| 1.10 **מסמכים ומקורות** | what this HLD is based on: RFP / requirements document, agreement or quote, meeting summaries, architecture documents, Figma. Status בשימוש / חלקי / חסר | `table` preset `sources` + `callout warning` when something is missing |
| 1.11 **נושאים פתוחים, סיכונים ותלויות** | decisions the client still owes, dependencies on third parties, with owner and status | `table` preset `open_issues` |

## 2. תיחום

"פרק זה מתאר את המערכות המשתתפות ומה מתבצע בכל אחת מהן."

| sub-section | content | blocks |
|---|---|---|
| 2.1 **רשימת המערכות המשתתפות** | every system in the solution, grouped (`group` rows): systems of the client, systems built in this project, third parties, infrastructure, DevOps. "טרם נבחר" where a vendor isn't chosen | `table` preset `systems` (numbered) |
| 2.2 **תרשים המערכות המשתתפות** | context diagram: the new system in the middle, every participating system around it, one word per arrow (what passes) | `diagram` `flowchart` + caption |
| 2.3 **מיפוי תהליכי העבודה בחלוקה למערכות** | **mandatory whenever more than one system takes part — including adjacent systems (מערכות משיקות) that the project only connects to.** For each system, which business processes touch it and what exactly happens there (identify the customer, calculate accrual, issue the card, store the document…), who owns that system's part, and whether that part is in the project's scope. This is what draws the project's boundary: everything with "בתכולת הפרויקט: לא" is someone else's work that the project depends on, and it must match the responsibility sub-sections below and chapter 7 | `table` preset `process_map`, one `group` row per system (systems built in the project first, then the client's, then third parties); optionally a matrix with a column per system (explicit `columns`, ✓ in the cells) when there are ≤ 6 systems and the reader needs the overview |
| 2.4 **מודולים מרכזיים** | the "shopping list" of functionality by module (BSI: "רשימת מכולת של פונקציונליות") — module as bold item, features as sub-items | `bullets` with `sub` |
| 2.5 **נושאים באחריות אמן** | what Aman delivers: discovery, UX/UI, development, integration, QA, project management, handover of code and documents | `bullets` with `sub` |
| 2.6 **נושאים באחריות \<הלקוח\>** | decision makers, approvals, APIs on the client's side, environments, test data, third-party licences and contracts, PT, store accounts | `bullets` with `sub` |
| 2.7 … **נושאים באחריות \<מערכת / ספק\>** | one sub-section per third party that owns part of the flow (credit company, POS, loyalty / CDC, CRM…) | `bullets` with `sub` |
| 2.8 **מחוץ לתכולה** | what is explicitly not in this project or phase, and what moves to phase 2 | `bullets` |

Responsibility starter texts: `boilerplate.md` §3.

## 3. משתמשים והרשאות *(optional — when there are internal users, roles or a back office)*

3.1 **אופן ההזדהות** (Azure AD / SSO / OTP / biometrics, strong authentication for sensitive actions) ·
3.2 **סוגי משתמשים והרשאות** — `user_roles` (role, number of users, actions, no access) ·
3.3 *(optional)* **ניהול תפקידים והרשאות** — where permissions are managed, the role hierarchy.

## 4. הנחות יסוד לפרויקט

The commercial-technical assumptions the plan and the price rest on. Start from `boilerplate.md` §2,
keep only what applies, put the client's name in, and take every number (response times, environments,
deadlines) from the agreement / quote when there is one. `numbered`, grouped by `sub`: כללי · ממשקים
ואינטגרציה · סביבות ותשתיות · אבטחת מידע · ניהול שינויים · זמני תגובה הדדיים.

## 5. פירוט דרישות

The heart of the HLD. One sub-section per business area / module, in the order the customer meets
them (BSI: רישום למועדון → פעולות באפליקציה → תהליכי רכישה → צבירה → פריקה → התחשבנות → צפייה בנקודות
→ מבצעים → פוש → עדכון פרטים → Back office). In each:

- one or two sentences on what the process does and who starts it;
- **a process flow** (`diagram` `flowchart RL`, decisions as diamonds, yes / no on the edges, systems
  named in the nodes) whenever there is a decision or more than one system — this is what makes an HLD
  an HLD;
- `sub` "פונקציונליות נדרשת" + `bullets`;
- variants as sub-sub-sections (onboarding for an admin / a family member / a prepaid card);
- a scenario table when the same event looks different to each party (BSI "תהליכי התחשבנות": what the
  customer / the business / the club / the credit company sees) — explicit `columns`;
- `callout open` for what still needs a decision, `callout note` for "יאופיין בהמשך".

Last sub-section: **דרישות מערכת Back Office** (CMS, content, coupons, campaigns, reports) when there is one.

## 6. מסכים וחבילות עבודה *(optional — when screens / phases are part of the HLD)*

6.1 **חבילות עבודה** — `work_packages` (package, dates, contents as a list, milestone) ·
6.2 **היררכיית מסכים** — `bullets` by area, each screen with "– MVP" / "– Web View" / "– שלב ב׳" ·
6.3 **אינדקס מסכים וממשקים** — `screen_index` (package, screen, process / component, system, interface,
interface name; "טרם הוגדר" when the service name is unknown) ·
6.4 **ארכיטקטורת מידע** (diagram or image) · 6.5 **קונספט UX** (Figma link in a `p`, key screens as `image`).

## 7. ממשקים ונתונים

What passes between the new system and each participating system, at HLD level (no field lists — those
belong in the interface specs). BSI: "דאטה מחברת האשראי" / "דאטה אל חברת האשראי" / "דאטה וממשקים
מהרשתות ואל הרשתות".

7.1 **עקרונות אינטגרציה** — gateway, authentication between systems, sync vs. async, file transfers,
monitoring of interfaces, who exposes and who consumes (`bullets`) ·
7.2 … one sub-section per counterpart: `data_flows` table (data, from, to, mode: Online API / קובץ /
Event / SSO, frequency, notes). Unknown mode or frequency → "לאפיון" + an open issue.

## 8. דרישות לא פונקציונליות

`nfr` table, one row per topic: משתמשים ונפחים (users, concurrent users, transactions per day / peak) ·
ביצועים (response time, p95) · זמינות (hours, uptime) · יכולת גדילה · נגישות (ת״י 5568 / WCAG 2.0 AA) ·
דפדפנים ומכשירים (iOS / Android versions) · שפות וכיווניות · תיעוד ו־Audit · גיבוי ושחזור (RPO / RTO).
A number that the sources don't give is written "לקבוע עם \<הלקוח\>" and listed as an open issue —
never a made-up figure.

## 9. תשתיות וארכיטקטורה

9.1 **ארכיטקטורת הפתרון** — a paragraph per layer (client, edge / WAF, BFF / services, data, integration),
the architecture diagram (the client's drawing as `image`, or a Mermaid `flowchart TD` with `subgraph`s),
and a `components` table ·
9.2 **החלטות ארכיטקטורה וחלופות** — `decisions` (decision, rationale, alternatives considered), e.g.
Low-code vs. code, React Native vs. native, cloud provider, identity product. A decision that is not
taken yet is a row marked "המלצה – לאישור" plus an open issue ·
9.3 **סביבות** — `hld_environments` (DEV / TEST / UAT / PROD: purpose, hosting, owner, data) ·
9.4 **DevOps ו־CI/CD** — source control, pipelines, code scanning, release flow, store publishing
(`bullets`; starter text `boilerplate.md` §5).

## 10. אבטחת מידע

The nine standard sub-sections, in this order (texts: `boilerplate.md` §1; adapt to the client's cloud,
identity product and CISO guidelines; drop a sub-section only if it truly does not apply, e.g. no file
uploads → no הלבנת קבצים):

10.1 נהלי אבטחת מידע – אפליקטיבית · 10.2 ניהול מרכזי של זהויות והרשאות · 10.3 הצפנת מידע ·
10.4 אבטחת תשתיות התקשורת · 10.5 הלבנת קבצים · 10.6 אבטחת ממשקי API · 10.7 אבטחת מידע – תשתיות ·
10.8 ניטור, שליטה ובקרה · 10.9 אבטחת מידע – אבטחת מתקן הפיתוח

## 11. פרטיות ורגולציה

Personal data processed (`bullets` by type) · data owner and processor (the client owns the database;
Aman processes it on its behalf) · retention and deletion · consents (privacy policy, marketing
consent, information sharing within a group) · the regulation that applies (`nfr` table: topic,
requirement, notes) — starter list in `boilerplate.md` §6. Legal wording is confirmed by the client's
legal / privacy officer: say so in a `callout note`.

## 12. מיגרציית נתונים *(optional — when replacing a system or loading existing data)*

What moves (`migration`: entity, source, volume, method, owner) · cleansing and mapping rules ·
dry runs and reconciliation · cutover window and freeze · rollback. If the existing data has not been
seen yet, say so (`callout warning`) and plan the mapping as a deliverable.

## 13. אסטרטגיית בדיקות וקבלה

`test_levels` (unit, integration, system QA, UAT, performance, accessibility, PT) with owner,
environment and exit criteria · defect severities used in acceptance · who signs off. Starter:
`boilerplate.md` §4.

## 14. הטמעה ועלייה לאוויר

Rollout strategy (pilot / gradual / big bang) · go-live checklist · training and guides · store
submission (apps) · hypercare period after go-live. `numbered` steps; dates belong in chapter 16.

## 15. תמיכה, תחזוקה ו־SLA

Support model (first line – \<client\> / Aman, second line – Aman / the product vendor) · channels
and hours · `sla` table (severity, definition, response, resolution) · warranty period · maintenance
and version upgrades. Every SLA number comes from the agreement or quote; without one, write the
structure with "לפי ההסכם" and open an issue. Starter: `boilerplate.md` §7.

## 16. תכנית עבודה

16.1 **ניהול סיכונים** — `risks` (risk, impact, likelihood, mitigation) ·
16.2 **מבנה ניהול הפרויקט** — `governance` (forum, chaired by, members, purpose, frequency: היגוי
עליונה / היגוי / צוותי משנה) ·
16.3 **צוות הפרויקט** — `team` per side (name, role, organization, responsibility); only people named in
the sources ·
16.4 **לו״ז ואבני דרך** — `schedule` (task, owner, start, end, deliverable), milestones marked
"אבן דרך:" in the task text; an optional `gantt` diagram for ≤ 12 tasks.

## 17. נספחים *(optional)*

17.1 **השוואה בין מסמך הדרישות ל־HLD** — `traceability`: every section of the requirements document /
agreement → the HLD section that answers it (`{{sec:id}}`), "לא נכלל – ראה {{sec:out_of_scope}}" when
it is out of scope ·
17.2 **דרישות שאינן בתכולה – שלב ב׳** — `bullets` or `requirements` table.

---

## Completeness checklist (go through it before building)

**Business**: why the client is doing this · vision and principles · who the customers are and who is
not in this phase · what the system will and will not solve · KPIs if the client gave any.

**Scope**: every participating system appears in 2.1 *and* in the diagram 2.2 *and* in the process mapping 2.3 *and* in chapter 7 · every process in chapter 5 appears in 2.3 under each system it touches · every row in 2.3 with "בתכולת הפרויקט: לא" has an owner who also appears in the responsibility sub-sections ·
every system has a responsibility sub-section or is covered by the client's one · out of scope stated ·
phase 2 items listed.

**Requirements**: every module in 2.3 has a sub-section in chapter 5 (or is explicitly deferred) ·
every process with a decision or more than one system has a flow · every flow names the systems
involved · back office covered.

**Integration**: every arrow in 2.2 is a row in chapter 7 · each row says who exposes and who
consumes · authentication between systems stated.

**Non-functional & architecture**: every NFR has a number or an open issue · every architecture
decision has a rationale and the rejected alternative · environments listed with owner.

**Security & privacy**: all nine security sub-sections adapted to this client (cloud, identity
product, CISO) · personal data types listed · data owner stated · regulation relevant to the client's
industry listed.

**Delivery**: test levels with owners · acceptance sign-off · go-live steps · support model and SLA
from the agreement · risks with mitigation · steering forums · schedule with milestones.

**Consistency**: the same system has the same name everywhere (table, diagrams, flows, chapter 7) ·
numbers that appear twice agree (users, dates, environments, response times) · the version on the
title page is the last change-log row · every "ראה סעיף" is a `{{sec:id}}` reference.
