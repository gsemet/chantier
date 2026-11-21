// The views, in the order the sidebar lists them. An entry: its id (the `v=` of the address), its
// icon, its word, the module that draws it on a project, and, if it also shows on "All projects",
// the module that draws it there. A view without `overview` opens on the last real project.
// `count` is the number the sidebar shows beside the word; `countAll` the one it shows on "All
// projects" (a view with none shows no number there); `badge` also puts the count in the phone's
// bottom bar. A view with `offline` needs no project data: it draws before the project's record
// has arrived.

import { usd } from '../core/format.js';
import { ALL } from '../core/router.js';
import { inboxCount } from '../inbox/count.js';
import { itemsOf } from '../model/grill.js';
import { crsOf, openPr } from '../model/semantics.js';
import * as batch from './batch.js';
import * as config from './config.js';
import * as costs from './costs.js';
import * as dashboard from './dashboard.js';
import * as help from './help.js';
import * as history from './history.js';
import * as home from './home.js';
import * as inbox from './inbox.js';
import * as kanban from './kanban.js';
import * as overview from './overview.js';
import * as prs from './prs.js';
import * as triage from './triage.js';

export const VIEWS = [
  { id: 'home', icon: 'home', word: 'nav.home', module: home, overview },
  {
    id: 'inbox',
    icon: 'inbox',
    word: 'nav.inbox',
    module: inbox,
    overview: inbox,
    count: inboxCount,
    countAll: inboxCount,
    badge: true,
  },
  { id: 'help', icon: 'help', word: 'nav.help', module: help, overview: help, offline: true },
  {
    id: 'triage',
    icon: 'triage',
    word: 'nav.triage',
    module: triage,
    count: (state) => itemsOf(state.data?.backlog).length,
  },
  {
    id: 'kanban',
    icon: 'kanban',
    word: 'nav.kanban',
    module: kanban,
    count: (state) =>
      itemsOf(state.data?.backlog).length +
      crsOf(state.data?.batch).filter((c) => c.state !== 'merged').length,
  },
  {
    id: 'batch',
    icon: 'batch',
    word: 'nav.batch',
    module: batch,
    count: (state) => state.data?.batch?.id ?? null,
  },
  {
    id: 'prs',
    icon: 'pr',
    word: 'nav.prs',
    module: prs,
    count: (state) => (state.data?.batch ? crsOf(state.data.batch).filter(openPr).length : null),
  },
  { id: 'history', icon: 'history', word: 'nav.history', module: history },
  {
    id: 'costs',
    icon: 'costs',
    word: 'nav.costs',
    module: costs,
    count: (state) => (state.data?.batch ? usd(state.data.batch.spent_usd) : null),
  },
  { id: 'dashboard', icon: 'dashboard', word: 'nav.dashboard', module: dashboard },
  { id: 'config', icon: 'config', word: 'nav.config', module: config },
];

export const ids = () => VIEWS.map((v) => v.id);

export const overviewIds = () => VIEWS.filter((v) => v.overview).map((v) => v.id);

export const entry = (id) => VIEWS.find((v) => v.id === id) ?? VIEWS[0];

// The module that draws `view` for `project`: the overview module on "All projects".
export const moduleFor = (view, project) =>
  project === ALL ? (entry(view).overview ?? null) : entry(view).module;

// A view's count for the sidebar, or nothing.
export function countOf(view, state) {
  if (state.project === ALL) return view.countAll?.(state) ?? null;
  return project(state) ? (view.count?.(state) ?? null) : null;
}

const project = (state) => state.project !== ALL && Boolean(state.data);
