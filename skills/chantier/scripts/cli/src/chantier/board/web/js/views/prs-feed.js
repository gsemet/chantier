// The PRs view's own feed: one read of the forge when the view opens, then one every 10 s while the
// page is visible and the batch has a PR that is neither merged nor closed. It stops when every PR
// is done and starts again when a CR gets a PR it has not asked for. A failed read keeps the last
// good one on screen with the error beside it. The rules are the machine's (prs-feed-machine.js);
// this adapter only feeds it the page's facts and writes its answers in the store.
import { prs as ask } from '../core/api.js';
import { snapshot, subscribe, update } from '../core/store.js';
import { createActor, createAsyncLogic } from '../vendor/xstate.js';
import { feedMachine } from './prs-feed-machine.js';

const linksOf = (state) =>
  (state.data?.batch?.crs ?? [])
    .map((c) => c.pr)
    .filter(Boolean)
    .sort();

const visible = () => document.visibilityState === 'visible';

// Start the feed; it returns the function that stops it.
export function startFeed() {
  const project = snapshot().project;
  const readPrs = createAsyncLogic({
    run: async ({ input }) => (await ask(input.project)).data,
  });
  const actor = createActor(feedMachine.provide({ actors: { readPrs } }), {
    input: { project, visible: visible(), links: linksOf(snapshot()), prs: snapshot().prs },
  });
  actor.on('prs', (event) => {
    if (snapshot().project === project) update({ prs: event.prs });
  });
  const unsub = subscribe((state) => {
    if (state.project === project) actor.send({ type: 'links', links: linksOf(state) });
  });
  const wake = () => actor.send({ type: visible() ? 'shown' : 'hidden' });
  document.addEventListener('visibilitychange', wake);
  actor.start();
  return () => {
    unsub();
    document.removeEventListener('visibilitychange', wake);
    actor.stop();
  };
}
