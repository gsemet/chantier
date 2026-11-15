// Home, the earlier batches: the five newest closed batches, one line each (id, closing date, CRs
// merged out of the batch's CRs, cost), and a link to Costs, which holds the whole list.
import { html } from '../core/dom.js';
import { usd } from '../core/format.js';
import { knows } from '../core/router.js';
import { closedBatches, dayOf, mergedOf, totalOf } from '../model/history.js';
import { t } from '../model/words.js';

const SHOWN = 5;

const DASH = '—';

const line = (r) =>
  html`<div class="x"><b>${r.batch}</b><span class="ell">${dayOf(r.closed) || DASH}</span><span class="r">${t('home.history_crs', { a: mergedOf(r), b: totalOf(r) })} · ${usd(r.cost_usd)}</span></div>`;

export function historyBlock(state) {
  const records = closedBatches(state.data).slice(0, SHOWN);
  const more = knows('costs')
    ? html`<button class="more" type="button" data-go="costs">${t('home.history_see')}</button>`
    : '';
  const body = records.length ? records.map(line) : html`<div class="none">${t('home.none')}</div>`;
  return html`<section class="block wide"><h2>${t('home.history')}${more}</h2><div class="list">${body}</div></section>`;
}
