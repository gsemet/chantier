// Where the money went, for the Costs card, as one plain object. Pure, no DOM.
//   spendBy(r, by) takes the object of `receiptOf` and the switch ('model' or 'role') and returns
//   { state, line, span, budget, over, segments, rows, chief, note }.
// `state` is 'figures', 'unrecorded' (a record with no per-model figures) or 'pending'.
// A row is { key, name, version, provider, calls, usd, unpriced, color }; `unpriced` is true when
// some of its calls have no price, and `usd` is null for a model with none priced at all.
import { usd } from '../core/format.js';
import { parseModel } from './models.js';
import { money, steeringName } from './receipt.js';
import { t } from './words.js';

const PALETTE = 8;
const SHADE = {
  steering: 'var(--accent-dark)',
  drivers: 'var(--accent)',
  workers: 'var(--accent-light)',
  agents: 'var(--accent-light)',
};

const has = (n) => typeof n === 'number' && n > 0;

// The ticket's rule: when agents are not told apart, they stand in place of Drivers and workers.
function parts(split) {
  const agents = split.some((p) => p.part === 'agents');
  return split.filter((p) => !agents || !['drivers', 'workers'].includes(p.part));
}

function modelRows(receipt) {
  return receipt.models.map((m, i) => {
    const none = m.calls === 0 && has(m.unpriced);
    return {
      key: m.model,
      ...parseModel(m.model),
      calls: m.calls,
      usd: none ? null : m.usd,
      unpriced: has(m.unpriced),
      color: `var(--m${(i % PALETTE) + 1})`,
    };
  });
}

function roleRows(receipt) {
  return parts(receipt.split).map((p) => ({
    key: p.part,
    provider: null,
    name:
      p.part === 'steering'
        ? steeringName(receipt.steering.label)
        : t(`costs.receipt_part_${p.part}`),
    version: '',
    calls: p.calls,
    usd: p.usd,
    unpriced: Object.keys(p.unpriced ?? {}).length > 0,
    color: SHADE[p.part],
  }));
}

// The Chief of Staff's spend outside the budget: one row, the same in both views; unknown, never
// $0.00, where it is not measured.
function chiefRow(r) {
  const o = r.outside;
  if (o.kind !== 'value') return { unknown: true };
  const out = r.receipt.outside;
  return {
    unknown: false,
    usd: o.usd,
    calls: [out.grill, out.steering].filter(Boolean).reduce((n, p) => n + p.calls, 0),
    unpriced: Object.keys(o.unpriced ?? {}).length > 0,
    steering: Boolean(out.steering),
  };
}

// The line over the bar, in the board's money words.
function lineOf(r, spent) {
  const flag = r.unpriced ?? {};
  const some = Object.keys(flag).length > 0;
  if (!r.budget) return t('costs.money_nobudget', { x: money(spent, flag) });
  if (spent > r.budget) return t('costs.money_over', { x: money(spent - r.budget, flag) });
  const x = usd(r.budget - spent);
  return t(some ? 'costs.money_left_atmost' : 'costs.money_left', { x });
}

export function spendBy(r, by) {
  const base = { state: r.figures, line: '', span: 0, budget: r.budget, segments: [], rows: [] };
  if (r.figures !== 'figures') return { ...base, note: r.note };
  if (!r.receipt.models) return { ...base, state: 'unrecorded' };
  const rows = by === 'role' ? roleRows(r.receipt) : modelRows(r.receipt);
  const segments = rows.filter((x) => has(x.usd));
  const spent = Math.max(
    r.total ?? 0,
    segments.reduce((n, x) => n + x.usd, 0),
  );
  const over = Boolean(r.budget) && spent > r.budget;
  const span = r.budget && !over ? r.budget : spent;
  return {
    ...base,
    line: lineOf(r, spent),
    span,
    spent,
    over,
    segments,
    rows,
    chief: chiefRow(r),
  };
}
