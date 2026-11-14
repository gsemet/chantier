// The views, in the order the sidebar lists them. An entry: its id (the `v=` of the address), its
// icon, its word, the module that draws it on a project, and, if it also shows on "All projects",
// the module that draws it there. A view without `overview` opens on the last real project.

import { ALL } from '../core/router.js';
import { itemsOf } from '../model/grill.js';
import { crsOf } from '../model/semantics.js';
import * as batch from './batch.js';
import * as costs from './costs.js';
import * as home from './home.js';
import * as kanban from './kanban.js';
import * as overview from './overview.js';

export const VIEWS = [
  { id: 'home', icon: 'home', word: 'nav.home', module: home, overview },
  {
    id: 'kanban',
    icon: 'kanban',
    word: 'nav.kanban',
    module: kanban,
    count: (state) => itemsOf(state.data?.backlog).length,
  },
  {
    id: 'batch',
    icon: 'batch',
    word: 'nav.batch',
    module: batch,
    count: (state) => crsOf(state.data?.batch).length,
  },
  { id: 'costs', icon: 'costs', word: 'nav.costs', module: costs },
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
