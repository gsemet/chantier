// The Inbox's rules on plain data: which entries a scope holds, which are hidden, when a hide ends.
// Pure: no page, no store, no storage, no words (the device's marks are read by `inbox/marks.js`).
//   an entry: what the `board` topic's `needs_you` gives, plus `project`, `forge` and `id`
//   a mark: `{ how, until }`, how being `snooze`, `later` or `discard`; `until` null for a discard

export const HOUR_MS = 3600000;
export const LATER_HOUR = 8;
export const KINDS = ['question', 'approval', 'merge', 'blocked'];
export const EVERY = '*'; // the scope "All projects"

export const idOf = (project, entry) => `${project}|${entry.key}`;

// The instant a hide taken at `nowMs` ends: an hour on, the next 08:00 of the device's clock, or
// never (a discard lasts while its fact does).
export function hideUntil(how, nowMs) {
  if (how === 'snooze') return nowMs + HOUR_MS;
  if (how !== 'later') return null;
  const at = new Date(nowMs);
  at.setHours(LATER_HOUR, 0, 0, 0);
  if (at.getTime() <= nowMs) at.setDate(at.getDate() + 1);
  at.setHours(LATER_HOUR, 0, 0, 0);
  return at.getTime();
}

export const isHidden = (mark, nowMs) =>
  Boolean(mark) && (mark.how === 'discard' || Number(mark.until) > nowMs);

// An entry's place in time: its own `since`, else when this device first saw it, else the oldest.
const timeOf = (entry, first) => {
  const own = Date.parse(entry.since ?? '');
  if (!Number.isNaN(own)) return own;
  return first[entry.id] ?? Number.NEGATIVE_INFINITY;
};

const newest = (first) => (a, b) =>
  timeOf(b, first) - timeOf(a, first) || (a.key < b.key ? -1 : Number(a.key > b.key));

// The entries of the scope shown: one project's line, or every line on `*`, newest first.
export function entriesOf(board, project, first = {}) {
  const lines = (board?.projects ?? []).filter((l) => project === EVERY || l.id === project);
  const out = lines.flatMap((line) =>
    (line.needs_you ?? []).map((e) => ({
      ...e,
      project: line.id,
      forge: line.forge,
      id: idOf(line.id, e),
    })),
  );
  return out.sort(newest(first));
}

export function split(entries, marks, nowMs) {
  const hidden = entries.filter((e) => isHidden(marks[e.id], nowMs));
  return { shown: entries.filter((e) => !hidden.includes(e)), hidden };
}

// The marks that still hide an entry that still exists.
export function prune(marks, liveIds, nowMs) {
  const live = new Set(liveIds);
  return Object.fromEntries(
    Object.entries(marks).filter(([id, mark]) => live.has(id) && isHidden(mark, nowMs)),
  );
}
