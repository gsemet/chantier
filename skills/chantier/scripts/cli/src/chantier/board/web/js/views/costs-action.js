// The Recompute button's work: ask the server to read the transcripts again, wait until it has
// the figure, then read the project again so every view shows it. No agent turn is involved.
import { projectState, recompute } from '../core/api.js';
import { snapshot, update } from '../core/store.js';
import { subscribe } from '../core/transport.js';
import { withLive } from '../model/live.js';

const WAIT_MS = 90000;
const visible = () => document.visibilityState === 'visible';

// The Costs view's feed: a subscription to the `costs` topic of the project shown, laid over the
// store's data (`live`), dropped when the page is hidden and taken again when it shows. It returns
// the function that stops it.
export function watchCosts() {
  const project = snapshot().project;
  let off = null;
  const lay = (data) => {
    const now = snapshot();
    if (now.project === project && now.data) {
      update({ data: withLive({ ...now.data, live: data.live }) });
    }
  };
  const sync = () => {
    if (visible()) {
      off ??= subscribe('costs', { project }, lay);
      return;
    }
    off?.();
    off = null;
  };
  sync();
  document.addEventListener('visibilitychange', sync);
  return () => {
    off?.();
    document.removeEventListener('visibilitychange', sync);
  };
}

// Wait for the server to finish its computing, on the `costs` topic, within a minute and a half.
const untilDone = (project) =>
  new Promise((resolve) => {
    let off = () => {};
    const done = () => {
      clearTimeout(timer);
      off();
      resolve();
    };
    const timer = setTimeout(done, WAIT_MS);
    off = subscribe('costs', { project }, (data) => data.live?.computing || done(), done);
  });

export async function recomputeCosts() {
  const { project, recomputing } = snapshot();
  if (recomputing) return;
  update({ recomputing: true });
  try {
    await recompute(project);
    await untilDone(project);
    const got = await projectState(project);
    update({ data: withLive(got.data), rev: got.rev, now: got.now ?? snapshot().now });
  } finally {
    update({ recomputing: false });
  }
}
