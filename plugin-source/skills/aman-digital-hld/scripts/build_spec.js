#!/usr/bin/env node
/**
 * build_spec.js — Aman Digital HLD builder (מסמך HLD), on the aman-tech-spec engine
 *
 *   node build_spec.js <spec.json> <out.docx> [--diagrams manifest.json] [--pages pages.json]
 *                      [--info info.json] [--brand brand.json]
 *
 * Normally called by make_spec.py (which renders the diagrams, computes TOC page numbers and runs QA).
 *
 * - Hebrew specs (meta.lang "he"): every paragraph right-to-left, tables in RTL column order, Hebrew runs
 *   marked RTL and English runs isolated as LTR so Word keeps English word order. Code is always LTR.
 * - English specs (meta.lang "en"): everything left-to-right; Hebrew fragments become RTL runs.
 * - Section / figure / table numbers and cross references ({{sec:id}}, {{fig:id}}, {{tbl:id}}) are computed.
 * - JSON examples are validated; `checks` compare JSON examples with field tables.
 * - Exit code 1 on any error; nothing is written in that case.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  AlignmentType, Header, Footer, ImageRun, PageNumber, VerticalAlign, LevelFormat, TableLayoutType,
  HeadingLevel, Bookmark, InternalHyperlink, Tab, TabStopType,
} = require('docx');

// ───────────────────────────── CLI ─────────────────────────────
const argv = process.argv.slice(2);
const opt = (n) => { const i = argv.indexOf(n); return i > -1 ? argv[i + 1] : undefined; };
const positional = argv.filter((a, i) => !a.startsWith('--') && !(i > 0 && argv[i - 1].startsWith('--')));
if (positional.length < 2) {
  console.error('Usage: node build_spec.js <spec.json> <out.docx> [--diagrams manifest.json] [--pages pages.json] [--info info.json]');
  process.exit(2);
}
const [specPath, outPath] = positional;
const SPEC_DIR = path.dirname(path.resolve(specPath));
const SKILL_DIR = path.resolve(__dirname, '..');
const brandPath = opt('--brand') || path.join(SKILL_DIR, 'assets', 'brand.json');
const BRAND = JSON.parse(fs.readFileSync(brandPath, 'utf8'));
const C = BRAND.colors;
const FONT = BRAND.font || 'Arial';
const CODE_FONT = BRAND.code_font || 'Consolas';
const MANIFEST = opt('--diagrams') ? JSON.parse(fs.readFileSync(opt('--diagrams'), 'utf8')) : null;
const PAGES = opt('--pages') ? JSON.parse(fs.readFileSync(opt('--pages'), 'utf8')) : null;
const INFO_OUT = opt('--info');

// jszip ships with docx (it is a dependency of it) but its folder moves between environments
// (nested under docx/node_modules or hoisted next to it) — resolve it from docx's own location.
function loadJSZip() {
  const docxDir = path.dirname(require.resolve('docx'));
  const tries = [
    () => require(require.resolve('jszip', { paths: [docxDir] })),
    () => require('jszip'),
    () => require(path.join(docxDir, '..', 'node_modules', 'jszip')),
  ];
  for (const t of tries) { try { return t(); } catch (e) { /* next */ } }
  return null;
}
const JSZIP = loadJSZip();

class SpecError extends Error {}
const errors = [];
const warnings = [];

// ───────────────────────────── i18n ─────────────────────────────
const I18N = {
  he: {
    doc_type: 'מסמך HLD', toc: 'תוכן עניינים', changelog: 'מעקב שינויים', version: 'גרסה', date: 'תאריך',
    author: 'מחבר/ת', change: 'תיאור השינוי', client: 'לקוח', project: 'פרויקט', authors: 'נכתב ע״י',
    status: 'סטטוס', figure: 'תרשים', table: 'טבלה', page: 'עמוד', of: 'מתוך', yes: 'כן', no: 'לא',
    callout: { note: 'הערה', info: 'לידיעה', warning: 'שים לב', decision: 'החלטה', open: 'סוגיה פתוחה' },
  },
  en: {
    doc_type: 'High-Level Design (HLD)', toc: 'Table of Contents', changelog: 'Revision History', version: 'Version',
    date: 'Date', author: 'Author', change: 'Description of change', client: 'Client', project: 'Project',
    authors: 'Prepared by', status: 'Status', figure: 'Figure', table: 'Table', page: 'Page', of: 'of', yes: 'Yes',
    no: 'No', callout: { note: 'Note', info: 'FYI', warning: 'Important', decision: 'Decision', open: 'Open issue' },
  },
};

