// The page's state, and who listens to it. One object, replaced by patches.

const data = {
  board: null, // GET /api/board
  project: null, // the id of the project shown
  view: 'home',
  state: null, // GET /api/projects/{id}/state
  etag: null,
  now: null, // the server's instant, from its last answer
  heard: null, // when the page last heard from it (device milliseconds)
  fails: 0, // asks failed in a row
  denied: false, // the board refused the page's key
};
const listeners = new Set();

export const snapshot = () => data;

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function update(patch) {
  Object.assign(data, patch);
  for (const listener of listeners) listener(data);
}
