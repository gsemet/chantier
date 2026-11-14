// What a click can open in the panel: a CR of the batch or an item of the backlog, found again
// from the key a card carries (`c:CR-12`, `i:slug`). Pure.
import { BUCKETS } from './grill.js';
import { crsOf } from './semantics.js';

export const crKey = (c) => `c:${c.cr}`;

export const itemKey = (item) => `i:${item.item}`;

const ofCr = (row) => ({
  kind: 'cr',
  key: crKey(row),
  title: row.title,
  folder: row.folder,
  files: row.files,
  row,
});

const ofItem = (row, bucket) => ({
  kind: 'item',
  key: itemKey(row),
  bucket,
  title: row.title,
  folder: row.folder,
  files: row.files,
  row,
});

// The target of a key against the project's data, or null when it is gone.
export function targetFor(state, key) {
  const id = key.slice(2);
  if (key.startsWith('c:')) {
    const row = crsOf(state.data?.batch).find((c) => c.cr === id);
    return row ? ofCr(row) : null;
  }
  for (const bucket of BUCKETS) {
    const row = (state.data?.backlog?.[bucket] ?? []).find((i) => i.item === id);
    if (row) return ofItem(row, bucket);
  }
  return null;
}

// Whether a key is the open panel's.
export const isOpenKey = (state, key) => state.panel?.key === key;
