// The PRs view's own feed: one read of the forge when the view opens, then one every 10 s while the
// page is visible and the batch has a PR that is neither merged nor closed. It stops when every PR
// is done and starts again when a CR gets a PR it has not asked for. A closed batch is read once,
// and the view starts a new feed for each batch it shows. A failed read keeps the last good one
// on screen with the error beside it.
import { prs as ask } from '../core/api.js';
import { snapshot, subscribe, update } from '../core/store.js';

const EVERY_MS = 10000;

const linksOf = (state) =>
  (state.data?.batch?.crs ?? [])
    .map((c) => c.pr)
    .filter(Boolean)
    .sort();

const same = (a, b) => a.length === b.length && a.every((link, i) => link === b[i]);

const visible = () => document.visibilityState === 'visible';

// The answer to show after a read that failed: the last one, with the error.
// With no good read yet, `unread` says the page knows no state at all.
const failed = (last, error) => ({
  rows: [],
  unread: !last,
  ...last,
  error: error.message,
  failed: true,
});

// Start the feed of one batch: `batch` is its id, or null for the batch in 4-batch/ (the server's
// default, which is the newest closed one when none is there). It returns the function that stops it.
export function startFeed(batch = null) {
  const project = snapshot().project;
  const feed = { asked: [], busy: false, stopped: false, once: false };
  const here = () => !feed.stopped && snapshot().project === project;

  async function fetchOnce() {
    try {
      const got = await ask(project, batch);
      if (!here()) return;
      feed.once = Boolean(got.data.closed && !got.data.error); // a closed batch is read once
      update({ prs: got.data });
    } catch (error) {
      if (here()) update({ prs: failed(snapshot().prs, error) });
    }
  }

  async function read() {
    if (feed.busy || feed.stopped) return;
    feed.busy = true;
    feed.asked = linksOf(snapshot());
    await fetchOnce();
    feed.busy = false;
  }

  const tick = () => visible() && !feed.once && !snapshot().prs?.all_done && read();
  // A CR got a PR the last read did not ask for: read now, the page is no longer all done.
  const unsub = subscribe((state) => {
    const open = state.project === project && !batch && !feed.once;
    if (open && !same(feed.asked, linksOf(state)) && visible()) read();
  });
  read();
  const timer = setInterval(tick, EVERY_MS);
  // The page comes back to the front: read again only while a PR is not done.
  document.addEventListener('visibilitychange', tick);
  return () => {
    feed.stopped = true;
    unsub();
    clearInterval(timer);
    document.removeEventListener('visibilitychange', tick);
  };
}
