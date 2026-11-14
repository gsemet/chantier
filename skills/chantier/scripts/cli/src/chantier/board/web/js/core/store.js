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
  panelTree: null, // the open panel's listing: { folder, count, list, failed }
  panelFile: null, // the open panel's file: { path, rel, kind, text, sha256, cut, loading, failed }
  panel: null, // the target (kind, key, title, folder, files, row) whose folder is open, else null
  editing: null, // the panel's Markdown editor: { path, original, draft, base, saving, error }
  autosync: { open: false, busy: false, error: '' }, // the autosync panel: open, a call running, its error
  recomputing: false, // Costs: a recompute was asked and its figure has not arrived
  selection: [], // Triage: the slugs selected
  labelFilter: [], // Triage: the labels that filter the post-its
  journalOpen: false, // Triage: the journal panel is open
  journal: null, // the board's journal since the last rescan: { count, entries }
  pending: [], // Triage: the slugs whose write runs (dimmed until the folder answers)
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
