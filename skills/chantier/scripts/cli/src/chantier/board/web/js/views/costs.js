// The Costs view: when the figures were computed, the Recompute button, four figures, and the
// batch's CRs and the last merged ones by cost.
//   render(state) returns the view's markup; mount(root, state) returns a cleanup.

import { delegate, html } from '../core/dom.js';
import { age, usd } from '../core/format.js';
import { t } from '../model/words.js';
import { bindOpen } from '../ui/open.js';
import { empty, kpi, meter } from '../ui/parts.js';
import { recomputeCosts } from './costs-action.js';
import { lastMerged, perCr } from './costs-tables.js';

const sum = (rows) => rows.reduce((n, c) => n + (c.cost_usd ?? 0), 0);

function ageLine(state) {
  const batch = state.data.batch;
  const busy = state.recomputing || Boolean(state.data.live?.computing);
  const when = age(batch.cost_at, state.now);
  const text = when ? t('costs.computed', { age: when }) : t('costs.never');
  const label = busy ? t('costs.recomputing') : t('costs.recompute');
  return html`<div class="age"><span>${text}</span><button class="btn${busy ? '' : ' pri'}" type="button" data-recompute data-key="recompute" ${busy ? 'disabled' : ''}>${label}</button><span class="note">${t('costs.note')}</span></div>`;
}

function figures(batch) {
  const spent = batch.spent_usd ?? 0;
  const total = sum(batch.crs);
  const priced = batch.crs.filter((c) => c.cost_usd).length;
  const used = batch.budget_usd
    ? t('costs.used', { n: Math.round((spent / batch.budget_usd) * 100) })
    : '—';
  const gauge = meter([{ n: spent, color: 'var(--blue)' }], batch.budget_usd);
  return html`<div class="kpis">${kpi({ label: t('costs.spent', { batch: batch.id }), value: usd(batch.spent_usd), extra: gauge })}${kpi({ label: t('costs.budget'), value: usd(batch.budget_usd), sub: used })}${kpi({ label: t('costs.sum'), value: usd(total), sub: t('costs.rest') })}${kpi({ label: t('costs.avg'), value: usd(total / Math.max(1, priced)), sub: t('costs.avg_sub', { n: priced }) })}</div>`;
}

export function render(state) {
  const batch = state.data.batch;
  if (!batch) return empty(t('batch.none'));
  return html`<div class="costs">${ageLine(state)}${figures(batch)}${perCr(batch)}${lastMerged(state.data.merged ?? [])}</div>`;
}

export function mount(root) {
  const off = bindOpen(root);
  const ask = delegate(root, 'click', '[data-recompute]', () => recomputeCosts());
  return () => {
    off();
    ask();
  };
}
