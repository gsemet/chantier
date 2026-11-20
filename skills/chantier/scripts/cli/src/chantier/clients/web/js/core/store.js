// The page's one state, and who listens to it. One object, replaced by patches. With the router,
// this module is the only one that writes the browser's `localStorage`.

// The buckets the Kanban's priority filter toggles: the inbox and the four priorities.
export const FILTER_BUCKETS = ['inbox', 'P1', 'P2', 'P3', 'P4'];

const data = {
  board: null, // the `board` topic: the projects of the surface, one line each
  project: null, // the id of the project shown, or '*' for All projects
  view: 'home',
  batchId: null, // Costs and Batch: the batch the navigator chose (its id), or null for the latest
  batchTab: 'graph', // Batch: the open tab, `graph`, `gantt` or `cards` (the address's `t=`)
  data: null, // the `project` topic: the project's record
  rev: null, // the record's revision, as the server names it
  now: null, // the server's instant, from its last answer
  minute: 0, // the server's minute: a new one redraws the ages
  heard: null, // when the page last heard the server, a tick included (device milliseconds)
  mode: 'live', // the connection: 'live' (a WebSocket) or 'http' (the long-poll)
  upgraded: false, // the server speaks another protocol: reload the page
  fails: 0, // failed reconnects or polls in a row
  denied: false, // the board refused the page's key
  menu: false, // the project menu is open
  panelTree: null, // the open panel's listing: { folder, count, list, failed }
  panelFile: null, // the open panel's file: { path, rel, kind, text, sha256, cut, loading, failed }
  panel: null, // the target (kind, key, title, folder, files, row) whose folder is open, else null
  editing: null, // the panel's Markdown editor: { path, original, draft, base, saving, error }
  writer: { open: false, busy: false, error: '' }, // the writer panel: open, a call running, its error
  prsState: null, // PRs: the state filter ('open', 'draft', 'merged'), null for all
  prsSort: null, // PRs: the sort ('opened', 'activity', 'cr'), null for the batch's order
  prs: null, // PRs: the `prs` topic's last value, kept across a failed read
  copying: false, // Costs: the receipt is being copied as an image
  recomputing: false, // Costs: a recompute was asked and its figure has not arrived
  spendBy: 'model', // Costs: the card's switch, by 'model' or by 'role'
  selection: [], // Triage: the slugs selected
  labelFilter: [], // Triage: the labels that filter the post-its
  priorityFilter: [...FILTER_BUCKETS], // Kanban: the buckets shown (all on at the start)
  historyOpen: [], // Costs: the earlier batches whose CRs are unfolded
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
