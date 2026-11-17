// The Costs view: the batch's receipt on the left, and on its right the cards: when the figures
// were computed (the Recompute button), four figures, the batch's CRs by cost, the earlier batches
// and the last merged CRs. The batch shown is the one the navigator chose; by default the running
// one, else the last closed one.
//   render(state) returns the view's markup; mount(root, state) returns a cleanup.

import { delegate, html } from '../core/dom.js';
import { age } from '../core/format.js';
import { href } from '../core/router.js';
import { money, receiptOf } from '../model/receipt.js';
import { t } from '../model/words.js';
import { bindOpen } from '../ui/open.js';
import { empty, kpi, meter } from '../ui/parts.js';
import { recomputeCosts } from './costs-action.js';
import { bindHistory, historyBlock } from './costs-history.js';
import { copyReceipt } from './costs-image.js';
import { lasted, receipt } from './costs-receipt.js';
import { lastMerged, perCr } from './costs-tables.js';

// Whether this page can copy an image: a secure origin, and a browser with the clipboard's `write`.
const canCopy = () =>
  window.isSecureContext &&
  typeof navigator.clipboard?.write === 'function' &&
  typeof ClipboardItem !== 'undefined';

// The 127.0.0.1 address of the same page, when the board gives one.
function localPage(state) {
  const base = state.board?.local_url;
  if (!base) return null;
  const place = { project: state.project, view: state.view, batch: state.batchId };
  return { link: `${base}&${href(place).slice(1)}`, host: new URL(base).host };
}

// The tooltip of the greyed button: a span that wraps it (a disabled button gets no pointer
// events), opened by hover and by focus.
function whyNot(state) {
  if (!window.isSecureContext) {
    const page = localPage(state);
    if (!page) return t('costs.copy_insecure_nolink');
    const [before, after] = t('costs.copy_insecure', { link: '{link}' }).split('{link}');
    return html`${before}<a href="${page.link}">${page.host}</a>${after}`;
  }
  return t('costs.copy_unsupported');
}

function copyButton(state) {
  const busy = state.copying;
  const label = busy ? t('costs.copying') : t('costs.copy_image');
  if (canCopy()) {
    return html`<button class="btn" type="button" data-copy-receipt data-key="copy-receipt" ${busy ? 'disabled' : ''}>${label}</button>`;
  }
  return html`<span class="tipwrap" tabindex="0" data-key="copy-receipt-tip"><button class="btn" type="button" data-copy-receipt data-key="copy-receipt" disabled>${label}</button><span class="tip" role="tooltip">${whyNot(state)}</span></span>`;
}

function ageLine(r, state) {
  if (!r.live) {
    return html`<div class="age"><span>${t('costs.final')}</span>${copyButton(state)}</div>`;
  }
  const busy = r.computing;
  const when = age(state.data.batch.cost_at, state.now);
  const text = when ? t('costs.computed', { age: when }) : t('costs.never');
  const label = busy ? t('costs.recomputing') : t('costs.recompute');
  return html`<div class="age"><span>${text}</span><button class="btn${busy ? '' : ' pri'}" type="button" data-recompute data-key="recompute" ${busy ? 'disabled' : ''}>${label}</button>${copyButton(state)}<span class="note">${t('costs.note')}</span></div>`;
}

// What is outside the budget, in the money words: unknown, a dash, or the amount.
function outsideSub(o) {
  if (o.kind === 'none') return t('costs.outside_sub', { x: '—' });
  const x = o.kind === 'value' ? money(o.usd, o.unpriced) : t('costs.receipt_unknown');
  return t('costs.outside_sub', { x });
}

const REST_MIN = 0.005;
const REST_SUB = { steer: 'costs.rest_steer', agents: 'costs.rest_agents' };

function figures(r) {
  const gauge = r.budget ? meter([{ n: r.total ?? 0, color: 'var(--accent)' }], r.budget) : '';
  const spentSub = t(`costs.spent_${r.stateName}`, { d: lasted(r.minutes) });
  const budget = r.budget ? money(r.budget) : t('costs.receipt_none');
  const rest = r.rest.usd > REST_MIN ? t(REST_SUB[r.rest.kind] ?? 'costs.rest') : '';
  const avg = r.avg == null ? '—' : money(r.avg);
  return html`<div class="kpis">${kpi({ label: t('costs.spent', { batch: r.id }), value: money(r.total, r.unpriced), sub: spentSub, extra: gauge })}${kpi({ label: t('costs.budget'), value: budget, sub: outsideSub(r.outside) })}${kpi({ label: t('costs.sum'), value: money(r.sum), sub: rest })}${kpi({ label: t('costs.avg'), value: avg, sub: t('costs.avg_sub', { n: r.priced }) })}</div>`;
}

// The Per CR table reads the running batch's rows, or a closed record's entries (merged or
// dropped, with their rounds).
function rowsOf(state, r) {
  if (r.live) return state.data.batch;
  const record = state.data.history.find((x) => x.batch === r.id);
  const crs = record.crs.map((c) => ({
    cr: c.cr,
    title: c.title,
    state: c.result === 'merged' ? 'merged' : 'cancelled',
    round: c.rounds,
    cost_usd: c.cost_usd,
  }));
  return { id: r.id, crs };
}

export function render(state) {
  const merged = lastMerged(state.data.merged ?? []);
  const r = receiptOf(state);
  if (!r) {
    return html`<div class="costs">${empty(t('batch.none'))}${historyBlock(state)}${merged}</div>`;
  }
  const side = html`<div class="cside">${ageLine(r, state)}${figures(r)}${perCr(rowsOf(state, r))}${historyBlock(state)}${merged}</div>`;
  return html`<div class="costs"><div class="cwrap">${receipt(r)}${side}</div></div>`;
}

export function mount(root) {
  const offs = [
    delegate(root, 'click', '[data-copy-receipt]', () => copyReceipt(root)),
    bindOpen(root),
    bindHistory(root),
    delegate(root, 'click', '[data-recompute]', () => recomputeCosts()),
  ];
  return () => {
    for (const off of offs) off();
  };
}
