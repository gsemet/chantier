// What a click can open in the panel: a CR of the batch or an item of the backlog, found again
// from the key a card carries (`c:CR-12`, `i:slug`, `m:CR-12` for a merged CR, `h:CR-12` for a CR of the History view). Pure.
import { BUCKETS } from './grill.js';
import { crsOf } from './semantics.js';

export const crKey = (c) => `c:${c.cr}`;

export const itemKey = (item) => `i:${item.item}`;

export const doneKey = (row) => `m:${row.cr}`;

const ofCr = (row) => ({
  kind: 'cr',
  key: crKey(row),
  title: row.title,
  folder: row.folder,
  files: row.files,
  row,
});

// A merged CR: its folder is the row's `path`.
const ofDone = (row) => ({
  kind: 'done',
  key: doneKey(row),
  title: row.title,
  folder: row.path,
  files: undefined,
  row,
});

// A line of the History view whose CR is not in the running batch: its folder is the event's.
// `key` is `h:<CR>`; the first event of that CR that has a folder gives it.
const ofHistory = (state, id) => {
  const events = (state.historyPage?.days ?? []).flatMap((d) => d.items);
  const e = events.find((x) => x.cr === id && x.folder);
  return e
    ? ofDone({
        cr: id,
        title: e.title,
        path: e.folder,
        batch: e.batch,
        cost_usd: e.cost_usd,
        pr: e.pr,
      })
    : null;
};

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
const ofRows = (rows, id, make) => {
  const row = rows.find((r) => r.cr === id);
  return row ? make(row) : null;
};

function itemTarget(state, id) {
  for (const bucket of BUCKETS) {
    const row = (state.data?.backlog?.[bucket] ?? []).find((i) => i.item === id);
    if (row) return ofItem(row, bucket);
  }
  return null;
}

export function targetFor(state, key) {
  const id = key.slice(2);
  if (key.startsWith('m:')) return ofRows(state.data?.merged ?? [], id, ofDone);
  if (key.startsWith('h:')) {
    const found = ofHistory(state, id);
    return found && { ...found, key };
  }
  if (key.startsWith('c:')) return ofRows(crsOf(state.data?.batch), id, ofCr);
  return itemTarget(state, id);
}

// Whether a key is the open panel's.
export const isOpenKey = (state, key) => state.panel?.key === key;
