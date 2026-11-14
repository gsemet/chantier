// What Triage shows, worked out from the record. Pure: no DOM, no fetch. A column is a folder of the
// backlog (`inbox`, `P1`..`P4`, `3-ready`, the record's own names); a group is the post-its of one
// column that carry the same group name; a label filter keeps the post-its that carry any label.
import { isSpecified, stageOf, tally } from './grill.js';

export const READY = '3-ready';
export const LANES = ['P1', 'P2', 'P3', 'P4'];
export const COLUMNS = ['inbox', ...LANES, READY];

// The colour dot of each column (a token).
export const DOTS = {
  inbox: 'var(--grey)',
  P1: 'var(--red)',
  P2: 'var(--amber)',
  P3: 'var(--blue)',
  P4: 'var(--grey)',
  [READY]: 'var(--green)',
};

const LABEL_COLORS = 6;

export const itemsIn = (backlog, column) => backlog?.[column] ?? [];

// The column an item is in, or null.
export const columnOf = (backlog, slug) =>
  COLUMNS.find((c) => itemsIn(backlog, c).some((i) => i.item === slug)) ?? null;

export const allItems = (backlog) => COLUMNS.flatMap((c) => itemsIn(backlog, c));

export const findItem = (backlog, slug) => allItems(backlog).find((i) => i.item === slug) ?? null;

// The items that carry a group name.
export const membersOf = (backlog, name) => allItems(backlog).filter((i) => i.group === name);

// The labels of the whole project, sorted: a label's colour is its place in this list.
export const labelsOf = (backlog) =>
  [...new Set(allItems(backlog).flatMap((i) => i.labels ?? []))].sort();

export const labelColor = (all, label) => Math.max(0, all.indexOf(label)) % LABEL_COLORS;

// Whether an item shows under a filter: no filter shows everything.
export const passes = (item, filter) =>
  !filter.length || (item.labels ?? []).some((l) => filter.includes(l));

// The items of a column that pass the filter.
export const shownIn = (backlog, column, filter) =>
  itemsIn(backlog, column).filter((i) => passes(i, filter));

// The groups of a list of items, in the order they first appear, and the items with no group.
export function groupsIn(items) {
  const byName = new Map();
  const loose = [];
  for (const item of items) {
    if (!item.group) loose.push(item);
    else byName.set(item.group, [...(byName.get(item.group) ?? []), item]);
  }
  return { groups: [...byName].map(([name, members]) => ({ name, members })), loose };
}

// Every group name of the project (the default name of a new one counts them).
export const groupNames = (backlog) =>
  new Set(allItems(backlog).flatMap((i) => (i.group ? [i.group] : [])));

// The counts by grill state of a list of items, for a column's header.
export const stateCounts = (items) => tally(items);

// "N specified, M automatable": the foot of 3-ready.
export function readyCounts(items) {
  const auto = items.filter((i) => !isSpecified(i) || stageOf(i) === 'auto').length;
  return { total: items.length, auto, specified: items.length - auto };
}

const sameList = (a, b) => a.length === b.length && a.every((slug, i) => slug === b[i]);

// The next-batch indicator, from the marker the user wrote and the CRs now in 3-ready:
// declared (the marker's list is 3-ready's), changed (it differs, one of its CRs is still there),
// preparing (no marker, or none of its CRs is in 3-ready any more: a batch took them).
export function indicator(marker, ready) {
  const slugs = ready.map((i) => i.item).sort();
  const base = { n: slugs.length, at: marker?.declared_at ?? null };
  if (!marker) return { kind: 'preparing', ...base };
  const listed = [...(marker.crs ?? [])].sort();
  if (sameList(listed, slugs)) return { kind: 'declared', ...base, n: listed.length };
  return { kind: listed.some((s) => slugs.includes(s)) ? 'changed' : 'preparing', ...base };
}

// The slugs the journal names since the last rescan: their post-it carries the "modified" mark.
export const modifiedSlugs = (entries) => new Set((entries ?? []).flatMap((e) => e.items ?? []));
