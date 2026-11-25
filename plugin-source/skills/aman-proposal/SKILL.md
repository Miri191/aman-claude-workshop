---
name: aman-proposal
description: Writes Aman Digital price proposals (הצעת מחיר) in the house format. Use whenever the user asks for a price proposal, quote, הצעת מחיר, הצעה ללקוח or תמחור for a UX/UI, research or product project, including when they paste a client brief, RFP, meeting summary or Teams thread and say "תכין הצעה". Also use to update or re-price an existing Aman Digital proposal.
---

# Aman Digital price proposals (הצעות מחיר)

Produce a Hebrew, right-to-left Word proposal in Aman Digital's house format, ready for the user to review and send.

## Before writing
1. Read all source material (brief, RFP, meeting summary, emails). If a Microsoft 365 connector is available and the user points to a thread or email, read it there.
2. List open questions and assumptions first. Ask the user only about what blocks pricing (scope, deliverables, deadlines); mark the rest as assumptions in the document.
3. Never invent client facts, names or numbers. Use bracketed placeholders such as [שם הלקוח] for anything not given.

## Bundled files
- `assets/proposal-template.docx`: the house template. Build the proposal from it: same chapters, same order, same styling. Fill the bracketed placeholders; keep a placeholder in brackets when the information is missing.
- `assets/commercial-terms.md`: rate, VAT and payment terms. Use it as the source for pricing and terms, and flag any line still marked [להשלים].

## Structure
1. Cover: client name, project name, date, "אמן דיגיטל | סטודיו UX/UI".
2. רקע ומטרות: the client's need in their words, and what success looks like.
3. היקף העבודה: deliverables per phase; component-level detail and edge cases where the scope needs it.
4. מה לא כלול בהצעה: explicit exclusions.
5. שלבים ולוחות זמנים: phases with durations.
6. טבלת שעות: rows per phase or deliverable, hours per row, subtotal per phase, total hours.
7. תמחור: hours × rate; total before VAT, VAT stated separately.
8. תנאים מסחריים: payment terms, validity, change requests.
9. הנחות ושאלות פתוחות: everything assumed while pricing.

## Commercial defaults
Take them from `assets/commercial-terms.md`. Confirm with the user if the brief suggests otherwise.

## Format
- Word document (.docx), Hebrew, right-to-left, right-aligned.
- Font: Google Sans for all text. Hebrew glyphs fall back to a Hebrew font if Google Sans has none; say so to the user once.
- Colors: navy #1F3864 for headings, #1F4E79 for secondary headings and table header fills.
- Tables right-to-left, numbers aligned consistently, totals in bold.
- File name: הצעת מחיר - [לקוח] - [פרויקט] - [תאריך].docx

## After writing
Give the user a short summary: total hours, total price before VAT, and the list of assumptions to check before sending. Hours and prices always need a human review.
