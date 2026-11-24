---
name: project-brief
description: Turns raw project material into an Aman Digital project brief (בריף). Use when the user asks for a brief, בריף, project brief or "תכין בריף", or pastes meeting notes, a transcript, a Teams thread, emails or an RFP and wants a structured starting point for a project, a proposal, an HLD or a Claude Code prototype.
---

# Project brief (בריף פרויקט)

Create a one-page Hebrew brief that the team can price, specify and build from.

## Steps
1. Read all source material. If it is a meeting transcript, summarize it first (topics, decisions, action items, open questions), then write the brief from the summary.
2. Separate what the client said from what is assumed. Never fill gaps with guesses: list them as open questions.
3. Write the brief in Hebrew, right-to-left, using the structure below.

## Structure
- **רקע:** who the client is and what triggered the project.
- **הבעיה:** the problem in the client's terms.
- **מטרות:** 2–4 measurable goals.
- **קהל יעד:** primary and secondary users.
- **היקף:** what is in scope (screens, flows, deliverables).
- **לא בהיקף:** explicit exclusions.
- **מגבלות:** technical, brand, accessibility, language (Hebrew RTL by default), deadlines.
- **הגדרת הצלחה:** what "done" looks like.
- **שאלות פתוחות:** everything that still needs the client's answer.

## Output
- In chat by default; as a Markdown file `brief.md` when the user is about to start a Claude Code project, so it can sit in the project folder.
- End with the open questions as a ready-to-send message to the client.
