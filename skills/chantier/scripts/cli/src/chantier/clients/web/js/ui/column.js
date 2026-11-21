// The one column of the board, the only module that writes the class `column` and the `column-*`
// classes (DESIGN.md). Pure: `column(parts)` returns the markup of a Triage or a Kanban column,
// `lane(parts)` that of a Backlog lane, which sits in a column's body.
//   key      the paint key (`data-key`), `drop` a drop target's name (`data-col`), `label` its aria-label
//   name     the head's title, `color` its dot's token, `count` the figure after it, `hint` a line in the
//            count's place (ellipsed), `states` the head's extras (grill counts), `act` an action under
//            the head
//   sub      the one-line grey sub-line (ellipsed), `body` what the column holds, `foot` what follows
//   fold     a foldable lane's row name, `folded` whether it is folded, `foldLabel` its chevron's label
// A lane has no dot. A Backlog lane's head is its chevron (`fold`), `chip` (the priority chip), `count` and `states`; a
// named lane (Triage's last column holds two) has `name`, `count`, `states` and its own `sub`, and
// `idle` greys it; `foot` follows its body.
import { html } from '../core/dom.js';
import { icon } from './icons.js';
import { dot } from './parts.js';

const attr = (name, value) =>
  value === undefined || value === '' ? '' : html` ${name}="${value}"`;

function head({ color, name, count, hint, states = '' }) {
  if (!color && !name && count === undefined && !hint && !states) return '';
  const mark = color ? dot(color) : '';
  const title = name ? html`<h2>${name}</h2>` : '';
  const figure = count === undefined ? '' : html`<span class="column-count">${count}</span>`;
  const line = hint ? html`<span class="column-hint" title="${hint}">${hint}</span>` : '';
  return html`<div class="column-head">${mark}${title}${figure}${line}${states}</div>`;
}

export function column(parts = {}) {
  const { key, drop, label, act = '', sub = '', body = '', foot = '' } = parts;
  const line = sub ? html`<div class="column-sub" title="${sub}">${sub}</div>` : '';
  const action = act ? html`<div class="column-act">${act}</div>` : '';
  return html`<section class="column"${attr('data-key', key)}${attr('data-col', drop)}${attr('aria-label', label)}>${head(parts)}${action}${line}<div class="column-body">${body}</div>${foot}</section>`;
}

export function lane(parts) {
  const { drop, label, chip = '', name = '', count, states = '', body = '', empty = false } = parts;
  const { sub = '', foot = '', idle = false, fold = '', folded = false, foldLabel = '' } = parts;
  const named = Boolean(name);
  const names = [
    'column-lane',
    named && 'column-named',
    idle && 'column-idle',
    empty && 'column-empty',
    fold && folded && 'column-folded',
  ]
    .filter(Boolean)
    .join(' ');
  const title = named ? html`<h2>${name}</h2>` : '';
  const figure = html`<span class="column-count">${count}</span>`;
  const line = sub ? html`<div class="column-sub" title="${sub}">${sub}</div>` : '';
  const grid = named ? '' : ' column-grid';
  const chevron = fold
    ? html`<button type="button" class="column-fold" data-key="fold-${fold}" aria-expanded="${!folded}" aria-label="${foldLabel}">${icon('chev')}</button>`
    : '';
  const toggle = fold ? html` data-fold="${fold}"` : '';
  return html`<section class="${names}" data-col="${drop}" aria-label="${label}"><div class="column-head"${toggle}>${chevron}${chip}${title}${figure}${states}</div>${line}<div class="column-body${grid}">${body}</div>${foot}</section>`;
}
