// The PRs view's own feed: a subscription to the `prs` topic of one batch. The server reads the
// forge for every client at once, at most every 10 s and only while a PR of the batch is not
// merged or closed. The subscription goes when the page is hidden and comes back when it shows
// again, and the view starts a new feed for each batch it shows. A refused subscription keeps the
// last good answer on screen with the error beside it.
import { snapshot, update } from '../core/store.js';
import { subscribe } from '../core/transport.js';

const visible = () => document.visibilityState === 'visible';

// The answer to show after a read that failed: the last one, with the error.
// With no good read yet, `unread` says the page knows no state at all.
const failed = (last, error) => ({
  rows: [],
  unread: !last,
  ...last,
  error,
  failed: true,
});

// Start the feed of one batch: `batch` is its id, or null for the batch in 4-batch/ (the server's
// default, which is the newest closed one when none is there). It returns the function that stops it.
export function startFeed(batch = null) {
  const project = snapshot().project;
  const args = { project, ...(batch ? { batch } : {}) };
  let stopped = false;
  let off = null;
  const here = () => !stopped && snapshot().project === project;
  const on = () => {
    off ??= subscribe(
      'prs',
      args,
      (data) => here() && update({ prs: data }),
      (error) => here() && update({ prs: failed(snapshot().prs, error) }),
    );
  };
  const sync = () => {
    if (visible()) return on();
    off?.();
    off = null;
    return undefined;
  };
  on();
  document.addEventListener('visibilitychange', sync);
  return () => {
    stopped = true;
    off?.();
    document.removeEventListener('visibilitychange', sync);
  };
}
