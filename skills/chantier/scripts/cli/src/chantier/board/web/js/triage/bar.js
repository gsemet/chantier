// The bar above the columns: the next-batch indicator, the journal button, the label filter row and
// the legend of the four grill states. Pure markup.
import { html } from '../core/dom.js';
import { hhmm } from '../core/format.js';
import { journalButton } from '../journal/journal.js';
import { filterRow } from '../labels/filter.js';
import { STAGES } from '../model/grill.js';
import { t } from '../model/words.js';
import { mark } from './postit.js';

// The indicator: green when the user said "ready" for exactly 3-ready, else amber.
export function indicatorMarkup({ kind, n, at }) {
  const ok = kind === 'declared';
  const text = t(`triage.ind_${kind}`, { n, time: hhmm(at) });
  const head = t(`triage.ind_${kind}_head`);
  return html`<div class="ind ${ok ? 'ok' : 'no'}" role="status">● <b>${head}</b>${text}</div>`;
}

const legend = () =>
  html`<div class="legend2">${STAGES.map((s) => html`<span>${mark(s)}${t(`postit.legend_${s}`)}</span>`)}</div>`;

export const bar = (state, ind) =>
  html`<div class="tbar">${indicatorMarkup(ind)}${journalButton(state)}${filterRow(state)}${legend()}</div>`;
