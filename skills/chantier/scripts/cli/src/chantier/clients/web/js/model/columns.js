// What each Triage column and each figure of the header holds, written once: Triage draws the
// columns, the header and Home's In grill tile count them, so the figures cannot drift from the
// columns. Pure.
//   The backlog's items come as `{ item, bucket }`; the batch's CRs and the merged rows as they are.
import { stageOf } from './grill.js';
import { crsOf } from './semantics.js';

export const PRIORITIES = ['P1', 'P2', 'P3', 'P4'];

// The buckets of the backlog that can hold an item being grilled: the inbox and the four priorities.
const FILTERED = ['inbox', ...PRIORITIES];

const PROGRESS = ['blocked', 'working', 'queued'];

const entries = (backlog, buckets) =>
  buckets.flatMap((bucket) => (backlog?.[bucket] ?? []).map((item) => ({ item, bucket })));

const at = (stages) => (x) => stages.includes(stageOf(x.item));

// Inbox: the filed items nobody has started to grill.
export const inboxItems = (backlog) => entries(backlog, ['inbox']).filter(at(['raw']));

// Grill: the items being grilled or specified, from the inbox or the backlog, not yet in 3-ready.
export const grillItems = (backlog) => entries(backlog, FILTERED).filter(at(['grill', 'spec']));

// In progress: the batch's CRs queued, working or blocked.
export const progressCrs = (batch) =>
  PROGRESS.flatMap((s) => crsOf(batch).filter((c) => c.state === s));

// Handed back: the batch's CRs ready, whatever their readiness.
export const handedCrs = (batch) => crsOf(batch).filter((c) => c.state === 'ready');

// How many of the Grill column's items are specified.
export const specifiedCount = (backlog) => grillItems(backlog).filter(at(['spec'])).length;
