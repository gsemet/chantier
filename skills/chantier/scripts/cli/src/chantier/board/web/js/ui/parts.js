// The small pieces every view draws the same way: tags, meters, figures, the empty state, marks.
import { html, vars } from '../core/dom.js';
import { markOf, percent } from '../core/format.js';
import { vstate } from '../model/semantics.js';
import { t } from '../model/words.js';

// A tag: `kind` is a CSS class of components.css (working, blocked, ready, waits, queued...).
export const tag = (kind, text, { badge = false } = {}) =>
  html`<span class="tag ${kind}${badge ? ' badge' : ''}">${text}</span>`;

// The tag of a CR's state: a queued CR held by its dependencies reads "waits".
export const stateTag = (c, opts) => tag(vstate(c), t(`state.${vstate(c)}`), opts);

// "release" or "fix" for a CR of that kind, else nothing.
export const kindTag = (c) =>
  c.kind ? tag(`kind-${c.kind}`, t(`kind.${c.kind}`), { badge: true }) : '';

// The state's tint class of a card.
export const tint = (c) => `st-${vstate(c)}`;

// A stacked bar: `parts` are `{ n, color }` with a token for the colour, `whole` the full width.
export function meter(parts, whole) {
  const bars = parts
    .filter((p) => p.n > 0)
    .map(
      (p) =>
        html`<i data-vars="${vars({ '--w': `${percent(p.n, whole)}%`, '--c': p.color })}"></i>`,
    );
  return html`<div class="meter">${bars}</div>`;
}

// A figure with its label and sub-line: `tone` is calm, go or hot; `go` the place a click opens.
export function kpi({ tone = '', label, value, sub = '', go = null }) {
  const attrs = go ? html` data-go="${go}"` : '';
  return html`<div class="kpi ${tone}"${attrs}><span class="l">${label}</span><b>${value}</b><span>${sub}</span></div>`;
}

// What a view shows when it has nothing to show.
export const empty = (text) => html`<div class="empty">${text}</div>`;

// A project's coloured square with its first letter.
export const mark = (id) =>
  html`<span class="mark" data-mark="${markOf(id)}">${(id[0] ?? '?').toUpperCase()}</span>`;

// A small dot in a token colour.
export const dot = (color) => html`<span class="dot" data-vars="${vars({ '--c': color })}"></span>`;
