// The host of the shown view: it mounts a view once for a project and a view, then repaints it on
// every change of the data (nothing is redrawn when the markup is unchanged).

import { setHtml } from '../core/dom.js';
import { forget, paint } from '../core/paint.js';
import { ALL } from '../core/router.js';
import { t } from '../model/words.js';
import { moduleFor } from '../views/registry.js';
import { empty } from './parts.js';

let shownKey = null;
let mountedKey = null;
let cleanup = null;

function leave(root) {
  cleanup?.();
  cleanup = null;
  mountedKey = null;
  forget(root);
  setHtml(root, '');
}

// The view has what it needs: a project's record, or the board's lines on All projects.
const ready = (state) => (state.project === ALL ? Boolean(state.board) : Boolean(state.data));

export function show(root, state) {
  const key = `${state.project}|${state.view}`;
  const view = moduleFor(state.view, state.project);
  const fresh = key !== shownKey;
  if (fresh) {
    leave(root);
    shownKey = key;
  }
  if (!view || !ready(state)) {
    paint(root, empty(t('stats.loading')));
    return;
  }
  paint(root, view.render(state));
  if (mountedKey !== key) {
    mountedKey = key;
    cleanup = view.mount?.(root, state) ?? null;
  }
  view.after?.(root, state);
}
