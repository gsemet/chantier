// The live refresh: ask the state every 5 s while the page is visible, with the last ETag.
import { AskError, projectState } from './api.js';
import { snapshot, subscribe, update } from './store.js';

const EVERY_MS = 5000;
const FAILS_BEFORE_NOTICE = 2;
let asking = null; // the project being asked, so a slow answer for another one is dropped
let timer = null;

async function ask() {
  const { project, etag } = snapshot();
  if (!project || asking === project) return;
  asking = project;
  try {
    const got = await projectState(project, etag);
    if (snapshot().project !== project) return;
    const patch = { now: got.now ?? snapshot().now, heard: Date.now(), fails: 0, denied: false };
    update(got.changed ? { ...patch, state: got.data, etag: got.etag } : patch);
  } catch (error) {
    if (snapshot().project !== project) return;
    const denied = error instanceof AskError && error.status === 401;
    update({ fails: snapshot().fails + 1, denied });
  } finally {
    asking = null;
  }
}

export const silent = (fails) => fails >= FAILS_BEFORE_NOTICE;

// Start asking: at once, every 5 s while visible, at once again when the page shows again, and
// at once when the project changes.
export function start() {
  let shown = null;
  subscribe((now) => {
    if (now.project !== shown) {
      shown = now.project;
      ask();
    }
  });
  timer = setInterval(() => document.visibilityState === 'visible' && ask(), EVERY_MS);
  document.addEventListener(
    'visibilitychange',
    () => document.visibilityState === 'visible' && ask(),
  );
  return () => clearInterval(timer);
}

export const askNow = ask;
