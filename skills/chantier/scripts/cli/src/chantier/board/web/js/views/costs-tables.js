// The Costs tables: the batch's CRs by cost, and the last merged CRs. Each cost has a bar.
import { html, vars } from '../core/dom.js';
import { percent, slug, title, usd } from '../core/format.js';
import { roundText } from '../model/semantics.js';
import { crKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { opener } from '../ui/open.js';
import { stateTag } from '../ui/parts.js';

const bar = (n, whole, color) =>
  html`<div class="hbar" data-vars="${vars({ '--w': `${percent(n, whole)}%`, '--c': color })}"></div>`;

const head = (cells) =>
  html`<thead><tr>${cells.map(([word, cls]) => html`<th class="${cls}">${word ? t(word) : ''}</th>`)}</tr></thead>`;

const byCost = (a, b) => (b.cost_usd ?? 0) - (a.cost_usd ?? 0);

function crRow(c, batch, top) {
  const round = c.round ? html` <span class="mut">r${roundText(c, batch)}</span>` : '';
  return html`<tr class="click" ${opener(crKey(c), 'cost-')}><td><b>${c.cr}</b> <span class="mut">${slug(c.folder)}</span></td><td class="hide-phone">${title(c.title)}</td><td>${stateTag(c)}${round}</td><td class="num">${usd(c.cost_usd)}</td><td class="hide-phone">${bar(c.cost_usd ?? 0, top, 'var(--blue)')}</td></tr>`;
}

export function perCr(batch) {
  const rows = [...batch.crs].sort(byCost);
  const top = Math.max(0.01, ...rows.map((c) => c.cost_usd ?? 0));
  const cells = [
    ['costs.th_cr', ''],
    ['costs.th_title', 'hide-phone'],
    ['costs.th_state', ''],
    ['costs.th_cost', 'num'],
    ['', 'hide-phone bar'],
  ];
  return html`<h2 class="h2t">${t('costs.per_cr', { batch: batch.id })}</h2><div class="tbl"><table>${head(cells)}<tbody>${rows.map((c) => crRow(c, batch, top))}</tbody></table></div>`;
}

function mergedRow(m, top) {
  return html`<tr><td><b>${m.cr}</b></td><td class="hide-phone">${title(m.title)}</td><td>${m.batch ?? ''}</td><td class="num">${usd(m.cost_usd)}</td><td class="hide-phone">${bar(m.cost_usd ?? 0, top, 'var(--green)')}</td></tr>`;
}

export function lastMerged(merged) {
  const top = Math.max(0.01, ...merged.map((m) => m.cost_usd ?? 0));
  const cells = [
    ['costs.th_cr', ''],
    ['costs.th_title', 'hide-phone'],
    ['costs.th_batch', ''],
    ['costs.th_cost', 'num'],
    ['', 'hide-phone bar'],
  ];
  return html`<h2 class="h2t">${t('costs.last_merged')}</h2><div class="tbl"><table>${head(cells)}<tbody>${merged.map((m) => mergedRow(m, top))}</tbody></table></div>`;
}
