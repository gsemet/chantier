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