// Column presets: [key, he label, en label, width weight, flags]
const PRESETS = {
  glossary: [['term', 'מונח', 'Term', 1.1, { bold: true }], ['desc', 'הסבר', 'Definition', 3.4]],
  screen_components: [['field', 'שדה', 'Element', 1.1, { bold: true }], ['desc', 'תיאור רכיב', 'Description', 2.5],
    ['type', 'סוג רכיב', 'Type', 0.95], ['source', 'מקור נתונים', 'Data source', 1], ['notes', 'הערות', 'Notes', 2.2]],
  api_request: [['name', 'שם השדה', 'Field', 1.6, { code: true }], ['desc', 'תיאור', 'Description', 1.55],
    ['type', 'סוג', 'Type', 0.95], ['req', 'חובה', 'Required', 0.95, { center: true }],
    ['example', 'דוגמה', 'Example', 1.3, { code: true }], ['notes', 'הערות', 'Notes', 2.1]],
  api_response: [['name', 'שם השדה', 'Field', 2.75, { code: true }], ['desc', 'תיאור', 'Description', 1.55],
    ['type', 'סוג', 'Type', 0.95], ['example', 'דוגמה', 'Example', 1.2, { code: true }],
    ['notes', 'מקור נתונים / הערות', 'Source / notes', 1.85]],
  db_table: [['name', 'שם השדה', 'Column', 1.5, { code: true }], ['type', 'סוג נתונים', 'Data type', 1.2, { code: true }],
    ['req', 'חובה', 'Required', 0.95, { center: true }], ['key', 'מפתח', 'Key', 0.6, { center: true }],
    ['desc', 'תיאור', 'Description', 1.9], ['notes', 'הערות', 'Notes', 2]],
  errors: [['code', 'קוד', 'Code', 0.7, { code: true, center: true }], ['desc', 'תיאור', 'Description', 1.6],
    ['when', 'מתי מוחזר', 'When returned', 2], ['action', 'פעולה מומלצת', 'Recommended action', 2]],
  mapping: [['source', 'שדה מקור', 'Source field', 1.7, { code: true }], ['target', 'שדה יעד', 'Target field', 1.7, { code: true }],
    ['notes', 'הערות / המרה', 'Notes / transformation', 2.4]],
  params: [['name', 'שם הפרמטר', 'Parameter', 1.4, { code: true }], ['value', 'ערך', 'Value', 3]],
  environments: [['env', 'סביבה', 'Environment', 1], ['url', 'כתובת', 'URL', 3.4, { code: true }]],
  open_issues: [['issue', 'סוגיה', 'Issue', 3.4], ['owner', 'באחריות', 'Owner', 1], ['status', 'סטטוס', 'Status', 0.9]],
  nfr: [['topic', 'נושא', 'Topic', 1.2, { bold: true }], ['requirement', 'דרישה', 'Requirement', 2.6], ['notes', 'הערות', 'Notes', 1.6]],
  states: [['state', 'מצב', 'State', 1.1, { bold: true }], ['condition', 'תנאי', 'Condition', 2], ['behavior', 'תצוגה / התנהגות', 'Display / behavior', 2.4]],
  test_cases: [['scenario', 'תרחיש', 'Scenario', 2], ['steps', 'צעדים', 'Steps', 2.3], ['expected', 'תוצאה צפויה', 'Expected result', 2]],
  requirements: [['requirement', 'דרישה', 'Requirement', 3.8], ['priority', 'עדיפות', 'Priority', 0.85, { center: true }], ['source', 'מקור / הערות', 'Source / notes', 1.7]],
  components: [['component', 'רכיב', 'Component', 1.3, { bold: true }], ['responsibility', 'אחריות', 'Responsibility', 2.7], ['technology', 'טכנולוגיה', 'Technology', 1.2], ['owner', 'באחריות', 'Owner', 1]],
  config: [['key', 'מפתח', 'Key', 1.7, { code: true }], ['type', 'סוג', 'Type', 0.8], ['default', 'ברירת מחדל', 'Default', 1.1, { code: true }], ['desc', 'תיאור', 'Description', 2.6]],
  monitoring: [['signal', 'מדד / אירוע', 'Signal', 1.6], ['condition', 'תנאי / סף', 'Condition / threshold', 1.6], ['severity', 'חומרה', 'Severity', 0.8, { center: true }], ['action', 'פעולה', 'Action', 2.1]],
  risks: [['risk', 'סיכון', 'Risk', 2.5], ['impact', 'השפעה', 'Impact', 0.8, { center: true }], ['likelihood', 'סבירות', 'Likelihood', 0.9, { center: true }], ['mitigation', 'דרך התמודדות', 'Mitigation', 2.4]],
  decisions: [['decision', 'החלטה', 'Decision', 2.1], ['rationale', 'נימוק', 'Rationale', 2.3], ['alternatives', 'חלופות שנבחנו', 'Alternatives considered', 1.8]],
  events: [['event', 'אירוע', 'Event', 1.5, { code: true }], ['producer', 'מפיק', 'Producer', 1.1], ['consumer', 'צרכן', 'Consumer', 1.1], ['notes', 'תוכן / הערות', 'Payload / notes', 2.4]],
  error_handling: [['failure', 'כשל', 'Failure', 1.8], ['detection', 'זיהוי', 'Detection', 1.4], ['handling', 'טיפול', 'Handling', 2.3], ['retry', 'Retry', 'Retry', 1.2]],
  sources: [['source', 'מקור', 'Source', 2.3], ['status', 'סטטוס', 'Status', 0.9], ['notes', 'הערות', 'Notes', 2.4]],
  // ── HLD presets ──
  systems: [['system', 'מערכת', 'System', 1.7, { bold: true }], ['product', 'מוצר / טכנולוגיה', 'Product / technology', 1.6],
    ['vendor', 'חברה / ספק', 'Vendor', 1.2], ['role', 'תפקיד בפתרון', 'Role in the solution', 2.2]],
  process_map: [['process', 'תהליך', 'Process', 1.5, { bold: true }], ['activity', 'מה מתבצע במערכת', 'What happens in the system', 2.8],
    ['owner', 'באחריות', 'Owner', 0.9], ['scope', 'בתכולת הפרויקט', 'In project scope', 0.85, { center: true }]],
  user_roles: [['role', 'סוג משתמש / תפקיד', 'User type / role', 1.3, { bold: true }], ['count', 'מס׳ משתמשים', 'Users', 0.75, { center: true }],
    ['permissions', 'פעולות והרשאות', 'Actions and permissions', 2.6], ['restrictions', 'ללא גישה', 'No access', 1.8]],
  kpis: [['kpi', 'מדד', 'KPI', 2], ['target', 'יעד', 'Target', 1.1], ['measure', 'אופן מדידה', 'How measured', 2.2]],
  data_flows: [['data', 'נתונים / ממשק', 'Data / interface', 2.2], ['from', 'ממערכת', 'From', 1.1], ['to', 'למערכת', 'To', 1.1],
    ['mode', 'אופן העברה', 'Mode', 1.1], ['frequency', 'תדירות', 'Frequency', 0.9], ['notes', 'הערות', 'Notes', 1.6]],
  screen_index: [['package', 'חבילה', 'Package', 0.6, { center: true }], ['screen', 'מסך', 'Screen', 1.2, { bold: true }],
    ['process', 'תהליך / רכיב במסך', 'Process / component', 1.7], ['system', 'מערכת', 'System', 0.9],
    ['interface', 'ממשק', 'Interface', 1.6], ['interface_name', 'שם ממשק', 'Interface name', 1.4, { code: true }]],
  work_packages: [['package', 'חבילה', 'Package', 0.7, { center: true, bold: true }], ['dates', 'מועדים', 'Dates', 1.1],
    ['contents', 'תכולה', 'Contents', 3.6], ['milestone', 'תוצר / אבן דרך', 'Deliverable / milestone', 1.5]],
  schedule: [['task', 'משימה / שלב', 'Task / phase', 2.3], ['owner', 'באחריות', 'Owner', 0.9], ['start', 'התחלה', 'Start', 0.85, { center: true }],
    ['end', 'סיום', 'End', 0.85, { center: true }], ['deliverable', 'תוצר', 'Deliverable', 1.8]],
  governance: [['forum', 'פורום', 'Forum', 1.1, { bold: true }], ['lead', 'בראשות', 'Chaired by', 1.2], ['members', 'משתתפים', 'Members', 1.9],
    ['purpose', 'מטרה', 'Purpose', 1.8], ['frequency', 'תדירות', 'Frequency', 1]],
  team: [['name', 'שם', 'Name', 1.2, { bold: true }], ['role', 'תפקיד בפרויקט', 'Project role', 2], ['org', 'ארגון', 'Organization', 1],
    ['notes', 'אחריות עיקרית', 'Main responsibility', 2.2]],
  traceability: [['req_ref', 'סעיף במסמך הדרישות / בהסכם', 'Requirement / agreement section', 2.6], ['hld_ref', 'סעיף ב־HLD', 'HLD section', 1.6],
    ['notes', 'הערות', 'Notes', 1.6]],
  hld_environments: [['env', 'סביבה', 'Environment', 0.9, { bold: true }], ['purpose', 'ייעוד', 'Purpose', 1.9], ['hosting', 'תשתית / אירוח', 'Hosting', 1.6],
    ['owner', 'באחריות', 'Owner', 1], ['data', 'נתונים', 'Data', 1.3]],
  test_levels: [['level', 'סוג בדיקה', 'Test level', 1.2, { bold: true }], ['scope', 'מה נבדק', 'Scope', 2.2], ['owner', 'באחריות', 'Owner', 0.9],
    ['env', 'סביבה', 'Environment', 0.8, { center: true }], ['exit', 'תנאי סיום', 'Exit criteria', 1.9]],
  sla: [['severity', 'חומרה', 'Severity', 0.9, { bold: true }], ['definition', 'הגדרה', 'Definition', 2.6], ['response', 'זמן תגובה', 'Response time', 1, { center: true }],
    ['resolution', 'זמן פתרון / עקיפה', 'Resolution / workaround', 1.2, { center: true }]],
  migration: [['entity', 'נתונים / ישות', 'Data / entity', 1.5, { bold: true }], ['source', 'מערכת מקור', 'Source', 1.1], ['volume', 'היקף', 'Volume', 0.9, { center: true }],
    ['method', 'אופן ההסבה', 'Method', 2], ['owner', 'באחריות', 'Owner', 1]],
};
// presets that number their rows: true → 1, 2, 3 · "FR" → FR-01, FR-02 (traceable IDs)
const PRESET_NUMBERED = { open_issues: true, test_cases: 'TC', requirements: 'REQ', risks: 'R', decisions: 'D', systems: true, schedule: true, data_flows: true };
const KV_PRESETS = {
  interface: [
    ['name', 'שם הממשק', 'Interface name'], ['service', 'שם השירות', 'Service name', true],
    ['operation_id', 'operationId', 'operationId', true], ['description', 'תיאור', 'Description'],
    ['source', 'מערכת מקור', 'Source system'], ['target', 'מערכת יעד / צרכן', 'Target / consumer'],
    ['format', 'פורמט', 'Format'], ['mode', 'אופן הפעלה', 'Invocation'], ['frequency', 'תדירות', 'Frequency'],
    ['architecture', 'ארכיטקטורה', 'Architecture'], ['method', 'סוג בקשה', 'HTTP method', true],
    ['endpoint', 'Endpoint', 'Endpoint', true], ['auth', 'אימות והרשאות', 'Authentication'],
  ],
};

// ───────────────────────────── load spec ─────────────────────────────
let spec;
try { spec = JSON.parse(fs.readFileSync(specPath, 'utf8')); } catch (e) { fail(new SpecError(`קובץ ה־spec אינו JSON תקין: ${e.message}`)); }
const meta = spec.meta || {};
const LANG = meta.lang || 'he';
if (!I18N[LANG]) fail(new SpecError(`meta.lang חייב להיות "he" או "en" (התקבל "${LANG}")`));
const RTL = LANG === 'he';
const T = I18N[LANG];
const VARS = Object.assign({}, spec.vars || {});

