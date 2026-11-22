// The device's Inbox state, kept in the browser's storage through the store (`pref`, `setPref`):
// the hides, when each entry was first seen, which the Inbox page has drawn, and the notification
// switch. Only `hide` and `restore`, the user's clicks, redraw the page with `update()`; `remember`
// and `markShown` write storage only, for they run inside a store listener or a view's `after()`.
import { pref, setPref, snapshot, update } from '../core/store.js';
import { hideUntil, prune } from '../model/inbox.js';

const MARKS = 'inbox.marks';
const FIRST = 'inbox.first';
const SHOWN = 'inbox.shown';
const NOTIFY = 'inbox.notify';

function read(key) {
  try {
    const value = JSON.parse(pref(key) ?? '{}');
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  } catch {
    return {}; // storage is off or holds something else: nothing is remembered
  }
}

function write(key, value) {
  try {
    setPref(key, JSON.stringify(value));
  } catch {
    // storage is off (a private window) or full: the hides last until the page is closed
  }
}

export const loadMarks = () => read(MARKS);

export const notifyOn = () => {
  try {
    return pref(NOTIFY) === '1';
  } catch {
    return false;
  }
};

export function setNotify(on) {
  try {
    setPref(NOTIFY, on ? '1' : '0');
  } catch {
    // storage is off: the switch lasts until the page is closed
  }
}

export function hide(id, how) {
  const inboxMarks = { ...snapshot().inboxMarks, [id]: { how, until: hideUntil(how, Date.now()) } };
  write(MARKS, inboxMarks);
  update({ inboxMarks });
}

export function restore(id) {
  const { [id]: _gone, ...inboxMarks } = snapshot().inboxMarks;
  write(MARKS, inboxMarks);
  update({ inboxMarks });
}

const keep = (map, ids) => Object.fromEntries(Object.entries(map).filter(([id]) => ids.has(id)));

// Record the first sight of each live id, and drop what belongs to an id that is gone. It runs once
// the `board` topic has arrived: an empty first state would otherwise forget everything.
export function remember(liveIds, nowMs) {
  const live = new Set(liveIds);
  const first = read(FIRST);
  const grown = liveIds.filter((id) => !(id in first));
  const kept = keep(first, live);
  if (grown.length || Object.keys(kept).length !== Object.keys(first).length) {
    for (const id of grown) kept[id] = nowMs;
    write(FIRST, kept);
  }
  const marks = prune(snapshot().inboxMarks, liveIds, nowMs);
  if (Object.keys(marks).length !== Object.keys(snapshot().inboxMarks).length) {
    write(MARKS, marks);
    Object.assign(snapshot(), { inboxMarks: marks }); // no listener: the draw in hand is current
  }
  const shown = read(SHOWN);
  const seen = keep(shown, live);
  if (Object.keys(seen).length !== Object.keys(shown).length) write(SHOWN, seen);
}

export const firstSights = () => read(FIRST);

export const isSeen = (id) => id in read(SHOWN);

// The ids the Inbox page has drawn; written only when the set grows.
export function markShown(ids) {
  const shown = read(SHOWN);
  const added = ids.filter((id) => !(id in shown));
  if (!added.length) return;
  for (const id of added) shown[id] = true;
  write(SHOWN, shown);
}
