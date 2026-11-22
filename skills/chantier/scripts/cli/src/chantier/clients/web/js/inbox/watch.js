// What the Inbox does with no page of its own open: remembers what the device has seen, raises a
// browser notification for a new entry when the user turned them on, and redraws when a hide ends.
// It reads the store only; it asks the server for nothing.
import { go } from '../core/router.js';
import { snapshot, subscribe, update } from '../core/store.js';
import { EVERY, entriesOf, isHidden } from '../model/inbox.js';
import { t } from '../model/words.js';
import { loadMarks, notifyOn, remember, setNotify } from './marks.js';

const TICK_MS = 30000;

let known = null; // the ids of the previous change (null before the first board)
let board = null;
let looked = Date.now();

// A failed or refused notification: the switch goes off, and the page says so once the listener's
// turn is over (a nested `update()` would redraw inside the draw in hand).
export function blocked() {
  setNotify(false);
  setTimeout(() => update({ inboxNotifyBlocked: true }), 0);
}

function raise(entry) {
  const kind = t(`inbox.kind.${entry.kind}`);
  const note = new Notification(t('inbox.notify_title', { kind, project: entry.project }), {
    body: `${entry.cr ?? entry.item} · ${entry.title}`,
    tag: entry.id,
  });
  note.addEventListener('click', () => {
    window.focus();
    go({ project: entry.project, view: 'inbox' });
    note.close();
  });
}

// The whole notification step is guarded: the constructor throws on some browsers (Android Chrome).
function notify(entries) {
  if (!entries.length || !notifyOn()) return;
  try {
    if (Notification.permission !== 'granted') return;
    for (const entry of entries) raise(entry);
  } catch {
    blocked();
  }
}

function onChange(state) {
  if (!state.board || state.board === board) return;
  board = state.board;
  const entries = entriesOf(board, EVERY);
  const ids = entries.map((e) => e.id);
  const now = Date.now();
  remember(ids, now);
  const fresh = known ? entries.filter((e) => !known.has(e.id)) : [];
  known = new Set(ids);
  notify(fresh.filter((e) => !isHidden(snapshot().inboxMarks[e.id], now)));
}

// A hide that ended since the last look brings its entry back: redraw, with no server event.
function tick() {
  const now = Date.now();
  const ended = Object.values(snapshot().inboxMarks).some(
    (mark) => mark.until && mark.until > looked && mark.until <= now,
  );
  looked = now;
  if (ended) update({ inboxTick: now });
}

export function watchInbox() {
  update({ inboxMarks: loadMarks() });
  subscribe(onChange);
  onChange(snapshot());
  setInterval(tick, TICK_MS);
}
