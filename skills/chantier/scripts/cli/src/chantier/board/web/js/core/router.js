// The address is the state of the page: ?p=<project>&v=<view>&b=<batch> (the batch only on the
// Costs, Batch and PRs views), &t=<tab> (the Batch view's tab, when not the graph), on the PRs view
// &st=<state>&sort=<sort>, and the browser's history. With the store, this module is the only one
// that writes the URL.
import { FILTER_BUCKETS, pref, setPref, snapshot, update } from './store.js';

export const ALL = '*';
const LAST = 'last';
const CHOSEN = 'project';
const rules = { views: ['home'], overview: ['home'] };
export const BATCH_VIEWS = ['costs', 'batch', 'prs']; // the views the batch navigator moves through
export const PRS_STATES = ['open', 'draft', 'merged']; // the PRs view's state filter (absent: all)
export const PRS_SORTS = ['opened', 'activity', 'cr']; // its sort (absent: the batch's order)
export const TABS = ['graph', 'gantt', 'cards']; // the Batch view's tabs, the first is the default

// The views the page knows, and those that stay on "All projects" (the registry says which).
export function configure(views, overview) {
  Object.assign(rules, { views, overview });
}

// Whether the page has a view of that id (a link to a later view shows only once it is there).
export const knows = (view) => rules.views.includes(view);

const known = (view) => (rules.views.includes(view) ? view : rules.views[0]);

// The last real project (never "All projects"), against the ones the board lists.
const lastOf = (ids) => [pref(LAST), ids[0]].find((id) => ids.includes(id)) ?? null;

// Where the address says to be, against the projects the board serves.
export function resolve(projects, search = location.search) {
  const ids = projects.map((p) => p.id);
  const asked = new URLSearchParams(search);
  const many = ids.length > 1;
  const wanted = [asked.get('p'), pref(CHOSEN)].find(
    (id) => ids.includes(id) || (many && id === ALL),
  );
  const view = known(asked.get('v'));
  const batch = BATCH_VIEWS.includes(view) ? asked.get('b') || null : null;
  const only = (key, values) =>
    view === 'prs' && values.includes(asked.get(key)) ? asked.get(key) : null;
  const st = only('st', PRS_STATES);
  const sort = only('sort', PRS_SORTS);
  const tab = view === 'batch' && TABS.includes(asked.get('t')) ? asked.get('t') : TABS[0];
  return { project: wanted ?? lastOf(ids), view, batch, tab, st, sort };
}

// A view that "All projects" does not show opens on the last real project.
function settle(place) {
  const ids = (snapshot().board?.projects ?? []).map((p) => p.id);
  const next =
    place.project === ALL ? { ...place, batch: null, tab: TABS[0], st: null, sort: null } : place;
  if (place.project === ALL && !rules.overview.includes(place.view)) {
    return { ...next, project: lastOf(ids) };
  }
  return next;
}

const reset = {
  data: null,
  etag: null,
  now: null,
  fails: 0,
  panel: null,
  menu: false,
  editing: null,
  selection: [],
  labelFilter: [],
  priorityFilter: [...FILTER_BUCKETS],
  historyOpen: [],
  prs: null,
  prsState: null,
  prsSort: null,
  journalOpen: false,
  journal: null,
  pending: [],
};

// A change of view closes the file panel (the project's change resets it with the rest).
const closed = { panel: null, panelTree: null, panelFile: null, editing: null };

function apply(place) {
  const now = snapshot();
  const moved = place.project !== now.project;
  const turned = place.view !== now.view;
  if (place.project) setPref(CHOSEN, place.project);
  if (place.project && place.project !== ALL) setPref(LAST, place.project);
  const { project, view, batch, tab, st, sort } = place;
  update({
    ...(turned ? closed : {}),
    ...(moved ? reset : {}),
    project,
    view,
    batchId: batch ?? null,
    batchTab: tab ?? TABS[0],
    prsState: st ?? null,
    prsSort: sort ?? null,
  });
}

// The relative address of a place: it keeps the page's own address in front of the query.
export const href = (place) =>
  `?${new URLSearchParams({
    p: place.project ?? '',
    v: place.view ?? 'home',
    ...(place.batch ? { b: place.batch } : {}),
    ...(place.view === 'prs' && place.st ? { st: place.st } : {}),
    ...(place.view === 'prs' && place.sort ? { sort: place.sort } : {}),
    ...(place.tab && place.tab !== TABS[0] ? { t: place.tab } : {}),
  })}`;

// The chosen batch after a move: kept (or set by `place.batch`) between Costs and Batch of the
// same project, cleared by any other view or project. `undefined` keeps the current one; a batch
// the place names (the address read at first load) holds, whatever the page showed before.
export function batchOf(place, now, project, view) {
  if (!BATCH_VIEWS.includes(view)) return null;
  if (place.batch !== undefined) return place.batch;
  return project === now.project ? now.batchId : null;
}

// The PRs view's filter and sort after a move: set by the place, else kept on the same project's
// PRs view (`undefined`), else cleared. Any other view has none.
export function prsOf(place, now, project, view) {
  if (view !== 'prs') return { st: null, sort: null };
  const keep = (key, held) =>
    place[key] !== undefined ? place[key] : project === now.project ? held : null;
  return { st: keep('st', now.prsState), sort: keep('sort', now.prsSort) };
}

// The Batch view's tab after a move: the place's own, else the current one while on the Batch view
// (the batch navigator keeps it); the graph on any other view.
export function tabOf(place, now, project, view) {
  if (view !== 'batch') return TABS[0];
  return place.tab ?? (project === now.project ? now.batchTab : TABS[0]);
}

let here = null; // the address the page last settled on

export function go(place, { replace = false } = {}) {
  const now = snapshot();
  const project = place.project ?? now.project;
  const view = known(place.view ?? now.view);
  const next = settle({
    project,
    view,
    batch: batchOf(place, now, project, view),
    tab: tabOf(place, now, project, view),
    ...prsOf(place, now, project, view),
  });
  if (replace) history.replaceState(null, '', href(next));
  else history.pushState(null, '', href(next));
  here = location.href;
  apply(next);
}

// A guard asked before back or forward leaves the page: it answers true to let it go.
let guard = null;
export const guardLeave = (fn) => {
  guard = fn;
};

// The back and forward buttons. A refused leave puts the address back where it was.
export function listen() {
  here = location.href;
  window.addEventListener('popstate', async () => {
    const board = snapshot().board;
    if (!board) return;
    if (guard && !(await guard())) {
      history.pushState(null, '', here); // here is where the page still is
      return;
    }
    apply(settle(resolve(board.projects)));
    here = location.href;
  });
}
