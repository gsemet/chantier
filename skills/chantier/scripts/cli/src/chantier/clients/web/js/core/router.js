// The address is the state of the page: ?p=<project>&v=<view>&b=<batch> (the batch only on the
// Costs, Batch and PRs views), &t=<tab> (the Batch view's tab, every tab of it), on the PRs view
// &st=<state>&sort=<sort>, on the Dashboard view &dt=<tab>&dr=<range>, on the History view
// &hp=<period>&hd=<YYYY-MM-DD> (each only when not the default), on the Help view &h=<topic> (its
// open topic), and the browser's history.
// With no `t=`, the Batch view opens the tab
// last shown on this device (the preference `batchTab`). With the store, this module is the only one
// that writes the URL. `transport=http` (the HTTP binding, forced) is kept in every address.
import { FILTER_BUCKETS, pref, setPref, snapshot, update } from './store.js';

export const ALL = '*';
const LAST = 'last';
const CHOSEN = 'project';
const rules = { views: ['home'], overview: ['home'], topics: [] };
export const BATCH_VIEWS = ['costs', 'batch', 'prs']; // the views the batch navigator moves through
export const PRS_STATES = ['open', 'draft', 'merged']; // the PRs view's state filter (absent: all)
export const PRS_SORTS = ['opened', 'activity', 'cr']; // its sort (absent: the batch's order)
export const DASH_TABS = ['productivity', 'spending']; // the Dashboard's tabs, the first is the default
export const DASH_RANGES = ['10', '20', 'all']; // its range of closed batches, the first is the default
export const HISTORY_PERIODS = ['day', 'week', 'month']; // the History view's periods, the first is the default
export const TABS = ['kanban', 'graph', 'gantt', 'cards']; // the Batch view's tabs, the first is the default

// A `YYYY-MM-DD` that is a real calendar date.
const isDate = (text) => {
  const found = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text ?? '');
  if (!found) return false;
  const [, y, m, d] = found.map(Number);
  const at = new Date(Date.UTC(y, m - 1, d));
  return at.getUTCFullYear() === y && at.getUTCMonth() === m - 1 && at.getUTCDate() === d;
};

// The views the page knows, those that stay on "All projects" (the registry says which), and the
// Help topics' ids.
export function configure(views, overview, topics = []) {
  Object.assign(rules, { views, overview, topics });
}

// Whether the page has a view of that id (a link to a later view shows only once it is there).
export const knows = (view) => rules.views.includes(view);

const known = (view) => (rules.views.includes(view) ? view : rules.views[0]);

// The last real project (never "All projects"), against the ones the board lists.
const lastOf = (ids) => [pref(LAST), ids[0]].find((id) => ids.includes(id)) ?? null;

// The tab kept on this device: the preference when it is one of the tabs, else the Kanban.
const keptTab = () => (TABS.includes(pref('batchTab')) ? pref('batchTab') : TABS[0]);

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
  const tab =
    view !== 'batch' ? TABS[0] : TABS.includes(asked.get('t')) ? asked.get('t') : keptTab();
  return { project: wanted ?? lastOf(ids), view, batch, tab, st, sort, ...askedKeys(view, asked) };
}

// What the address says for the Dashboard, History and Help views (each only on its own view).
function askedKeys(view, asked) {
  const dash = (key, values) =>
    view === 'dashboard' && values.includes(asked.get(key)) ? asked.get(key) : values[0];
  const hp =
    view === 'history' && HISTORY_PERIODS.includes(asked.get('hp')) ? asked.get('hp') : null;
  const hd = view === 'history' && isDate(asked.get('hd')) ? asked.get('hd') : null;
  const topic = view === 'help' && rules.topics.includes(asked.get('h')) ? asked.get('h') : null;
  return { dt: dash('dt', DASH_TABS), dr: dash('dr', DASH_RANGES), hp, hd, topic };
}

// A view that "All projects" does not show opens on the last real project.
function settle(place) {
  const ids = (snapshot().board?.projects ?? []).map((p) => p.id);
  const next =
    place.project === ALL
      ? { ...place, batch: null, tab: TABS[0], st: null, sort: null, hp: null, hd: null }
      : place;
  if (place.project === ALL && !rules.overview.includes(place.view)) {
    const { dt, dr } = place;
    const tab = place.view === 'batch' ? keptTab() : TABS[0];
    return { ...next, project: lastOf(ids), tab, dt, dr };
  }
  return next;
}

const reset = {
  data: null,
  rev: null,
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
  dashboard: null,
  prsState: null,
  prsSort: null,
  historyPage: null,
  historyPeriod: null,
  historyDate: null,
  journalOpen: false,
  journal: null,
  pending: [],
};

// A change of view closes the file panel (the project's change resets it with the rest).
const closed = { panel: null, panelTree: null, panelFile: null, editing: null };

