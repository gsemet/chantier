// The address is the state of the page: ?p=<project>&v=<view>, and the browser's history.
import { snapshot, update } from './store.js';

export const VIEWS = ['home', 'triage', 'kanban', 'batch', 'costs'];
const LAST_KEY = 'chantier.project';

const clean = (project, view) => ({ project, view: VIEWS.includes(view) ? view : 'home' });

// Where the address says to be, against the projects the board serves.
export function resolve(projects, search = location.search) {
  const ids = projects.map((p) => p.id);
  const asked = new URLSearchParams(search);
  const last = localStorage.getItem(LAST_KEY);
  const project = [asked.get('p'), last].find((id) => ids.includes(id)) ?? ids[0] ?? null;
  return clean(project, asked.get('v'));
}

const reset = { state: null, etag: null, now: null, fails: 0 };

function apply(place) {
  const now = snapshot();
  const moved = place.project !== now.project;
  if (place.project) localStorage.setItem(LAST_KEY, place.project);
  update({ ...place, ...(moved ? reset : {}) });
}

export function go(place, { replace = false } = {}) {
  const next = clean(place.project ?? snapshot().project, place.view ?? snapshot().view);
  const query = new URLSearchParams({ p: next.project ?? '', v: next.view });
  const url = `?${query}`;
  if (replace) history.replaceState(null, '', url);
  else history.pushState(null, '', url);
  apply(next);
}

// The back and forward buttons.
export function listen() {
  window.addEventListener('popstate', () => {
    const board = snapshot().board;
    if (board) apply(resolve(board.projects));
  });
}
