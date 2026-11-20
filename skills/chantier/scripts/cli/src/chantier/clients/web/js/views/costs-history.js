// Costs, the earlier batches: one row per closed batch, newest first; a click on a row unfolds that
// batch's CRs, a second click folds it. Which rows are open is the page's state (`historyOpen`).
import { delegate, html } from '../core/dom.js';
import { title, usd } from '../core/format.js';
import { snapshot, update } from '../core/store.js';
import { closedBatches, dayOf, hasUnpriced, mergedOf, totalOf } from '../model/history.js';
import { t } from '../model/words.js';
import { tag } from '../ui/parts.js';

const DASH = '—';

const head = (cells) =>
  html`<thead><tr>${cells.map(([word, cls]) => html`<th class="${cls}">${t(word)}</th>`)}</tr></thead>`;

// "$229.22 / $300.00"; a record with no budget shows its cost only, one with no figure a dash.
const spend = (r) =>
  r.budget_usd == null ? usd(r.cost_usd) : `${usd(r.cost_usd)} / ${usd(r.budget_usd)}`;

const crRow = (c) =>
  html`<tr><td><b>${c.cr}</b></td><td class="hide-phone"><span class="ct" title="${title(c.title)}">${title(c.title)}</span></td><td>${c.result ?? DASH}</td><td class="num">${c.rounds ?? DASH}</td><td class="num">${usd(c.cost_usd)}</td></tr>`;

const crTable = (r) => {
  const cells = [
    ['costs.th_cr', ''],
    ['costs.th_title', 'hide-phone'],
    ['costs.th_result', ''],
    ['costs.th_rounds', 'num'],
    ['costs.th_cost', 'num'],
  ];
  return html`<tr class="sub"><td colspan="5"><table>${head(cells)}<tbody>${(r.crs ?? []).map(crRow)}</tbody></table></td></tr>`;
};

function row(r, open) {
  const unpriced = hasUnpriced(r)
    ? html` ${tag('waits', t('costs.unpriced'), { badge: true })}`
    : '';
  const merged = `${mergedOf(r)}/${totalOf(r)}`;
  return html`<tr class="click" data-hist="${r.batch}" data-key="hist-${r.batch}" tabindex="0" role="button" aria-expanded="${open}"><td><b>${r.batch}</b></td><td>${dayOf(r.closed) || DASH}</td><td class="hide-phone">${r.mode ?? DASH}</td><td class="num">${merged}</td><td class="num">${spend(r)}${unpriced}</td></tr>${open ? crTable(r) : ''}`;
}

export function historyBlock(state) {
  const records = closedBatches(state.data);
  if (!records.length) return '';
  const cells = [
    ['costs.th_batch', ''],
    ['costs.th_closed', ''],
    ['costs.th_mode', 'hide-phone'],
    ['costs.th_crs', 'num'],
    ['costs.th_spend', 'num'],
  ];
  const body = records.map((r) => row(r, state.historyOpen.includes(r.batch)));
  return html`<h2 class="h2t">${t('costs.earlier')}</h2><div class="tbl"><table>${head(cells)}<tbody>${body}</tbody></table></div>`;
}

function toggle(batch) {
  const now = snapshot().historyOpen;
  update({ historyOpen: now.includes(batch) ? now.filter((b) => b !== batch) : [...now, batch] });
}

// Click, Enter or Space on a row folds or unfolds it. Returns the function that removes both.
export function bindHistory(root) {
  const offClick = delegate(root, 'click', '[data-hist]', (_, tr) => toggle(tr.dataset.hist));
  const offKey = delegate(root, 'keydown', '[data-hist]', (event, tr) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    toggle(tr.dataset.hist);
  });
  return () => {
    offClick();
    offKey();
  };
}