// What the device keeps: the chosen and last project, and the Batch view's tab when it shows.
function keep({ project, view, tab }) {
  if (project) setPref(CHOSEN, project);
  if (project && project !== ALL) setPref(LAST, project);
  if (view === 'batch') setPref('batchTab', tab ?? TABS[0]);
}

function apply(place) {
  const now = snapshot();
  const moved = place.project !== now.project;
  const turned = place.view !== now.view;
  keep(place);
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
    ...viewState(place),
  });
}

// The Dashboard's, History's and Help's state of a place.
const viewState = ({ dt, dr, hp, hd, topic }) => ({
  dashTab: dt ?? DASH_TABS[0],
  dashRange: dr ?? DASH_RANGES[0],
  historyPeriod: hp ?? null,
  historyDate: hd ?? null,
  helpTopic: topic ?? null,
});

// The dashboard's tab and range in the address, each only when not the default.
function dashQuery(place) {
  if (place.view !== 'dashboard') return {};
  return {
    ...(place.dt && place.dt !== DASH_TABS[0] ? { dt: place.dt } : {}),
    ...(place.dr && place.dr !== DASH_RANGES[0] ? { dr: place.dr } : {}),
  };
}

// The History view's keys of an address: each only when not the default (the day, today).
const historyKeys = (place) => {
  if (place.view !== 'history') return {};
  return {
    ...(place.hp && place.hp !== HISTORY_PERIODS[0] ? { hp: place.hp } : {}),
    ...(place.hd ? { hd: place.hd } : {}),
  };
};

// The Help view's open topic in an address.
const helpKeys = (place) => (place.view === 'help' && place.topic ? { h: place.topic } : {});

// The relative address of a place: it keeps the page's own address in front of the query.
export const href = (place) =>
  `?${new URLSearchParams({
    ...(new URLSearchParams(location.search).get('transport') === 'http'
      ? { transport: 'http' }
      : {}),
    p: place.project ?? '',
    v: place.view ?? 'home',
    ...(place.batch ? { b: place.batch } : {}),
    ...(place.view === 'prs' && place.st ? { st: place.st } : {}),
    ...(place.view === 'prs' && place.sort ? { sort: place.sort } : {}),
    ...historyKeys(place),
    ...helpKeys(place),
    ...(place.view === 'batch' && place.tab ? { t: place.tab } : {}),
    ...dashQuery(place),
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

// The Dashboard's tab and range after a move: the place's own, else the current ones while the
// page stays on the same project's Dashboard, else the defaults (any other view has the defaults).
export function dashOf(place, now, project, view) {
  const same = view === 'dashboard' && now.view === 'dashboard' && project === now.project;
  const keep = (key, held, first) => place[key] ?? (same ? held : first);
  return view === 'dashboard'
    ? { dt: keep('dt', now.dashTab, DASH_TABS[0]), dr: keep('dr', now.dashRange, DASH_RANGES[0]) }
    : { dt: DASH_TABS[0], dr: DASH_RANGES[0] };
}

// The History view's period and date after a move: set by the place (`null` clears), else kept on
// the same project's History view, else cleared. Any other view has none.
export function historyOf(place, now, project, view) {
  if (view !== 'history') return { hp: null, hd: null };
  const keep = (key, held) =>
    place[key] !== undefined ? place[key] : project === now.project ? held : null;
  return { hp: keep('hp', now.historyPeriod), hd: keep('hd', now.historyDate) };
}

// The Batch view's tab after a move: the place's own, else the current one while the page stays on
// the Batch view of the same project (the batch navigator keeps it), else the one kept on this
// device (the Kanban the first time); the first tab on any other view.
export function tabOf(place, now, project, view) {
  if (view !== 'batch') return TABS[0];
  if (place.tab) return place.tab;
  return now.view === 'batch' && project === now.project ? now.batchTab : keptTab();
}

// The Help view's open topic after a move: the place's own (`null` closes; an id the page does not
// know is `null`), else the current one (Help is the same on every project); none on another view.
export function topicOf(place, now, view) {
  if (view !== 'help') return null;
  if (place.topic === undefined) return now.helpTopic;
  return rules.topics.includes(place.topic) ? place.topic : null;
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
    topic: topicOf(place, now, view),
    ...prsOf(place, now, project, view),
    ...dashOf(place, now, project, view),
    ...historyOf(place, now, project, view),
  });
  // A push that opens a Help topic is marked: its Back is a close (`closeTopic`).
  const opens = now.view === 'help' && !now.helpTopic && Boolean(next.topic);
  if (replace) history.replaceState(history.state, '', href(next));
  else history.pushState(opens ? { helpOpen: true } : null, '', href(next));
  here = location.href;
  apply(next);
}

// Close the open Help topic, with no new history entry: a topic opened here from Help is closed by
// Back (its pushed entry is popped, `popstate` re-resolves), one reached by a link closes in place.
export function closeTopic() {
  if (history.state?.helpOpen) history.back();
  else go({ topic: null }, { replace: true });
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
