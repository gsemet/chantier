// The one column of the board, the only module that writes the class `column` and the `column-*`
// classes (DESIGN.md). Pure: `column(parts)` returns the markup of a Triage or a Kanban column,
// `lane(parts)` that of a Backlog lane, which sits in a column's body.
//   key      the paint key (`data-key`), `drop` a drop target's name (`data-col`), `label` its aria-label
//   name     the head's title, `color` its dot's token, `count` the figure after it, `hint` a line in the
//            count's place (ellipsed), `states` the head's extras (grill counts), `act` an action under
//            the head
//   sub      the one-line grey sub-line (ellipsed), `body` what the column holds, `foot` what follows
// A lane has no dot and no name: its head is `chip` (the priority chip), `count` and `states`.
import { html } from '../core/dom.js';
import { dot } from './parts.js';

const attr = (name, value) =>
  value === undefined || value === '' ? '' : html` ${name}="${value}"`;

function head({ color, name, count, hint, states = '' }) {
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

export function lane({ drop, label, chip, count, states = '', body = '', empty = false }) {
  const names = `column-lane${empty ? ' column-empty' : ''}`;
  const figure = html`<span class="column-count">${count}</span>`;
  return html`<section class="${names}" data-col="${drop}" aria-label="${label}"><div class="column-head">${chip}${figure}${states}</div><div class="column-body column-grid">${body}</div></section>`;
}
