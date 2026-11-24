// The History view's two filters, applied in the browser to the answer the server gave for the whole
// period (nothing is cut there): the kinds of event (opened, merged, dropped, releases) and, on
// All projects, the projects. Pure: the answer's days, counts and five figures are counted again
// from the events that stay, as the server counts them (the cost is the sum of the ended events'
// cost; it is partial when one has none or has unpriced calls).

// The state chip's variant of each kind of event: no new colour.
export const VARIANT = { merged: 'merged', dropped: 'blocked', opened: 'draft', release: 'ready' };

export const KINDS = ['opened', 'merged', 'dropped', 'releases'];
const ENDING = ['merged', 'dropped', 'release'];

// The answer's key for an event's kind (`release` is counted as `releases`).
export const keyOf = (e) => (e.kind === 'release' ? 'releases' : e.kind);

// What an event adds to the cost: only an ending event has one; it is partial when unpriced.
const spend = (e) =>
  ENDING.includes(e.kind)
    ? {
        usd: e.cost_usd ?? 0,
        partial: e.cost_usd == null || Object.keys(e.cost_unpriced ?? {}).length > 0,
      }
    : { usd: 0, partial: false };

const counts = () => ({ merged: 0, dropped: 0, opened: 0, releases: 0 });

// The answer as the filters show it: `off` holds the hidden `kinds` and `projects`.
export function filtered(answer, off) {
  const total = counts();
  let cost = 0;
  let partial = false;
  const days = [];
  for (const day of answer.days) {
    const items = day.items.filter(
      (e) => !off.kinds.includes(keyOf(e)) && !off.projects.includes(e.project),
    );
    if (!items.length) continue;
    const dayCounts = counts();
    for (const e of items) {
      dayCounts[keyOf(e)] += 1;
      total[keyOf(e)] += 1;
      const spent = spend(e);
      cost += spent.usd;
      partial ||= spent.partial;
    }
    days.push({ ...day, counts: dayCounts, items });
  }
  const totals = { ...total, cost_usd: Math.round(cost * 10000) / 10000, cost_partial: partial };
  return { ...answer, days, totals };
}
