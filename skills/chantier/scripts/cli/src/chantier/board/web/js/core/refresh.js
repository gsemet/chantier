// The live refresh: read the board and the shown project every 5 s while the page is visible. The
// project is read with its last ETag, so an unchanged record costs a 304 and no redraw.
import { AskError, board, projectState } from './api.js';
import { ALL } from './router.js';
import { snapshot, subscribe, update } from './store.js';

const EVERY_MS = 5000;
const MINUTE_MS = 60000;
const FAILS_BEFORE_NOTICE = 2;
let busy = null; // the project being read, so a slow answer never blocks another project

export const unreachable = (fails) => fails >= FAILS_BEFORE_NOTICE;

const minuteOf = (iso) => Math.floor(Date.parse(iso) / MINUTE_MS) || 0;

// The patch a successful read brings: the clock always, the data only when it changed.
const clock = (got) => {
  const now = got.now ?? snapshot().now;
  return { now, minute: minuteOf(now), heard: Date.now(), fails: 0, denied: false };
};

const lines = (b) => JSON.stringify(b?.projects ?? []);

async function readBoard() {
  const got = await board();
  const same = lines(snapshot().board) === lines(got.data);
  return { ...clock(got), ...(same ? {} : { board: got.data }) };
}

async function readProject(project) {
  const got = await projectState(project, snapshot().etag);
  if (!got.changed) return clock(got);
  return { ...clock(got), data: got.data, etag: got.etag };
}

async function ask() {
  const { project } = snapshot();
  if (!project || busy === project) return;
  busy = project;
  try {
    const patch = await readBoard();
    const more = project === ALL ? {} : await readProject(project);
    if (snapshot().project === project) update({ ...patch, ...more });
  } catch (error) {
    const denied = error instanceof AskError && error.status === 401;
    if (snapshot().project === project) update({ fails: snapshot().fails + 1, denied });
  } finally {
    if (busy === project) busy = null;
  }
}

// Start asking: at once, every 5 s while visible, at once again when the page shows again, and
// at once when the project changes. It returns the function that stops it.
export function start() {
  let shown = null;
  const stop = subscribe((now) => {
    if (now.project === shown) return;
    shown = now.project;
    ask();
  });
  const timer = setInterval(() => document.visibilityState === 'visible' && ask(), EVERY_MS);
  const wake = () => document.visibilityState === 'visible' && ask();
  document.addEventListener('visibilitychange', wake);
  return () => {
    stop();
    clearInterval(timer);
    document.removeEventListener('visibilitychange', wake);
  };
}
