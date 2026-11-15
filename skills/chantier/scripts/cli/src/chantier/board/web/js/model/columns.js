// What each Kanban column holds, written once: the Kanban draws the columns, the header and Home's
// In grill tile count them, so the figures cannot drift from the columns. Pure.
//   The backlog's items come as `{ item, bucket }`; the batch's CRs and the merged rows as they are.
import { FILTER_BUCKETS } from '../core/store.js';
import { stageOf } from './grill.js';
import { crsOf } from './semantics.js';
import { passes } from './triage.js';

export const PRIORITIES = ['P1', 'P2', 'P3', 'P4'];

// The buckets the priority filter toggles: the inbox and the four priorities.
export const FILTERED = FILTER_BUCKETS;

// The Done column draws this many of the newest merged CRs; its count is the merged total.
export const DONE_SHOWN = 20;

const PROGRESS = ['blocked', 'working', 'queued'];

const entries = (backlog, buckets) =>
  buckets.flatMap((bucket) => (backlog?.[bucket] ?? []).map((item) => ({ item, bucket })));

const at = (stages) => (x) => stages.includes(stageOf(x.item));

// Inbox: the filed items nobody has started to grill.
export const inboxItems = (backlog) => entries(backlog, ['inbox']).filter(at(['raw']));

// Backlog: the prioritised items nobody has started to grill.
export const backlogItems = (backlog) => entries(backlog, PRIORITIES).filter(at(['raw']));

// Grill: the items being grilled or specified, from the inbox or the backlog, not yet in 3-ready.
export const grillItems = (backlog) => entries(backlog, FILTERED).filter(at(['grill', 'spec']));

// 3-ready: what waits for the next batch.
export const readyItems = (backlog) => entries(backlog, ['3-ready']);

// In progress: the batch's CRs queued, working or blocked.
export const progressCrs = (batch) =>
  PROGRESS.flatMap((s) => crsOf(batch).filter((c) => c.state === s));

// Handed back: the batch's CRs ready, whatever their readiness.
export const handedCrs = (batch) => crsOf(batch).filter((c) => c.state === 'ready');

// Done: the newest merged CRs the column draws, and how many it leaves out.
export const doneRows = (data) => (data.merged ?? []).slice(0, DONE_SHOWN);

export const doneMore = (data) => Math.max(0, (data.merged_total ?? 0) - doneRows(data).length);

// How many of the Grill column's items are specified.
export const specifiedCount = (backlog) => grillItems(backlog).filter(at(['spec'])).length;

// The entries that pass the page's two filters: their bucket is on (3-ready has no toggle: it is
// never hidden), and they carry a chosen label.
export const visible = (list, priorities, labels) =>
  list.filter(
    (x) =>
      (!FILTERED.includes(x.bucket) || priorities.includes(x.bucket)) && passes(x.item, labels),
  );
