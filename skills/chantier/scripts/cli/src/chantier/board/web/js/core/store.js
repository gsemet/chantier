// The page's one state, and who listens to it. One object, replaced by patches. With the router,
// this module is the only one that writes the browser's `localStorage`.

const data = {
  board: null, // GET api/board: the projects of the surface, one line each
  project: null, // the id of the project shown, or '*' for All projects
  view: 'home',
  data: null, // GET api/projects/{id}/state: the project's record
  etag: null,
  now: null, // the server's instant, from its last answer
  minute: 0, // the server's minute: a new one redraws the ages
  heard: null, // when the page last read the server (device milliseconds)
  fails: 0, // reads failed in a row
  denied: false, // the board refused the page's key
  menu: false, // the project menu is open
  panel: null, // the key of the CR or item whose folder is open, else null
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

// What the browser keeps between visits.
export const pref = (key) => localStorage.getItem(`chantier.${key}`);

export const setPref = (key, value) => localStorage.setItem(`chantier.${key}`, value);