// ───────────────────────────── text & bidi ─────────────────────────────
const LRM = '\u200E';
const isHeb = (ch) => /[\u0590-\u05FF\uFB1D-\uFB4F]/.test(ch);
const isLat = (ch) => /[A-Za-z\u00C0-\u024F]/.test(ch);
const isDig = (ch) => /[0-9]/.test(ch);
const TRAIL_ATTACHED = /[+#%*°™®]/;

// Hebrew typography: gershayim/geresh, spaced dashes, double spaces.
function normalizeHe(s) {
  return String(s)
    .replace(/([\u05D0-\u05EA])"(?=[\u05D0-\u05EA])/g, '$1״')
    .replace(/([\u05D0-\u05EA])'(?=[\u05D0-\u05EA])/g, '$1׳')
    .replace(/([\u05D0-\u05EA])'(?=[\s,.;:)\]]|$)/g, '$1׳')
    .replace(/\s--?\s/g, ' – ')
    .replace(/(\S) -(?=[^\s\-\d])/g, '$1 – ')
    .replace(/ {2,}/g, ' ');
}
const normalizeEn = (s) => String(s).replace(/\s--\s/g, ' – ').replace(/ {2,}/g, ' ');

// RTL paragraph: Hebrew segments rtl; Latin segments (incl. inner spaces/digits/punctuation) stay LTR
// so Word never reverses English word order inside Hebrew text. (Same engine as aman-price-quote.)
function splitBidi(text) {
  const chars = Array.from(text);
  const segs = [];
  let i = 0; let buf = '';
  const push = (t, rtl) => { if (!t) return; const last = segs[segs.length - 1]; if (last && last.rtl === rtl) last.text += t; else segs.push({ text: t, rtl }); };
  while (i < chars.length) {
    if (isLat(chars[i])) {
      // characters glued to the start of the Latin token belong to it: "@user", ".NET", and tokens that
      // start with digits — "12:A3:72:F1:8B:13", "10MB", "3DS", "4XEDD"
      let lead = '';
      while (buf.length && /[@#$.0-9:_\-\/]/.test(buf[buf.length - 1])) { lead = buf[buf.length - 1] + lead; buf = buf.slice(0, -1); }
      while (lead && !/^[@#$.0-9]/.test(lead)) { buf += lead[0]; lead = lead.slice(1); }
      push(buf, true); buf = '';
      let j = i; let lastStrong = i;
      while (j < chars.length && !isHeb(chars[j])) { if (isLat(chars[j]) || isDig(chars[j])) lastStrong = j; j++; }
      let lastLat = i;
      for (let k = i; k <= lastStrong; k++) if (isLat(chars[k])) lastLat = k;
      let glued = lastLat;
      while (glued + 1 <= lastStrong && /[0-9\-_./:]/.test(chars[glued + 1])) glued++;
      if (glued < lastStrong) {
        const tail = chars.slice(glued + 1, lastStrong + 1).join('');
        let n = lastStrong + 1;
        while (n < chars.length && chars[n] === ' ') n++;
        // "Chrome – 5 גרסאות", "Label: 5 פריטים": a spaced separator + number that quantifies the Hebrew noun
        if (/[–—:\-]/.test(tail) && /\s/.test(tail) && n < chars.length && isHeb(chars[n])) {
          push(lead ? LRM + lead + chars.slice(i, glued + 1).join('') : chars.slice(i, glued + 1).join(''), false);
          buf = '\u200F';
          i = glued + 1;
          continue;
        }
      }
      let end = lastStrong + 1;
      while (end < chars.length && TRAIL_ATTACHED.test(chars[end])) end++;
      let span = lead + chars.slice(i, end).join('');
      if (lead) span = LRM + span;
      if (end > lastStrong + 1) span += LRM;
      push(span, false);
      i = end;
    } else { buf += chars[i]; i++; }
  }
  push(buf, true);
  return segs;
}
// LTR paragraph: only Hebrew stretches become rtl runs.
function splitHebLtr(text) {
  const chars = Array.from(text);
  const segs = [];
  const push = (t, rtl) => { if (!t) return; const last = segs[segs.length - 1]; if (last && last.rtl === rtl) last.text += t; else segs.push({ text: t, rtl }); };
  let i = 0; let buf = '';
  while (i < chars.length) {
    if (isHeb(chars[i])) {
      push(buf, false); buf = '';
      let j = i; let last = i;
      while (j < chars.length && !isLat(chars[j])) { if (isHeb(chars[j])) last = j; j++; }
      push(chars.slice(i, last + 1).join(''), true);
      i = last + 1;
    } else { buf += chars[i]; i++; }
  }
  push(buf, false);
  return segs;
}

// {{sec:id}} {{title:id}} {{fig:id}} {{tbl:id}} {{var}}
const SECTIONS = {}; const FIGS = {}; const TBLS = {}; const IDS = new Set();
function resolve(text, label) {
  if (text === undefined || text === null) return '';
  const out = String(text).replace(/\{\{\s*(?:([a-z]+):)?([A-Za-z0-9_\-]+)\s*\}\}/g, (m, kind, id) => {
    if (!kind) {
      if (Object.prototype.hasOwnProperty.call(VARS, id)) return String(VARS[id]);
      errors.push(`${label}: משתנה לא מוגדר {{${id}}} (הגדר אותו ב־vars)`); return m;
    }
    const table = { sec: SECTIONS, title: SECTIONS, fig: FIGS, tbl: TBLS }[kind];
    if (!table) { errors.push(`${label}: סוג הפניה לא מוכר "${kind}" (sec / title / fig / tbl)`); return m; }
    if (!table[id]) { errors.push(`${label}: הפניה ל־"${id}" שלא קיים (${m})`); return m; }
    return kind === 'title' ? table[id].title : table[id].num;
  });
  return out;
}

function inlineParts(text) {
  const out = []; const re = /(\*\*[^*]+?\*\*|`[^`]+`)/g; let last = 0; let m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push({ t: text.slice(last, m.index) });
    out.push(m[0].startsWith('**') ? { t: m[0].slice(2, -2), bold: true } : { t: m[0].slice(1, -1), code: true });
    last = re.lastIndex;
  }
  if (last < text.length) out.push({ t: text.slice(last) });
  return out;
}

// text → TextRuns (inline **bold** and `code`), bidi-safe
function runs(text, st = {}, rtlPara = RTL) {
  const out = [];
  const size = st.size || 20;
  for (const part of inlineParts(String(text))) {
    if (part.code) {
      out.push(new TextRun({
        text: rtlPara ? LRM + part.t + LRM : part.t, font: CODE_FONT, size: Math.max(size - 2, 14),
        bold: st.bold, color: st.codeColor || st.color || C.code_text, rightToLeft: false,
      }));
      continue;
    }
    const t = (RTL ? normalizeHe : normalizeEn)(part.t);
    for (const s of rtlPara ? splitBidi(t) : splitHebLtr(t)) {
      out.push(new TextRun({
        text: s.text, rightToLeft: s.rtl, font: st.font || FONT, size, bold: st.bold || part.bold,
        italics: st.italics, color: st.color || C.text,
      }));
    }
  }
  return out;
}

// ───────────────────────────── layout constants ─────────────────────────────
const PAGE_W = 11906; const PAGE_H = 16838; const MARGIN_X = 1134;
const CONTENT_W = PAGE_W - 2 * MARGIN_X; // twips
const CONTENT_PX = Math.floor(CONTENT_W / 15); // 96 dpi
const CM_PX = 96 / 2.54;
const border = (color = C.border, size = 4) => ({ style: BorderStyle.SINGLE, size, color });
const cellBorders = { top: border(), bottom: border(), left: border(), right: border() };
const KEEP_ROWS = 14;

function P(text, o = {}, label = 'טקסט') {
  const rtl = RTL && !o.ltr;
  return new Paragraph({
    bidirectional: rtl ? true : (RTL ? false : undefined),
    alignment: o.align,
    spacing: { before: o.before ?? 0, after: o.after ?? 120, line: o.line ?? 288, lineRule: o.lineRule },
    keepNext: o.keepNext, keepLines: o.keepLines, numbering: o.numbering, heading: o.heading,
    border: o.border, shading: o.shading, indent: o.indent, style: o.style, tabStops: o.tabStops,
    pageBreakBefore: o.pageBreakBefore,
    children: o.children || runs(resolve(text, label), o.run || {}, rtl),
  });
}
const spacer = (after = 120) => new Paragraph({ bidirectional: RTL || undefined, spacing: { before: 0, after }, children: [] });

function widths(weights, total = CONTENT_W) {
  const sum = weights.reduce((a, b) => a + b, 0);
  const w = weights.map((x) => Math.floor((x / sum) * total));
  w[0] += total - w.reduce((a, b) => a + b, 0);
  return w;
}

function cellValueParas(v, o, label) {
  const st = { size: o.size || 18, bold: o.bold, color: o.color || C.text };
  const codeSize = (o.size || 18) - 2;
  const mk = (txt, extra = {}) => new Paragraph({
    bidirectional: RTL || undefined,
    alignment: o.center ? AlignmentType.CENTER : undefined,
    spacing: { before: 0, after: extra.after ?? 0, line: 252 },
    keepNext: o.keepNext, numbering: extra.numbering,
    children: o.code && txt && !/[\u0590-\u05FF]/.test(txt)
      ? [new TextRun({ text: RTL ? LRM + txt + LRM : txt, font: CODE_FONT, size: codeSize, bold: st.bold, color: o.color || C.code_text, rightToLeft: false })]
      : runs(resolve(txt, label), st),
  });
  if (v === undefined || v === null || v === '') return [mk('')];
  if (typeof v === 'boolean') return [mk(v ? T.yes : T.no)];
  if (Array.isArray(v)) return v.map((it, i) => mk(String(it), { numbering: { reference: 'cellbullets', level: 0 }, after: i === v.length - 1 ? 0 : 20 }));
  return String(v).split('\n').map((ln) => mk(ln));
}

function cell(v, o = {}, label = 'תא') {
  return new TableCell({
    width: { size: o.width, type: WidthType.DXA },
    columnSpan: o.span,
    verticalAlign: VerticalAlign.CENTER,
    borders: cellBorders,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR, color: 'auto' } : undefined,
    children: cellValueParas(v, o, label),
  });
}

// ───────────────────────────── numbering pass ─────────────────────────────
const ID_RE = /^[A-Za-z][A-Za-z0-9_\-]*$/;
function registerId(id, label) {
  if (!ID_RE.test(id)) { errors.push(`${label}: המזהה "${id}" אינו חוקי (אותיות לטיניות, ספרות, _ -)`); return; }
  if (IDS.has(id)) errors.push(`${label}: המזהה "${id}" כבר בשימוש`);
  IDS.add(id);
}
const HEADINGS = []; // {bookmark, text, level, num, part?}
let bmCounter = 0;
const newBookmark = () => `_TocAD${String(++bmCounter).padStart(4, '0')}`;

function numberSections(list, prefix, level) {
  if (!Array.isArray(list)) { errors.push(`sections חייב להיות מערך (${prefix || 'שורש'})`); return; }
  list.forEach((sec, i) => {
    const num = prefix ? `${prefix}.${i + 1}` : `${i + 1}`;
    const label = `סעיף ${num}`;
    if (!sec || typeof sec !== 'object') { errors.push(`${label}: סעיף לא תקין`); return; }
    if (!sec.title) errors.push(`${label}: חסרה כותרת (title)`);
    if (level > 3) errors.push(`${label}: עומק מקסימלי הוא 3 רמות (1.1.1) — השתמש בבלוק sub לכותרת פנימית`);
    if (sec.part && level !== 1) errors.push(`${label}: part מותר רק בסעיף ברמה העליונה`);
    sec._num = num; sec._level = level;
    if (sec.id) { registerId(sec.id, label); SECTIONS[sec.id] = { num, title: sec.title }; }
    const hasBlocks = Array.isArray(sec.blocks) && sec.blocks.length;
    const hasSubs = Array.isArray(sec.sections) && sec.sections.length;
    if (!hasBlocks && !hasSubs) errors.push(`${label} ("${sec.title}") ריק — הוסף תוכן או הסר אותו`);
    if (sec.blocks !== undefined && !Array.isArray(sec.blocks)) errors.push(`${label}: blocks חייב להיות מערך`);
    numberSections(sec.sections || [], num, level + 1);
  });
}

function forEachBlock(list, fn) {
  for (const sec of list || []) {
    (sec.blocks || []).forEach((b, bi) => fn(b, sec, bi));
    forEachBlock(sec.sections, fn);
  }
}

// ───────────────────────────── blocks ─────────────────────────────
const CODE_DATA = {}; const TABLE_DATA = {};
let numberedInstance = 0;

function resolveColumns(b, label) {
  let cols = b.columns;
  let presetName = null;
  if (typeof cols === 'string') presetName = cols;
  else if (!cols && b.preset) presetName = b.preset;
  if (presetName) {
    const p = PRESETS[presetName];
    if (!p) { errors.push(`${label}: preset עמודות לא מוכר "${presetName}" (קיימים: ${Object.keys(PRESETS).join(', ')})`); return null; }
    cols = p.map(([key, he, en, width, flags]) => Object.assign({ key, label: RTL ? he : en, width }, flags || {}));
    if (b.labels) for (const [k, v] of Object.entries(b.labels)) { const c = cols.find((x) => x.key === k); if (c) c.label = v; else errors.push(`${label}: labels — עמודה לא מוכרת "${k}"`); }
    if (b.hide) cols = cols.filter((c) => !b.hide.includes(c.key));
  }
  if (!Array.isArray(cols) || !cols.length) { errors.push(`${label}: חסר columns (מערך עמודות או שם preset)`); return null; }
  cols = cols.map((c, i) => (typeof c === 'string' ? { key: `c${i}`, label: c } : Object.assign({}, c)));
  const keys = new Set();
  for (const c of cols) {
    if (!c.key) { errors.push(`${label}: לכל עמודה חייב להיות key`); return null; }
    if (keys.has(c.key)) errors.push(`${label}: מפתח עמודה כפול "${c.key}"`);
    keys.add(c.key);
  }
  const numbered = b.numbered ?? (presetName ? (PRESET_NUMBERED[presetName] || false) : false);
  if (typeof numbered === 'string' && !/^[A-Za-z][A-Za-z0-9]{0,6}$/.test(numbered)) errors.push(`${label}: numbered צריך להיות true או קידומת מזהה כמו "FR" (התקבל "${numbered}")`);
  return { cols, numbered };
}

function makeTable(b, label) {
  const rc = resolveColumns(b, label);
  if (!rc) return null;
  let { cols } = rc;
  const rows = Array.isArray(b.rows) ? b.rows : (errors.push(`${label}: חסר rows`), []);
  // normalise rows
  const norm = [];
  rows.forEach((r, ri) => {
    const rl = `${label} שורה ${ri + 1}`;
    if (r && typeof r === 'object' && !Array.isArray(r) && 'group' in r) { norm.push({ group: r.group }); return; }
    let obj = {};
    if (Array.isArray(r)) {
      if (r.length !== cols.length) errors.push(`${rl}: ${r.length} ערכים אבל ${cols.length} עמודות (${cols.map((c) => c.key).join(', ')})`);
      cols.forEach((c, ci) => { obj[c.key] = r[ci]; });
    } else if (r && typeof r === 'object') {
      for (const k of Object.keys(r)) if (!cols.some((c) => c.key === k)) errors.push(`${rl}: עמודה לא מוכרת "${k}" (עמודות: ${cols.map((c) => c.key).join(', ')})`);
      obj = r;
    } else { errors.push(`${rl}: שורה לא תקינה`); return; }
    norm.push({ values: obj });
  });
  if (b.id) TABLE_DATA[b.id] = { cols: cols.map((c) => c.key), rows: norm.filter((r) => r.values).map((r) => r.values) };
  // duplicate identifiers in code key columns
  for (const c of cols.filter((x) => x.code && x === cols[0])) {
    const seen = new Map();
    norm.forEach((r, ri) => {
      if (!r.values) return;
      const v = String(r.values[c.key] ?? '').trim();
      if (!v) return;
      if (seen.has(v)) warnings.push(`${label}: "${v}" מופיע פעמיים בעמודה "${c.label}" (שורות ${seen.get(v) + 1} ו־${ri + 1})`);
      else seen.set(v, ri);
    });
  }
  if (rc.numbered) {
    const prefix = typeof rc.numbered === 'string' ? rc.numbered : '';
    cols = [{ key: '_n', label: prefix ? (RTL ? 'מזהה' : 'ID') : '#', width: prefix ? 0.62 : 0.35, center: true, code: Boolean(prefix) }, ...cols];
    let n = 0;
    norm.forEach((r) => {
      if (r.values) { n += 1; r.values = Object.assign({ _n: prefix ? `${prefix}-${String(n).padStart(2, '0')}` : String(n) }, r.values); }
    });
  }
  const ws = widths(cols.map((c) => c.width || 1.5));
  const nRows = 1 + norm.length;
  const keep = nRows <= KEEP_ROWS && b.keep_together !== false;
  let rowNo = 0;
  const kn = () => { rowNo += 1; return keep && rowNo < nRows; };
  const size = b.font_size || 18;
  const out = [];
  const hk = kn();
  out.push(new TableRow({
    tableHeader: true, cantSplit: true,
    children: cols.map((c, i) => cell(c.label, { width: ws[i], fill: C.primary, color: 'FFFFFF', bold: true, center: c.center, keepNext: hk, size }, label)),
  }));
  let zebra = 0;
  norm.forEach((r, ri) => {
    const k = kn();
    if (r.group !== undefined) {
      zebra = 0;
      out.push(new TableRow({
        cantSplit: true,
        children: [cell(r.group, { width: CONTENT_W, span: cols.length, fill: C.group_fill, color: C.navy, bold: true, keepNext: true, size }, label)],
      }));
      return;
    }
    const fill = zebra % 2 ? C.row_alt : undefined; zebra += 1;
    out.push(new TableRow({
      cantSplit: true,
      children: cols.map((c, i) => cell(r.values[c.key], { width: ws[i], fill, center: c.center, bold: c.bold, code: c.code, keepNext: k, size }, `${label} שורה ${ri + 1}`)),
    }));
  });
  return new Table({
    visuallyRightToLeft: RTL || undefined, layout: TableLayoutType.FIXED,
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: ws, rows: out,
  });
}

function kvTable(b, label) {
  let rows = b.rows;
  if (b.preset || b.data) {
    const p = KV_PRESETS[b.preset || 'interface'];
    if (!p) { errors.push(`${label}: preset לא מוכר "${b.preset}" (קיים: ${Object.keys(KV_PRESETS).join(', ')})`); return null; }
    const data = b.data || {};
    for (const k of Object.keys(data)) if (!p.some(([key]) => key === k)) errors.push(`${label}: שדה לא מוכר "${k}" ב־preset ${b.preset || 'interface'} (קיימים: ${p.map(([x]) => x).join(', ')})`);
    rows = p.filter(([key]) => data[key] !== undefined && data[key] !== '').map(([key, he, en, code]) => [RTL ? he : en, data[key], code]);
    for (const extra of b.rows || []) rows.push(extra);
  }
  if (!Array.isArray(rows) || !rows.length) { errors.push(`${label}: kv ללא rows`); return null; }
  const ws = widths(b.widths || [1.15, 3]);
  const nRows = rows.length + (b.header ? 1 : 0);
  const keep = nRows <= KEEP_ROWS;
  let rowNo = 0;
  const kn = () => { rowNo += 1; return keep && rowNo < nRows; };
  const out = [];
  if (b.header) {
    const k = kn();
    out.push(new TableRow({ tableHeader: true, cantSplit: true, children: b.header.map((h, i) => cell(h, { width: ws[i], fill: C.primary, color: 'FFFFFF', bold: true, keepNext: k }, label)) }));
  }
  rows.forEach((r, ri) => {
    if (!Array.isArray(r) || r.length < 2) { errors.push(`${label} שורה ${ri + 1}: כל שורה ב־kv היא [מפתח, ערך]`); return; }
    const k = kn();
    out.push(new TableRow({
      cantSplit: true,
      children: [
        cell(r[0], { width: ws[0], fill: C.label_fill, color: C.navy, bold: true, keepNext: k }, label),
        cell(r[1], { width: ws[1], keepNext: k, code: r[2] === true }, label),
      ],
    }));
  });
  return new Table({ visuallyRightToLeft: RTL || undefined, layout: TableLayoutType.FIXED, width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: ws, rows: out });
}

function codeParas(b, label) {
  let text;
  let parsed;
  const lang = (b.language || (b.json !== undefined ? 'json' : 'text')).toLowerCase();
  if (b.json !== undefined) { parsed = b.json; text = JSON.stringify(b.json, null, 2); }
  else if (typeof b.text === 'string') text = b.text;
  else if (Array.isArray(b.lines)) text = b.lines.join('\n');
  else { errors.push(`${label}: בלוק code צריך json (אובייקט), text או lines`); return []; }
  if (lang === 'json' && b.json === undefined) {
    try { parsed = JSON.parse(text); } catch (e) {
      if (b.lenient) warnings.push(`${label}: ה־JSON אינו תקין (lenient) — ${e.message}`);
      else errors.push(`${label}: דוגמת JSON לא תקינה — ${e.message}. תקן, או העבר את הדוגמה כ־"json": {...}, או סמן "lenient": true אם יש בה השמטות מכוונות (...)`);
    }
  }
  if (b.id) CODE_DATA[b.id] = parsed;
  const lines = text.replace(/\t/g, '  ').replace(/\s+$/, '').split('\n');
  const bd = { style: BorderStyle.SINGLE, size: 4, color: C.code_border, space: 4 };
  const keep = lines.length <= 30;
  const out = [];
  if (b.title) out.push(P(b.title, { before: 100, after: 60, keepNext: true, run: { bold: true, size: 19, color: C.navy } }, label));
  lines.forEach((ln, i) => {
    out.push(new Paragraph({
      bidirectional: false,
      alignment: AlignmentType.LEFT,
      spacing: { before: 0, after: 0, line: 240 },
      keepNext: keep && i < lines.length - 1, keepLines: true,
      shading: { type: ShadingType.CLEAR, fill: C.code_fill, color: 'auto' },
      border: { top: bd, left: bd, bottom: bd, right: bd },
      indent: { left: 60, right: 60 },
      children: [new TextRun({ text: ln.length ? ln : ' ', font: CODE_FONT, size: 16, color: C.code_text, rightToLeft: false })],
    }));
  });
  out.push(spacer(140));
  return out;
}

function imageSize(buf, what) {
  if (buf.length > 24 && buf.slice(0, 8).equals(Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]))) {
    return { type: 'png', w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
  }
  if (buf[0] === 0xFF && buf[1] === 0xD8) {
    let i = 2;
    while (i + 9 < buf.length) {
      if (buf[i] !== 0xFF) { i += 1; continue; }
      const m = buf[i + 1];
      if (m === 0xD8 || m === 0x01 || (m >= 0xD0 && m <= 0xD7)) { i += 2; continue; }
      const len = buf.readUInt16BE(i + 2);
      if ((m >= 0xC0 && m <= 0xC3) || (m >= 0xC5 && m <= 0xC7) || (m >= 0xC9 && m <= 0xCB) || (m >= 0xCD && m <= 0xCF)) {
        return { type: 'jpg', h: buf.readUInt16BE(i + 5), w: buf.readUInt16BE(i + 7) };
      }
      i += 2 + len;
    }
  }
  throw new SpecError(`${what}: התמונה אינה PNG או JPEG`);
}

function figureParas(b, label) {
  const imgs = [];
  if (b.type === 'diagram') {
    if (!MANIFEST) { errors.push(`${label}: תרשים "${b.id}" לא רונדר — בנה דרך make_spec.py (או העבר --diagrams)`); return []; }
    const m = MANIFEST[b.id];
    if (!m) { errors.push(`${label}: תרשים "${b.id}" חסר ב־manifest — הרינדור נכשל?`); return []; }
    const data = fs.readFileSync(m.png);
    let w = m.width * (b.scale || 0.85); let h = m.height * (b.scale || 0.85);
    if (b.width_pct) { const nw = (CONTENT_PX * b.width_pct) / 100; h = (h * nw) / w; w = nw; }
    imgs.push({ data, type: 'png', w, h, natural: m.width });
  } else {
    const list = b.paths || (b.path ? [b.path] : []);
    if (!list.length) { errors.push(`${label}: בלוק image צריך path או paths`); return []; }
    for (const p of list) {
      const full = path.isAbsolute(p) ? p : path.join(SPEC_DIR, p);
      if (!fs.existsSync(full)) { errors.push(`${label}: קובץ התמונה לא נמצא: ${full}`); continue; }
      const data = fs.readFileSync(full);
      let sz;
      try { sz = imageSize(data, label); } catch (e) { errors.push(e.message); continue; }
      imgs.push({ data, type: sz.type, nw: sz.w, nh: sz.h });
    }
    if (!imgs.length) return [];
    const multi = imgs.length > 1;
    const hcm = b.height_cm || (multi ? 8 : null);
    for (const im of imgs) {
      if (hcm) { im.h = hcm * CM_PX; im.w = (im.nw * im.h) / im.nh; }
      else if (b.width_cm) { im.w = b.width_cm * CM_PX; im.h = (im.nh * im.w) / im.nw; }
      else { im.w = Math.min(CONTENT_PX, im.nw); im.h = (im.nh * im.w) / im.nw; }
    }
  }
  // fit: total width ≤ content width, height ≤ max
  const gap = 14;
  const maxH = (b.max_height_cm || 19) * CM_PX;
  const totalW = imgs.reduce((a, im) => a + im.w, 0) + gap * (imgs.length - 1);
  let f = Math.min(1, CONTENT_PX / totalW);
  for (const im of imgs) f = Math.min(f, maxH / im.h);
  if (b.type === 'diagram' && imgs[0]) {
    const eff = (imgs[0].w * f) / imgs[0].natural;
    if (eff < 0.65) warnings.push(`${label}: התרשים "${b.id}" הוקטן ל־${Math.round(eff * 100)}% כדי להיכנס לעמוד — הטקסט בו יהיה קטן מדי לקריאה. קצר את התרשים, פצל אותו לשניים או שנה כיוון (TD / LR)`);
  }
  const children = [];
  imgs.forEach((im, i) => {
    if (i) children.push(new TextRun({ text: '   ' }));
    children.push(new ImageRun({
      type: im.type, data: im.data,
      transformation: { width: Math.round(im.w * f), height: Math.round(im.h * f) },
      altText: { title: b.caption || b.id || 'image', description: b.alt || b.caption || '', name: b.id || `image${i + 1}` },
    }));
  });
  const out = [new Paragraph({
    bidirectional: RTL || undefined, alignment: AlignmentType.CENTER, keepNext: Boolean(b.caption), keepLines: true,
    spacing: { before: 120, after: b.caption ? 60 : 160 }, children,
  })];
  if (b.caption) {
    const num = b.id && FIGS[b.id] ? FIGS[b.id].num : b._fignum;
    out.push(new Paragraph({
      bidirectional: RTL || undefined, alignment: AlignmentType.CENTER, spacing: { before: 0, after: 200 },
      children: [
        ...runs(`${T.figure} ${num} – `, { size: 17, bold: true, color: C.navy }),
        ...runs(resolve(b.caption, label), { size: 17, color: C.muted }),
      ],
    }));
  }
  return out;
}

const CALLOUT_COLORS = {
  note: [C.callout_fill, C.border], info: [C.callout_fill, C.border], warning: [C.warn_fill, C.warn_border],
  decision: [C.ok_fill, C.ok_border], open: [C.open_fill, C.open_border],
};

function renderBlock(b, ctx, body) {
  const label = `סעיף ${ctx.num} ("${ctx.title}") בלוק ${ctx.bi + 1}${b && b.type ? ` (${b.type})` : ''}`;
  if (!b || typeof b !== 'object') { errors.push(`${label}: בלוק לא תקין`); return; }
  const next = ctx.next || {};
  const nextIsObject = ['table', 'kv', 'code', 'diagram', 'image'].includes(next.type);
  switch (b.type) {
    case 'p': body.push(P(b.text, { keepNext: nextIsObject || b.keep_next }, label)); break;
    case 'sub': body.push(P(b.text, { before: 200, after: 80, keepNext: true, run: { size: 22, bold: true, color: C.navy } }, label)); break;
    case 'note': body.push(P(b.text, { before: 40, after: 140, keepNext: nextIsObject || b.keep_next, run: { size: 17, color: C.muted } }, label)); break;
    case 'callout': {
      const kind = b.kind || 'note';
      if (!CALLOUT_COLORS[kind]) errors.push(`${label}: kind לא מוכר "${kind}" (note / info / warning / decision / open)`);
      const [fill, bc] = CALLOUT_COLORS[kind] || CALLOUT_COLORS.note;
      const bd = { style: BorderStyle.SINGLE, size: 6, color: bc, space: 6 };
      const prefix = b.label === false ? '' : `**${b.label || T.callout[kind] || ''} –** `;
      body.push(P(`${prefix}${b.text}`, {
        before: 80, after: 200, keepNext: b.keep_next, shading: { type: ShadingType.CLEAR, fill, color: 'auto' },
        border: { top: bd, left: bd, bottom: bd, right: bd }, indent: { left: 120, right: 120 }, run: { size: 20, color: C.navy },
      }, label));
      break;
    }
    case 'bullets':
    case 'numbered': {
      if (!Array.isArray(b.items) || !b.items.length) { errors.push(`${label}: חסר items`); break; }
      const ref = b.type === 'bullets' ? 'bullets' : 'numbers';
      const instance = b.type === 'numbered' ? ++numberedInstance : undefined;
      // a short list that introduces a table / figure stays on the same page as it
      const glue = nextIsObject && b.items.length <= 4;
      b.items.forEach((it, ii) => {
        const item = typeof it === 'string' ? { text: it } : it;
        if (!item || item.text === undefined) { errors.push(`${label} פריט ${ii + 1}: חסר text`); return; }
        if (/^\s*([•◦▪●\-*]|\d+[.)])\s/.test(item.text)) warnings.push(`${label} פריט ${ii + 1}: הטקסט מתחיל בתבליט/מספר מוקלד — הרשימה כבר ממוספרת`);
        const last = ii === b.items.length - 1 && !(item.sub || []).length;
        body.push(P(item.text, { numbering: { reference: ref, level: 0, instance }, after: 60, keepNext: glue || (nextIsObject && last) }, label));
        (item.sub || []).forEach((s) => {
          const stext = typeof s === 'string' ? s : s.text;
          body.push(P(stext, { numbering: { reference: ref, level: 1, instance }, after: 40, keepNext: glue }, label));
        });
      });
      body.push(new Paragraph({ bidirectional: RTL || undefined, keepNext: nextIsObject, spacing: { before: 0, after: 60 }, children: [] }));
      break;
    }
    case 'kv': { const t = kvTable(b, label); if (t) { body.push(t); body.push(spacer(b.note ? 40 : 160)); if (b.note) body.push(P(b.note, { after: 160, run: { size: 17, color: C.muted } }, label)); } break; }
    case 'table': {
      if (b.caption) {
        const num = TBLS[b.id] ? TBLS[b.id].num : b._tblnum;
        body.push(new Paragraph({ bidirectional: RTL || undefined, keepNext: true, spacing: { before: 120, after: 60 }, children: [...runs(`${T.table} ${num} – `, { size: 17, bold: true, color: C.navy }), ...runs(resolve(b.caption, label), { size: 17, color: C.muted })] }));
      }
      const t = makeTable(b, label);
      if (t) { body.push(t); body.push(spacer(b.note ? 40 : 160)); if (b.note) body.push(P(b.note, { after: 160, run: { size: 17, color: C.muted } }, label)); }
      break;
    }
    case 'code': body.push(...codeParas(b, label)); break;
    case 'diagram':
    case 'image': body.push(...figureParas(b, label)); break;
    case 'page_break': body.push(new Paragraph({ bidirectional: RTL || undefined, pageBreakBefore: true, children: [] })); break;
    default: errors.push(`${label}: סוג בלוק לא מוכר "${b.type}" (p, sub, note, callout, bullets, numbered, kv, table, code, diagram, image, page_break)`);
  }
}

// ───────────────────────────── checks ─────────────────────────────
function flattenJson(v, prefix, out) {
  if (Array.isArray(v)) {
    const p = prefix ? `${prefix}[]` : '[]';
    out.add(p);
    for (const el of v) flattenJson(el, p, out);
  } else if (v && typeof v === 'object') {
    if (prefix) out.add(prefix);
    for (const [k, x] of Object.entries(v)) flattenJson(x, prefix ? `${prefix}.${k}` : k, out);
  } else if (prefix) out.add(prefix);
  return out;
}
const stripArr = (p) => p.replace(/\[\]/g, '').replace(/^\./, '');

function runChecks() {
  for (const [ci, ch] of (spec.checks || []).entries()) {
    const label = `בדיקה ${ci + 1}${ch.msg ? ` ("${ch.msg}")` : ''}`;
    if (ch.type !== 'json_fields') { errors.push(`${label}: סוג בדיקה לא מוכר "${ch.type}" (קיים: json_fields)`); continue; }
    if (!(ch.json in CODE_DATA)) { errors.push(`${label}: אין בלוק code עם id "${ch.json}"`); continue; }
    if (!TABLE_DATA[ch.table]) { errors.push(`${label}: אין טבלה עם id "${ch.table}"`); continue; }
    const js = CODE_DATA[ch.json];
    if (js === undefined) { errors.push(`${label}: הבלוק "${ch.json}" אינו JSON תקין`); continue; }
    const col = ch.column || TABLE_DATA[ch.table].cols[0];
    let jp = [...flattenJson(js, '', new Set())].map(stripArr).filter(Boolean);
    if (ch.root) {
      const r = stripArr(ch.root);
      jp = jp.filter((p) => p.startsWith(`${r}.`)).map((p) => p.slice(r.length + 1));
    }
    const ignore = (p) => (ch.ignore || []).some((ig) => p === ig || p.startsWith(`${ig}.`));
    jp = jp.filter((p) => !ignore(p));
    const tp = TABLE_DATA[ch.table].rows.map((r) => stripArr(String(r[col] ?? '').trim().split(/\s+/)[0] || '')).filter((p) => /^[A-Za-z_$][\w$.\-]*$/.test(p)).filter((p) => !ignore(p));
    if (!tp.length) { errors.push(`${label}: לא נמצאו שמות שדות בעמודה "${col}" של הטבלה "${ch.table}"`); continue; }
    const covered = (p) => tp.some((t) => t === p || p.startsWith(`${t}.`) || t.startsWith(`${p}.`));
    const undocumented = jp.filter((p) => !covered(p));
    // report only the top-most undocumented paths
    const top = undocumented.filter((p) => !undocumented.some((q) => q !== p && p.startsWith(`${q}.`)));
    if (top.length) errors.push(`${label}: שדות שמופיעים בדוגמת ה־JSON "${ch.json}" ואינם בטבלה "${ch.table}": ${top.slice(0, 12).join(', ')}${top.length > 12 ? ` (+${top.length - 12})` : ''}`);
    if (ch.require_all) {
      const inJson = (t) => jp.some((p) => p === t || p.startsWith(`${t}.`) || t.startsWith(`${p}.`));
      const missing = tp.filter((t) => !inJson(t));
      if (missing.length) {
        const msg = `${label}: שדות בטבלה "${ch.table}" שחסרים בדוגמה "${ch.json}": ${missing.slice(0, 12).join(', ')}${missing.length > 12 ? ` (+${missing.length - 12})` : ''}`;
        if (ch.require_all === 'error') errors.push(msg); else warnings.push(msg);
      }
    }
  }
}

// ───────────────────────────── dates & versions ─────────────────────────────
const MONTHS_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
function fmtDate(iso, label) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
  if (!m || Number(m[2]) < 1 || Number(m[2]) > 12 || Number(m[3]) < 1 || Number(m[3]) > 31) { errors.push(`${label}: תאריך חייב להיות בפורמט YYYY-MM-DD (התקבל "${iso}")`); return String(iso || ''); }
  return RTL ? `${m[3]}.${m[2]}.${m[1]}` : `${Number(m[3])} ${MONTHS_EN[Number(m[2]) - 1]} ${m[1]}`;
}
function cmpVer(a, b) {
  const x = String(a).split('.').map(Number); const y = String(b).split('.').map(Number);
  for (let i = 0; i < Math.max(x.length, y.length); i++) { const d = (x[i] || 0) - (y[i] || 0); if (d) return d; }
  return 0;
}

// ───────────────────────────── main ─────────────────────────────
async function main() {
  for (const req of ['title']) if (!meta[req]) errors.push(`meta.${req} חסר`);
  if (!Array.isArray(spec.sections) || !spec.sections.length) errors.push('sections חסר או ריק');

  // change log
  const log = spec.changelog || [];
  if (!Array.isArray(log) || !log.length) errors.push('changelog חסר — לפחות שורה אחת: {"version": "1.0", "date": "YYYY-MM-DD", "author": "...", "changes": "גרסה ראשונית"}');
  log.forEach((r, i) => {
    const l = `changelog שורה ${i + 1}`;
    if (!r.version || !/^\d+(\.\d+)*$/.test(String(r.version))) errors.push(`${l}: version חייב להיות מספר גרסה (1.0, 1.1 …)`);
    if (!r.changes) errors.push(`${l}: חסר changes`);
    if (i > 0 && r.version && log[i - 1].version && cmpVer(r.version, log[i - 1].version) <= 0) errors.push(`${l}: הגרסה ${r.version} אינה גדולה מהקודמת (${log[i - 1].version})`);
    if (i > 0 && r.date && log[i - 1].date && r.date < log[i - 1].date) warnings.push(`${l}: התאריך ${r.date} מוקדם מהשורה הקודמת`);
  });
  // author names are written in the document's language (Hebrew spec → Hebrew names)
  const authorList = [].concat(meta.authors || []).map((a, i) => [`meta.authors[${i}]`, a])
    .concat(log.map((r, i) => [`changelog שורה ${i + 1} (author)`, r.author]));
  for (const [where, name] of authorList) {
    if (!name) { if (where.startsWith('changelog')) errors.push(`${where}: חסר שם המחבר`); continue; }
    if (RTL && /[A-Za-z]/.test(name)) errors.push(`${where}: "${name}" – באפיון בעברית שם המחבר נכתב בעברית (למשל "מתן שרון", "צוות אפיון – אמן דיגיטל")`);
    if (!RTL && /[\u05D0-\u05EA]/.test(name)) errors.push(`${where}: "${name}" – in an English spec the author name is written in English`);
  }
  const lastLog = log[log.length - 1] || {};
  const version = meta.version || lastLog.version || '';
  if (meta.version && lastLog.version && String(meta.version) !== String(lastLog.version)) errors.push(`meta.version (${meta.version}) שונה מהגרסה האחרונה במעקב השינויים (${lastLog.version})`);
  const docDate = meta.date || lastLog.date;
  VARS.version = VARS.version ?? version;

  // numbering
  numberSections(spec.sections || [], '', 1);
  let figN = 0; let tblN = 0;
  forEachBlock(spec.sections, (b, sec, bi) => {
    if (!b || typeof b !== 'object') return;
    const l = `סעיף ${sec._num} בלוק ${bi + 1}`;
    if (b.id) registerId(b.id, l);
    if ((b.type === 'diagram' || b.type === 'image') && b.caption) { figN += 1; b._fignum = figN; if (b.id) FIGS[b.id] = { num: String(figN), title: b.caption }; }
    if (b.type === 'diagram' && !b.id) errors.push(`${l}: לבלוק diagram חייב להיות id`);
    if (b.type === 'table' && b.caption) { tblN += 1; b._tblnum = tblN; if (b.id) TBLS[b.id] = { num: String(tblN), title: b.caption }; }
  });

  const tocLevels = meta.toc_levels || 2;
  const topCount = (spec.sections || []).length;
  const allCount = (() => { let n = 0; const rec = (l) => (l || []).forEach((s) => { n += 1; rec(s.sections); }); rec(spec.sections); return n; })();
  const tocOn = meta.toc === true || (meta.toc !== false && (topCount >= 5 || allCount >= 10));

  const body = [];
  // ── logos: Aman Digital (brand) and the client's (meta.client_logo, optional)
  const AMAN_LOGO = fs.readFileSync(path.join(path.dirname(brandPath), BRAND.logo));
  let CLIENT_LOGO = null;
  if (meta.client_logo) {
    const cp = path.isAbsolute(meta.client_logo) ? meta.client_logo : path.join(SPEC_DIR, meta.client_logo);
    if (!fs.existsSync(cp)) errors.push(`meta.client_logo: קובץ הלוגו של הלקוח לא נמצא: ${cp}`);
    else {
      const data = fs.readFileSync(cp);
      try { const sz = imageSize(data, 'meta.client_logo'); CLIENT_LOGO = { data, type: sz.type, w: sz.w, h: sz.h }; } catch (e) { errors.push(e.message); }
    }
  }
  // ── cover page (page 1): logos, title band, document details. Change log and TOC start on page 2.
  const nb = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
  const noBorders = { top: nb, bottom: nb, left: nb, right: nb };
  const coverLogoRuns = () => {
    const cw = BRAND.cover_logo_width_px || 210;
    const out = [new ImageRun({ type: 'png', data: AMAN_LOGO, transformation: { width: cw, height: Math.round(cw * (BRAND.logo_aspect || 0.17485)) },
      altText: { title: BRAND.company_en, description: BRAND.company_en, name: 'cover_logo' } })];
    if (CLIENT_LOGO) {
      const k = Math.min((BRAND.cover_client_logo_max_height_px || 64) / CLIENT_LOGO.h, (BRAND.cover_client_logo_max_width_px || 220) / CLIENT_LOGO.w);
      out.push(new TextRun({ children: [new Tab()] }));
      out.push(new ImageRun({ type: CLIENT_LOGO.type, data: CLIENT_LOGO.data, transformation: { width: Math.round(CLIENT_LOGO.w * k), height: Math.round(CLIENT_LOGO.h * k) },
        altText: { title: meta.client || 'client logo', description: meta.client || 'client logo', name: 'cover_client_logo' } }));
    }
    return out;
  };
  // logos: Aman on the left, the client's on the right (LTR paragraph without text)
  body.push(new Paragraph({ bidirectional: false, alignment: AlignmentType.LEFT, spacing: { before: 0, after: 0 },
    tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }], children: coverLogoRuns() }));
  body.push(spacer(BRAND.cover_space_above_title || 2600));
  const bandParas = [
    P(meta.doc_type || T.doc_type, { after: 160, line: 240, lineRule: 'auto', run: { size: 26, bold: true, color: BRAND.cover_label_color || 'A9C2FF' } }, 'meta.doc_type'),
    P(meta.title, { after: meta.subtitle ? 200 : 0, line: 240, lineRule: 'auto', run: { size: 60, bold: true, color: 'FFFFFF' } }, 'meta.title'),
  ];
  if (meta.subtitle) bandParas.push(P(meta.subtitle, { after: 0, line: 276, lineRule: 'auto', run: { size: 26, color: 'DCE6FF' } }, 'meta.subtitle'));
  body.push(new Table({
    visuallyRightToLeft: RTL || undefined, layout: TableLayoutType.FIXED, width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
    rows: [
      new TableRow({ cantSplit: true, children: [new TableCell({ width: { size: CONTENT_W, type: WidthType.DXA }, borders: noBorders,
        shading: { fill: C.navy, type: ShadingType.CLEAR, color: 'auto' }, margins: { top: 520, bottom: 520, left: 480, right: 480 }, children: bandParas })] }),
      new TableRow({ cantSplit: true, height: { value: 110, rule: 'exact' }, children: [new TableCell({ width: { size: CONTENT_W, type: WidthType.DXA }, borders: noBorders,
        shading: { fill: C.primary, type: ShadingType.CLEAR, color: 'auto' }, children: [new Paragraph({ children: [] })] })] }),
    ],
  }));
  body.push(spacer(BRAND.cover_space_below_title || 900));
  const det = [];
  if (meta.client) det.push([T.client, meta.client]);
  if (meta.project) det.push([T.project, meta.project]);
  if (version) det.push([T.version, version]);
  if (docDate) det.push([T.date, fmtDate(docDate, 'meta.date')]);
  const authors = Array.isArray(meta.authors) ? meta.authors.join(', ') : meta.authors;
  if (authors) det.push([T.authors, authors]);
  if (meta.status) det.push([T.status, meta.status]);
  for (const d of meta.details || []) det.push(d);
  if (det.length) {
    const dw = widths([1, 3.4]);
    const rule = { style: BorderStyle.SINGLE, size: 4, color: C.border };
    const dcell = (v, w, o) => new TableCell({ width: { size: w, type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
      borders: { top: nb, left: nb, right: nb, bottom: rule }, margins: { top: 90, bottom: 90, left: 60, right: 60 }, children: cellValueParas(v, o, 'פרטי המסמך') });
    body.push(new Table({ visuallyRightToLeft: RTL || undefined, layout: TableLayoutType.FIXED, width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: dw,
      rows: det.map((r) => new TableRow({ cantSplit: true, children: [
        dcell(r[0], dw[0], { size: 18, bold: true, color: C.primary }), dcell(r[1], dw[1], { size: 21, color: C.navy })] })) }));
  }

  if (log.length) {
    body.push(P(T.changelog, { before: 0, after: 80, keepNext: true, pageBreakBefore: true, run: { size: 24, bold: true, color: C.navy } }));
    const logTable = makeTable({
      columns: [
        { key: 'version', label: T.version, width: 0.65, center: true },
        { key: 'date', label: T.date, width: 0.95, center: true },
        { key: 'author', label: T.author, width: 1.3 },
        { key: 'changes', label: T.change, width: 4.3 },
      ],
      rows: log.map((r, i) => ({ version: String(r.version || ''), date: fmtDate(r.date, `changelog שורה ${i + 1}`), author: r.author || '', changes: r.changes || '' })),
    }, 'מעקב שינויים');
    if (logTable) body.push(logTable);
    body.push(spacer(200));
  }

  // ── headings registry (TOC)
  const collect = (list) => (list || []).forEach((sec) => {
    sec._bm = newBookmark();
    if (sec.part) { sec._partBm = newBookmark(); HEADINGS.push({ bookmark: sec._partBm, text: normalizeTitle(sec.part), level: 0, part: true }); }
    HEADINGS.push({ bookmark: sec._bm, text: normalizeTitle(headingText(sec)), level: sec._level, num: sec._num });
    collect(sec.sections);
  });
  collect(spec.sections);

  if (tocOn) {
    body.push(P(T.toc, { before: 240, after: 120, keepNext: true, run: { size: 26, bold: true, color: C.navy } }));
    const entries = HEADINGS.filter((h) => h.level <= tocLevels);
    if (!PAGES) warnings.push('מספרי העמודים בתוכן העניינים לא חושבו — בנה דרך make_spec.py');
    entries.forEach((e, i) => {
      const page = PAGES && PAGES[e.bookmark] !== undefined ? String(PAGES[e.bookmark]) : '';
      const lvl = Math.max(1, e.level);
      const kids = [];
      if (i === 0 && JSZIP) kids.push(new TextRun({ text: '@@TOC_BEGIN@@' }));
      kids.push(new InternalHyperlink({
        anchor: e.bookmark,
        children: runs(e.text, { size: lvl === 1 ? 20 : 19, bold: lvl === 1 || e.part, color: e.part ? C.primary : C.navy }),
      }));
      kids.push(new TextRun({ children: [new Tab(), page], font: FONT, size: 19, color: C.navy, rightToLeft: false }));
      if (i === entries.length - 1 && JSZIP) kids.push(new TextRun({ text: '@@TOC_END@@' }));
      body.push(new Paragraph({
        bidirectional: RTL || undefined, style: `TOC${lvl}`,
        tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W, leader: 'dot' }],
        spacing: { before: lvl === 1 ? 60 : 0, after: 40 }, indent: lvl > 1 ? { left: 280 * (lvl - 1) } : undefined,
        children: kids,
      }));
    });
  }

  // ── sections
  let firstTop = true;
  const renderSection = (sec) => {
    if (sec.part) {
      body.push(new Paragraph({
        bidirectional: RTL || undefined, style: 'PartTitle', pageBreakBefore: (tocOn && firstTop) || sec.page_break_before,
        keepNext: true, spacing: { before: 240, after: 160 },
        shading: { type: ShadingType.CLEAR, fill: C.navy, color: 'auto' }, indent: { left: 0, right: 0 },
        children: [new Bookmark({ id: sec._partBm, children: runs(normalizeTitle(resolve(sec.part, 'part')), { size: 26, bold: true, color: 'FFFFFF' }) })],
      }));
    }
    const lvl = sec._level;
    const hs = { 1: { size: 30, color: C.primary, before: 360, after: 140 }, 2: { size: 25, color: C.navy, before: 260, after: 110 }, 3: { size: 22, color: C.navy, before: 200, after: 90 } }[lvl] || { size: 22, color: C.navy, before: 200, after: 90 };
    const breakHere = !sec.part && ((lvl === 1 && firstTop && tocOn) || sec.page_break_before);
    if (lvl === 1) firstTop = false;
    body.push(new Paragraph({
      bidirectional: RTL || undefined,
      heading: [null, HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3][lvl] || HeadingLevel.HEADING_3,
      pageBreakBefore: breakHere, keepNext: true, keepLines: true,
      spacing: { before: hs.before, after: hs.after, line: 264 },
      border: lvl === 1 ? { bottom: { style: BorderStyle.SINGLE, size: 8, color: C.primary, space: 4 } } : undefined,
      children: [new Bookmark({ id: sec._bm, children: runs(normalizeTitle(headingText(sec)), { size: hs.size, bold: true, color: hs.color }) })],
    }));
    const blocks = sec.blocks || [];
    blocks.forEach((b, bi) => renderBlock(b, { num: sec._num, title: sec.title, bi, next: blocks[bi + 1] }, body));
    (sec.sections || []).forEach(renderSection);
  };
  (spec.sections || []).forEach(renderSection);

  runChecks();

  // leftover placeholders anywhere in the spec text
  const dump = JSON.stringify(spec.sections || []);
  const todo = dump.match(/\b(TODO|XXX|FIXME)\b|\?\?\?|\[להשלים\]|lorem ipsum/gi);
  if (todo) warnings.push(`נמצאו ${todo.length} סימני השלמה (${[...new Set(todo)].join(', ')}) — להשלים או להעביר לסוגיות פתוחות`);

  if (errors.length) throw new SpecError('נמצאו שגיאות');

  // ── header / footer
  const lw = BRAND.logo_width_px || 150;
  const headerText = meta.header_note || `${meta.doc_type || T.doc_type} – ${meta.title}${version ? ` · ${T.version} ${version}` : ''}`;
  // Header logos: Aman Digital always on the left edge; the right edge is kept for the client's logo.
  // The paragraph is explicitly LTR and has no text, so Word and LibreOffice agree on the sides.
  const amanH = Math.round(lw * (BRAND.logo_aspect || 0.17485));
  const logoRuns = [new ImageRun({ type: 'png', data: AMAN_LOGO, transformation: { width: lw, height: amanH }, altText: { title: BRAND.company_en, description: BRAND.company_en, name: 'logo' } })];
  if (CLIENT_LOGO) {
    const k = Math.min((BRAND.client_logo_max_height_px || 34) / CLIENT_LOGO.h, (BRAND.client_logo_max_width_px || 150) / CLIENT_LOGO.w);
    logoRuns.push(new TextRun({ children: [new Tab()] }));
    logoRuns.push(new ImageRun({ type: CLIENT_LOGO.type, data: CLIENT_LOGO.data, transformation: { width: Math.round(CLIENT_LOGO.w * k), height: Math.round(CLIENT_LOGO.h * k) },
      altText: { title: meta.client || 'client logo', description: meta.client || 'client logo', name: 'client_logo' } }));
  }
  const header = new Header({
    children: [
      new Paragraph({ bidirectional: false, alignment: AlignmentType.LEFT, spacing: { after: 60 }, tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }], children: logoRuns }),
      new Paragraph({ bidirectional: RTL || undefined, spacing: { after: 0 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.border, space: 6 } }, children: runs(resolve(headerText, 'header'), { size: 16, color: C.muted }) }),
    ],
  });
  const company = RTL ? BRAND.company : BRAND.company_en;
  const address = RTL ? BRAND.address : BRAND.address_en;
  const note = meta.footer_note || (RTL ? BRAND.footer_note : BRAND.footer_note_en);
  const footRun = (t) => new TextRun({ text: t, rightToLeft: RTL, font: FONT, size: 15, color: C.muted });
  const footer = new Footer({
    children: [new Paragraph({
      bidirectional: RTL || undefined, border: { top: { style: BorderStyle.SINGLE, size: 6, color: C.border, space: 6 } }, spacing: { after: 0 },
      children: [
        ...runs(`${company} | ${address}${note ? ` | ${note}` : ''} | `, { size: 15, color: C.muted }),
        footRun(`${T.page} `),
        new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 15, color: C.muted }),
        footRun(` ${T.of} `),
        new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 15, color: C.muted }),
      ],
    })],
  });

  // cover page: no running header; the footer carries only the company line and the confidentiality note
  const coverHeader = new Header({ children: [new Paragraph({ children: [] })] });
  const coverFooter = new Footer({
    children: [new Paragraph({
      bidirectional: RTL || undefined, alignment: AlignmentType.CENTER, spacing: { after: 0 },
      children: runs(`${company} | ${address}${note ? ` | ${note}` : ''}`, { size: 15, color: C.muted }),
    })],
  });

  const lang = RTL ? { value: 'he-IL', bidirectional: 'he-IL' } : { value: 'en-US', bidirectional: 'he-IL' };
  const hstyle = (id, name, size, color, outline, extra = {}) => ({
    id, name, basedOn: 'Normal', next: 'Normal', quickFormat: true,
    run: { font: FONT, size, bold: true, color },
    paragraph: Object.assign({ spacing: { before: 240, after: 120 }, outlineLevel: outline, keepNext: true }, extra),
  });
  const doc = new Document({
    creator: authors || BRAND.company_en,
    title: `${meta.doc_type || T.doc_type} – ${meta.title}`,
    subject: meta.subtitle || '',
    description: `${T.version} ${version}`,
    styles: {
      default: { document: { run: { font: FONT, size: 20, color: C.text, language: lang }, paragraph: RTL ? { bidirectional: true } : {} } },
      paragraphStyles: [
        hstyle('Heading1', 'Heading 1', 30, C.primary, 0),
        hstyle('Heading2', 'Heading 2', 25, C.navy, 1),
        hstyle('Heading3', 'Heading 3', 22, C.navy, 2),
        hstyle('PartTitle', 'Part Title', 26, 'FFFFFF', 0),
        { id: 'TOC1', name: 'toc 1', basedOn: 'Normal', next: 'Normal', run: { font: FONT, size: 20, bold: true, color: C.navy }, paragraph: { spacing: { before: 60, after: 40 } } },
        { id: 'TOC2', name: 'toc 2', basedOn: 'Normal', next: 'Normal', run: { font: FONT, size: 19, color: C.navy }, paragraph: { spacing: { after: 40 }, indent: { left: 280 } } },
        { id: 'TOC3', name: 'toc 3', basedOn: 'Normal', next: 'Normal', run: { font: FONT, size: 18, color: C.navy }, paragraph: { spacing: { after: 30 }, indent: { left: 560 } } },
      ],
    },
    numbering: {
      config: [
        { reference: 'bullets', levels: [
          { level: 0, format: LevelFormat.BULLET, text: '•', style: { paragraph: { indent: { left: 400, hanging: 260 } }, run: { color: C.primary, font: FONT } } },
          { level: 1, format: LevelFormat.BULLET, text: '◦', style: { paragraph: { indent: { left: 800, hanging: 260 } }, run: { color: C.primary, font: FONT } } },
        ] },
        { reference: 'numbers', levels: [
          { level: 0, format: LevelFormat.DECIMAL, text: '%1.', style: { paragraph: { indent: { left: 420, hanging: 300 } }, run: { color: C.navy, font: FONT, bold: true } } },
          { level: 1, format: LevelFormat.DECIMAL, text: '%1.%2.', style: { paragraph: { indent: { left: 900, hanging: 440 } }, run: { color: C.navy, font: FONT } } },
        ] },
        { reference: 'cellbullets', levels: [
          { level: 0, format: LevelFormat.BULLET, text: '•', style: { paragraph: { indent: { left: 240, hanging: 180 } }, run: { color: C.primary, font: FONT } } },
        ] },
      ],
    },
    sections: [{
      properties: { titlePage: true, page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: 1650, bottom: 1250, left: MARGIN_X, right: MARGIN_X, header: 500, footer: 560 } } },
      headers: { default: header, first: coverHeader }, footers: { default: footer, first: coverFooter }, children: body,
    }],
  });

  let buf = await Packer.toBuffer(doc);
  buf = await postProcess(buf, tocOn, tocLevels);
  fs.mkdirSync(path.dirname(path.resolve(outPath)), { recursive: true });
  fs.writeFileSync(outPath, buf);

  const info = {
    lang: LANG, version, toc: tocOn, headings: HEADINGS,
    counts: { sections: allCount, figures: figN, captioned_tables: tblN, tables: Object.keys(TABLE_DATA).length, code_blocks: Object.keys(CODE_DATA).length, checks: (spec.checks || []).length },
    warnings,
  };
  if (INFO_OUT) fs.writeFileSync(INFO_OUT, JSON.stringify(info, null, 2));
  console.log(`✓ נבנה: ${outPath}`);
  console.log(`  שפה: ${LANG === 'he' ? 'עברית (RTL)' : 'English (LTR)'} | גרסה ${version} | ${allCount} סעיפים | ${figN} תרשימים ממוספרים | ${(spec.checks || []).length} בדיקות עקביות JSON↔טבלה`);
  if (warnings.length) { console.log(`\n⚠️  אזהרות (${warnings.length}):`); warnings.forEach((w) => console.log(`  - ${w}`)); }
}

function headingText(sec) { return `${sec._num}${sec._level === 1 ? '.' : ''} ${resolve(sec.title, `כותרת סעיף ${sec._num}`)}`; }
function normalizeTitle(t) { return RTL ? normalizeHe(t) : normalizeEn(t); }

// Post-processing of the packed docx:
//  - every bookmark gets a unique w:id (docx-js gives them all id 1 → schema violation)
//  - the cached TOC paragraphs become a real Word TOC field (right-click → Update Field works in Word)
// docx-js writes <w:pBdr> children as top, bottom, left, right; the schema order is top, left, bottom, right
const BORDER_ORDER = ['top', 'left', 'bottom', 'right', 'between', 'bar'];
function fixBorderOrder(xml) {
  return xml.replace(/<w:pBdr>([\s\S]*?)<\/w:pBdr>/g, (m, inner) => {
    const kids = inner.match(/<w:(top|left|bottom|right|between|bar)\b[^>]*\/>/g) || [];
    kids.sort((a, b) => BORDER_ORDER.indexOf(a.match(/<w:(\w+)/)[1]) - BORDER_ORDER.indexOf(b.match(/<w:(\w+)/)[1]));
    return `<w:pBdr>${kids.join('')}</w:pBdr>`;
  });
}

async function postProcess(buf, tocOn, levels) {
  const JSZip = JSZIP;
  if (!JSZip) {
    warnings.push('jszip לא נמצא — מזהי סימניות לא תוקנו ותוכן העניינים נוצר כרשימת קישורים ולא כשדה Word');
    return buf;
  }
  const zip = await JSZip.loadAsync(buf);
  let xml = await zip.file('word/document.xml').async('string');
  let next = 1; const stack = [];
  xml = xml.replace(/<w:bookmark(Start|End)\b([^>]*?)w:id="\d+"([^>]*)\/>/g, (m, kind, a, b) => {
    let id;
    if (kind === 'Start') { id = next++; stack.push(id); } else { id = stack.length ? stack.pop() : next++; }
    return `<w:bookmark${kind}${a}w:id="${id}"${b}/>`;
  });
  if (tocOn) {
    const runRe = (marker) => new RegExp(`<w:r(?:\\s[^>]*)?>(?:(?!<w:r[\\s>])[\\s\\S])*?${marker}</w:t></w:r>`);
    const begin = `<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \\o "1-${levels}" \\h \\z \\u </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r>`;
    const end = '<w:r><w:fldChar w:fldCharType="end"/></w:r>';
    if (!runRe('@@TOC_BEGIN@@').test(xml) || !runRe('@@TOC_END@@').test(xml)) throw new SpecError('לא נמצאו סמני תוכן העניינים במסמך');
    xml = xml.replace(runRe('@@TOC_BEGIN@@'), begin).replace(runRe('@@TOC_END@@'), end);
    if (xml.includes('@@TOC_')) throw new SpecError('סמן תוכן עניינים לא הוחלף');
  }
  zip.file('word/document.xml', fixBorderOrder(xml));
  for (const name of Object.keys(zip.files).filter((n) => /^word\/(header|footer)\d*\.xml$/.test(n))) {
    zip.file(name, fixBorderOrder(await zip.file(name).async('string')));
  }
  return zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
}

function fail(e) {
  if (e instanceof SpecError) {
    console.error('❌ הבנייה נכשלה — לא נוצר קובץ.');
    if (e.message !== 'נמצאו שגיאות') console.error(`  - ${e.message}`);
    errors.forEach((x) => console.error(`  - ${x}`));
    if (warnings.length) { console.error(`  אזהרות:`); warnings.forEach((w) => console.error(`  ⚠️ ${w}`)); }
    process.exit(1);
  }
  console.error(e);
  process.exit(1);
}

main().catch(fail);
