// The views, in the order the sidebar lists them. An entry: its id (the `v=` of the address), its
// icon, its word, the module that draws it on a project, and, if it also shows on "All projects",
// the module that draws it there. A view without `overview` opens on the last real project.

import { usd } from '../core/format.js';
import { ALL } from '../core/router.js';
import { itemsOf } from '../model/grill.js';
import { crsOf } from '../model/semantics.js';
import * as batch from './batch.js';
import * as costs from './costs.js';
import * as home from './home.js';
import * as kanban from './kanban.js';
import * as overview from './overview.js';
import * as triage from './triage.js';

export const VIEWS = [
  { id: 'home', icon: 'home', word: 'nav.home', module: home, overview },
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
    id: 'costs',
    icon: 'costs',
    word: 'nav.costs',
    module: costs,
    count: (state) => (state.data?.batch ? usd(state.data.batch.spent_usd) : null),
  },
];

export const ids = () => VIEWS.map((v) => v.id);

export const overviewIds = () => VIEWS.filter((v) => v.overview).map((v) => v.id);

export const entry = (id) => VIEWS.find((v) => v.id === id) ?? VIEWS[0];

// The module that draws `view` for `project`: the overview module on "All projects".
export const moduleFor = (view, project) =>
  project === ALL ? (entry(view).overview ?? null) : entry(view).module;

// A view's count for the sidebar, or nothing.
export const countOf = (view, state) => (project(state) ? (view.count?.(state) ?? null) : null);

const project = (state) => state.project !== ALL && Boolean(state.data);
