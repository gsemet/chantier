// The closed batches, from the state's `history` (the batches' own records, newest first). Pure.
//   A back-filled record (an old batch) has its CRs but no date, mode or cost: those read as empty.

// The records of batches that are closed: the running batch has a record too, and is not one.
export const closedBatches = (data) => (data?.history ?? []).filter((r) => r.state === 'closed');

// How many of a record's CRs ended merged, and how many it holds.
export const mergedOf = (record) => (record.crs ?? []).filter((c) => c.result === 'merged').length;

export const totalOf = (record) => (record.crs ?? []).length;

// Whether some CR of the record has no price.
export const hasUnpriced = (record) => Object.keys(record.cost_unpriced ?? {}).length > 0;

// The day of an ISO instant, "2026-11-14", or empty.
export const dayOf = (iso) => (iso ? String(iso).slice(0, 10) : '');

const numberOf = (id) => Number(String(id).match(/\d+/)?.[0] ?? 0);

// The batches the navigator walks, oldest first: every closed record, and the running or paused
// batch. A record that is neither (an abandoned one) is left out. The last id is the latest batch.
export function batchSequence(data) {
  const found = closedBatches(data).map((r) => ({ id: r.batch, n: r.number ?? numberOf(r.batch) }));
  const live = data?.batch?.id;
  if (live && !found.some((x) => x.id === live)) found.push({ id: live, n: numberOf(live) });
  return found.sort((a, b) => a.n - b.n).map((x) => x.id);
}

// The batch the page shows: the chosen one when the sequence holds it, else the latest (or null).
export function shownId(data, chosen) {
  const seq = batchSequence(data);
  return seq.includes(chosen) ? chosen : (seq.at(-1) ?? null);
}

// The closed record that the page shows, or null when it shows the live batch (or none).
export function shownRecord(data, chosen) {
  const id = shownId(data, chosen);
  if (!id || id === data?.batch?.id) return null;
  return closedBatches(data).find((r) => r.batch === id) ?? null;
}

// An archive's folder name, without its `<YYMMDD-HHMM>-` stamp: "253-baseline-and-legacy".
const lastPart = (path) =>
  String(path ?? '')
    .replace(/\/+$/, '')
    .split('/')
    .pop()
    .replace(/^\d{6}-\d{4}-/, '');

// A closed record's CRs as the rows the batch graph reads, by `order` when recorded.
export function recordRows(record) {
  const rows = (record.crs ?? []).map((c, i) => ({
    cr: c.cr,
    title: c.title,
    folder: lastPart(c.archive),
    state: c.result === 'merged' ? 'merged' : 'cancelled',
    round: c.rounds,
    cost_usd: c.cost_usd,
    pr: c.pr,
    after: c.after ?? [],
    order: c.order ?? i,
  }));
  return rows.sort((a, b) => a.order - b.order);
}
