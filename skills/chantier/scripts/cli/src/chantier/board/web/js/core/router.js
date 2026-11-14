// The address is the state of the page: ?p=<project>&v=<view>, and the browser's history. With
// the store, this module is the only one that writes the URL.
import { pref, setPref, snapshot, update } from './store.js';

export const ALL = '*';
const LAST = 'last';
const CHOSEN = 'project';
const rules = { views: ['home'], overview: ['home'] };

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
  return { project: wanted ?? lastOf(ids), view: known(asked.get('v')) };
}

// A view that "All projects" does not show opens on the last real project.
function settle(place) {
  const ids = (snapshot().board?.projects ?? []).map((p) => p.id);
  if (place.project === ALL && !rules.overview.includes(place.view)) {
    return { ...place, project: lastOf(ids) };
  }
  return place;
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
  journalOpen: false,
  journal: null,
  pending: [],
};

function apply(place) {
  const moved = place.project !== snapshot().project;
  if (place.project) setPref(CHOSEN, place.project);
  if (place.project && place.project !== ALL) setPref(LAST, place.project);
  update({ ...place, ...(moved ? reset : {}) });
}

// The relative address of a place: it keeps the page's own address in front of the query.
export const href = (place) =>
  `?${new URLSearchParams({ p: place.project ?? '', v: place.view ?? 'home' })}`;

let here = null; // the address the page last settled on

export function go(place, { replace = false } = {}) {
  const now = snapshot();
  const next = settle({
    project: place.project ?? now.project,
    view: known(place.view ?? now.view),
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
