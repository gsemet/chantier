// The Costs receipt, as one plain object built from the page's data. Pure, no DOM.
//   receiptOf(state) is null when there is no batch to show (no batch runs, no closed record).
// The batch shown is the one the navigator chose; by default the running or paused one, else the
// newest closed record (`data.history`).
// `figures` says which of three receipts it is: the figures are there ('figures'), a running or
// paused batch has no usable live figure ('pending'), a closed record predates `cost_receipt`
// ('unrecorded').

import { usd } from '../core/format.js';
import { closedBatches } from './history.js';
import { t } from './words.js';

const MINUTE_MS = 60000;
const CENT = 0.005;
const PERCENT = 100;

// A figure in the board's money words: "at least $X" with calls not priced, "—" when missing.
export function money(amount, unpriced = {}) {
  const text = usd(amount);
  return amount != null && Object.keys(unpriced ?? {}).length
    ? t('costs.receipt_atleast', { x: text })
    : text;
}

const costOf = (c) => c.cost_usd ?? 0;
const byCost = (a, b) => costOf(b) - costOf(a);

// The Driver type without a `<plugin>:` prefix.
export const driverName = (type) => String(type ?? '').replace(/^[^:]*:/, '');

// The steering session's name: the label up to its first comma.
export const steeringName = (label) => String(label ?? '').split(',')[0];

// The chosen closed record; with none chosen (or an unknown id, or the live batch's), the running
// batch, else the newest closed record, as { live, rec }; null with neither.
export function shownBatch(data, chosen = null) {
  const picked =
    chosen && chosen !== data?.batch?.id
      ? closedBatches(data).find((r) => r.batch === chosen)
      : null;
  if (picked) return { live: false, rec: picked };
  if (data?.batch) return { live: true, rec: data.batch };
  const closed = (data?.history ?? []).find((r) => r.state === 'closed');
  return closed ? { live: false, rec: closed } : null;
}

function figuresCase(shown, data) {
  if (!shown.live) return shown.rec.cost_receipt ? 'figures' : 'unrecorded';
  return shown.rec.cost_receipt && !data.live?.error ? 'figures' : 'pending';
}

function crLines(rec, live) {
  return (rec.crs ?? []).map((c) => ({
    cr: c.cr,
    title: c.title,
    usd: c.cost_usd ?? null,
    unpriced: c.cost_unpriced ?? {},
    merged: live ? c.state === 'merged' : c.result === 'merged',
    pr: Boolean(c.pr),
  }));
}

// Where the rest of the total went: the steering part of the receipt, the remainder, or both.
function restOf(total, sum, receipt) {
  const usdRest = total - sum;
  if (!receipt) return { usd: usdRest, kind: 'any' };
  const steer = Math.min(usdRest, receipt.steering?.usd ?? 0);
  const other = usdRest - steer;
  if (steer > CENT && other > CENT) return { usd: usdRest, kind: 'both', steer, other };
  return { usd: usdRest, kind: steer > CENT ? 'steer' : 'agents' };
}

const unpricedOf = (...parts) => Object.assign({}, ...parts.map((p) => p?.unpriced ?? {}));

// The Outside-the-budget cell: the grill and the specifications, the steering in a Foreman batch.
function outsideOf(receipt, figures) {
  if (figures !== 'figures') return { kind: 'none' };
  const out = receipt.outside;
  if (!out) return { kind: 'unknown', cause: receipt.outside_unknown };
  const parts = [out.grill, out.steering].filter(Boolean);
  if (parts.some((p) => p.usd == null)) return { kind: 'unknown', cause: null, out };
  const sum = parts.reduce((n, p) => n + p.usd, 0);
  return { kind: 'value', usd: sum, unpriced: unpricedOf(...parts), out };
}

// The batch's length in minutes; null when a date is missing (an old record).
function minutesOf(from, to) {
  const span = Date.parse(to ?? '') - Date.parse(from ?? '');
  return Number.isFinite(span) ? Math.max(0, Math.round(span / MINUTE_MS)) : null;
}

function headOf(shown, state) {
  const { rec, live } = shown;
  const name = live ? rec.state : 'closed';
  return {
    id: live ? rec.id : rec.batch,
    stateName: name,
    mode: rec.mode,
    steering: rec.steering,
    opened: live ? rec.created : rec.opened,
    closed: live ? null : rec.closed,
    minutes: minutesOf(live ? rec.created : rec.opened, live ? state.now : rec.closed),
  };
}

function countsOf(crs, total, sum) {
  const priced = crs.filter((c) => c.usd).length;
  return {
    avg: total == null ? null : sum / Math.max(1, priced),
    priced,
    merged: crs.filter((c) => c.merged).length,
    prs: crs.filter((c) => c.merged && c.pr).length,
  };
}

export function receiptOf(state) {
  const data = state.data;
  const shown = shownBatch(data, state.batchId);
  if (!shown) return null;
  const { rec, live } = shown;
  const crs = crLines(rec, live).sort(byCost);
  const total = live ? rec.spent_usd : rec.cost_usd;
  const sum = crs.reduce((n, c) => n + (c.usd ?? 0), 0);
  const figures = figuresCase(shown, data);
  const receipt = figures === 'figures' ? rec.cost_receipt : null;
  const budget = rec.budget_usd ?? null;
  return {
    ...headOf(shown, state),
    live,
    project: state.project,
    figures,
    note: data.live?.error ?? null,
    computing: Boolean(state.recomputing || data.live?.computing),
    receipt,
    total,
    unpriced: live ? rec.unpriced : rec.cost_unpriced,
    budget,
    used: budget && total != null ? Math.round((total / budget) * PERCENT) : null,
    crs,
    sum,
    ...countsOf(crs, total, sum),
    rest: restOf(total ?? 0, sum, receipt),
    outside: outsideOf(receipt, figures),
  };
}
