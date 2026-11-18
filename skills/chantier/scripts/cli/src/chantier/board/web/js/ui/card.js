// The one card of the board, the only module that writes the class `card` and the `card-*` classes
// (DESIGN.md). Pure: `card(parts)` returns the markup, every page builds its cards with it.
//   as        'div' (default), 'section' or 'a' (with `href`: it opens in a new tab)
//   classes   page hooks (`pi`, `node`...), `attrs`: markup of attributes (opener, drag, data-*)
//   variants  names of card.css variants: sel, pick-up, picked, drag, pending, dim, highlight,
//             draft, flush, compact, clamp
//   priority  a bucket: its chip is first in the top row; `picked` puts the check mark after it
//   top       the rest of the top row; `title` (in a `heading` tag when it is one), `labels`,
//             `desc` (shown when given, even empty), `body` (a free block)
//   meta      the band's left items, `end` its right-aligned end, `foot` what follows the end
import { html, raw, textOf } from '../core/dom.js';
import { icon } from './icons.js';
import { priorityChip } from './parts.js';

const ELEMENTS = new Set(['div', 'section', 'a']);
const TITLES = new Set(['div', 'h2', 'h3']);
const given = (markup) => textOf(markup) !== '';

const check = html`<span class="card-check" aria-hidden="true">${icon('check')}</span>`;

// The top row: the priority chip first, then the check mark of a picked card, then the rest.
function topRow({ priority, picked, top }) {
  const chip = priority ? priorityChip(priority) : '';
  const first = html`${chip}${chip && picked ? check : ''}${top}`;
  return given(first) ? html`<div class="card-top">${first}</div>` : '';
}

function band({ meta, end, foot }) {
  if (!given(html`${meta}${end}${foot}`)) return '';
  const last = given(end) ? html`<span class="card-end">${end}</span>` : '';
  return html`<div class="card-meta">${meta}${last}${foot}</div>`;
}

function heading({ title, tag }) {
  if (!given(title)) return '';
  return html`${raw(`<${tag} class="card-title">`)}${title}${raw(`</${tag}>`)}`;
}

export function card(parts = {}) {
  const { as = 'div', href = '', classes = '', attrs = '', variants = [] } = parts;
  const { heading: tag = 'div', desc = null, body = '', labels = '' } = parts;
  if (!ELEMENTS.has(as) || !TITLES.has(tag)) throw new Error(`card: ${as}, ${tag}`);
  const names = ['card', ...variants.filter(Boolean).map((v) => `card-${v}`), classes]
    .filter(Boolean)
    .join(' ');
  const link = as === 'a' ? html` href="${href}" target="_blank" rel="noopener"` : '';
  const text = desc === null ? '' : html`<div class="card-desc">${desc}</div>`;
  const block = given(body) ? html`<div class="card-body">${body}</div>` : '';
  const inner = html`${topRow(parts)}${heading({ title: parts.title, tag })}${labels}${text}${block}${band(parts)}`;
  return html`${raw(`<${as}`)} class="${names}"${link} ${attrs}>${inner}${raw(`</${as}>`)}`;
}

// Put a variant on a card, or take it off: the drag and the light of the Batch graph.
export const cardMark = (element, variant, on = true) =>
  element.classList.toggle(`card-${variant}`, on);
