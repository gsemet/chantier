// The Dashboard's own feed: a one-shot read of `dashboard.get`, asked again when the project's
// range changes or a closed batch record does (a batch closing, a record corrected afterwards); on
// All projects, any project's.
// There is no `dashboard` topic: the key is built from the closed records the project state already
// carries, so an unrelated push asks nothing. The answer is kept in `state.dashboard` with the
// project and range it was asked for; a failed read keeps the last good answer with the error.
import { dashboard } from '../core/api.js';
import { ALL } from '../core/router.js';
import { snapshot, subscribe, update } from '../core/store.js';
import { closedBatches } from '../model/history.js';

// What a read of the figures depends on beside the range: each closed record's batch, day, cost.
// On All projects it is each project's batch and the digest of its closed records (`closed_rev`,
// on its line of the `board` topic): a batch closing or a record corrected moves it.
const keyOf = (state) => {
  const records =
    state.project === ALL
      ? (state.board?.projects ?? [])
          .map((p) => `${p.id}:${p.batch?.id}:${p.batch?.state}:${p.closed_rev}`)
          .join(',')
      : closedBatches(state.data)
          .map((r) => `${r.batch}:${r.closed}:${r.cost_usd}`)
          .join(',');
  return `${state.dashRange}|${records}`;
};

// The answer to keep after a read that failed: the last good one, with the error beside it.
const failed = (last, error) => ({ ...last, error: error?.message ?? String(error) });

// Start the feed of the project shown; it returns the function that stops it.
export function startFeed() {
  const project = snapshot().project;
  let stopped = false;
  let turn = 0; // an answer that comes back after a later read was asked is dropped
  const here = (mine) => !stopped && snapshot().project === project && mine === turn;
  const ask = async () => {
    const range = snapshot().dashRange;
    const mine = ++turn;
    try {
      const got = await dashboard(project, range);
      if (here(mine)) update({ dashboard: { project, range, answer: got.data, error: null } });
    } catch (error) {
      if (here(mine)) update({ dashboard: failed(snapshot().dashboard, error) });
    }
  };
  let asked = keyOf(snapshot());
  ask();
  const off = subscribe((state) => {
    const key = keyOf(state);
    if (key === asked) return;
    asked = key;
    ask();
  });
  return () => {
    stopped = true;
    off();
  };
}
