// The phone's bottom bar: the views as icons with their names.
import { html } from '../core/dom.js';
import { t } from '../model/words.js';
import { countOf, VIEWS } from '../views/registry.js';
import { icon } from './icons.js';
import { shown } from './sidebar.js';

// A view with `badge` shows its count after its word.
const badge = (v, state) => {
  const n = v.badge ? countOf(v, state) : null;
  return n == null ? '' : html`<span class="n">${n}</span>`;
};

export const bottomBar = (state) =>
  VIEWS.filter((v) => shown(v, state)).map(
    (v) =>
      html`<button type="button" class="${state.view === v.id ? 'on' : ''}" data-view="${v.id}" data-key="bnav-${v.id}"><span class="ic">${icon(v.icon)}</span>${t(v.word)}${badge(v, state)}</button>`,
  );
