// The small Markdown renderer of the panel: headings, paragraphs, lists, tables, fenced code,
// inline code, bold and links. Every piece of text is escaped first; the only markup in the
// output is the tags written here. A link shows underlined and does not navigate.
import { esc, raw } from '../core/dom.js';

const FENCE = /^\s*```/;
const ROW = /^\s*\|/;
const RULE = /^\s*\|[\s:|-]+\|\s*$/;
const ITEM = /^\s*([-*]|\d+\.) (.*)/;
const HEADING = /^(#{1,6}) (.*)/;

// A heading of the file sits under the panel's own `h2`: `#` is drawn as an `h3`, down to `h6`.
const levelOf = (hashes) => Math.min(hashes.length + 2, 6);

// Inline marks on already escaped text.
const inline = (text) =>
  esc(text)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<u>$1</u>');

const startsBlock = (line) =>
  FENCE.test(line) || ROW.test(line) || ITEM.test(line) || HEADING.test(line) || !line.trim();

// Each reader takes the lines and a start, and returns `[markup, next]`.
function readFence(lines, at) {
  let end = at + 1;
  while (end < lines.length && !FENCE.test(lines[end])) end += 1;
  const body = lines
    .slice(at + 1, end)
    .map(esc)
    .join('\n');
  return [`<pre><code>${body}</code></pre>`, end + 1];
}

const cells = (line) =>
  line
    .trim()
    .replace(/^\||\|$/g, '')
    .split('|')
    .map((c) => c.trim());

function readTable(lines, at) {
  let end = at;
  while (end < lines.length && ROW.test(lines[end])) end += 1;
  const rows = lines.slice(at, end);
  const head = rows.length > 1 && RULE.test(rows[1]);
  const body = rows.filter((row, i) => !RULE.test(row) && !(head && i === 0));
  const tr = (row, tag) =>
    `<tr>${cells(row)
      .map((c) => `<${tag}>${inline(c)}</${tag}>`)
      .join('')}</tr>`;
  const top = head ? `<thead>${tr(rows[0], 'th')}</thead>` : '';
  return [`<table>${top}<tbody>${body.map((row) => tr(row, 'td')).join('')}</tbody></table>`, end];
}

function readList(lines, at) {
  const tag = /^\s*\d/.test(lines[at]) ? 'ol' : 'ul';
  const items = [];
  let end = at;
  while (end < lines.length) {
    const item = ITEM.exec(lines[end]);
    if (item) items.push(inline(item[2]));
    else if (/^\s{2,}\S/.test(lines[end]) && items.length)
      items[items.length - 1] += ` ${inline(lines[end].trim())}`;
    else break;
    end += 1;
  }
  return [`<${tag}>${items.map((i) => `<li>${i}</li>`).join('')}</${tag}>`, end];
}

function readParagraph(lines, at) {
  let end = at;
  while (end < lines.length && (end === at || !startsBlock(lines[end]))) end += 1;
  return [`<p>${lines.slice(at, end).map(inline).join(' ')}</p>`, end];
}

function readBlock(lines, at) {
  const line = lines[at];
  if (FENCE.test(line)) return readFence(lines, at);
  if (ROW.test(line)) return readTable(lines, at);
  if (ITEM.test(line)) return readList(lines, at);
  const heading = HEADING.exec(line);
  if (heading) {
    const n = levelOf(heading[1]);
    return [`<h${n} class="md-h${heading[1].length}">${inline(heading[2])}</h${n}>`, at + 1];
  }
  return line.trim() ? readParagraph(lines, at) : ['', at + 1];
}

// The markup of a Markdown text, ready to be drawn.
export function renderMarkdown(text) {
  const lines = String(text ?? '').split(/\r?\n/);
  let out = '';
  let at = 0;
  while (at < lines.length) {
    const [markup, next] = readBlock(lines, at);
    out += markup;
    at = next;
  }
  return raw(out);
}
