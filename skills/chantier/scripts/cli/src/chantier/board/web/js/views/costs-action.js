// The Recompute button's work: ask the server to read the transcripts again, wait until it has
// the figure, then read the project again so every view shows it. No agent turn is involved.
import { costs, projectState, recompute } from '../core/api.js';
import { snapshot, update } from '../core/store.js';
import { withLive } from '../model/live.js';

const POLL_MS = 1500;
const POLL_MAX = 60;

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Wait for the server to finish its computing, within a minute and a half.
async function untilDone(project) {
  for (let i = 0; i < POLL_MAX; i += 1) {
    await pause(POLL_MS);
    const got = await costs(project);
    if (!got.data.live?.computing) return;
  }
}

export async function recomputeCosts() {
  const { project, recomputing } = snapshot();
  if (recomputing) return;
  update({ recomputing: true });
  try {
    await recompute(project);
    await untilDone(project);
    const got = await projectState(project, null);
    update({ data: withLive(got.data), etag: got.etag, now: got.now ?? snapshot().now });
  } finally {
    update({ recomputing: false });
  }
}
