// The History view's own feed: a subscription to the `history` topic for one period of one project.
// The server answers in the browser's time zone and pushes again only when the period's answer
// changes (a CR merged while the page shows today appears without a reload). The subscription goes
// when the page is hidden and comes back when it shows again, and the view starts a new feed for
// each period it shows. A refused read keeps the last good answer on screen with the error beside
// it.
import { snapshot, update } from '../core/store.js';
import { subscribe } from '../core/transport.js';

const visible = () => document.visibilityState === 'visible';

// The browser's IANA time zone, what the server counts the local day in.
export const zone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

// What a feed is told: the project (or All), the period and the date (null: today). The answer is
// kept with it, so a change of project shows no answer of the other.
export const askedKey = (project, period, date) => `${project ?? ''}|${period}|${date ?? ''}`;

// The answer to show after a read that failed: the last one, with the error.
// With no good read yet, `unread` says the page knows no answer at all.
const failed = (last, error) => ({ unread: !last, ...last, error, failed: true });

// Start the feed of one period: `period` is day, week or month, `date` a YYYY-MM-DD or null (today).
// It returns the function that stops it.
export function startFeed(period, date = null) {
  const project = snapshot().project;
  const key = askedKey(project, period, date);
  const args = { project, period, ...(date ? { date } : {}), tz: zone() };
  let stopped = false;
  let off = null;
  const here = () => !stopped && snapshot().project === project;
  const on = () => {
    off ??= subscribe(
      'history',
      args,
      (data) => here() && update({ historyPage: { ...data, asked: key } }),
      (error) =>
        here() && update({ historyPage: { ...failed(snapshot().historyPage, error), asked: key } }),
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
