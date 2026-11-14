// The sidebar: the project picker, the views, and the foot (the data's age, the language button).
import { html } from '../core/dom.js';
import { waited } from '../core/format.js';
import { unreachable } from '../core/refresh.js';
import { ALL } from '../core/router.js';
import { nextLanguage, t, wordOf } from '../model/words.js';
import { countOf, VIEWS } from '../views/registry.js';
import { icon } from './icons.js';
import { menu, trigger } from './picker.js';

// A view shows on the current project, or on All projects only when it has an overview.
export const shown = (view, state) => state.project !== ALL || Boolean(view.overview);

const item = (view, state) => {
  const n = countOf(view, state);
  const count = n == null ? '' : html`<span class="n">${n}</span>`;
  const on = state.view === view.id;
  return html`<button class="nav${on ? ' on' : ''}" type="button" data-view="${view.id}" data-key="nav-${view.id}"${on ? html` aria-current="page"` : ''}><span class="ic">${icon(view.icon)}</span>${t(view.word)}${count}</button>`;
};

export const projectSide = (state) => html`${trigger(state, 'ws')}${menu(state)}`;

export const navigation = (state) =>
  VIEWS.filter((v) => shown(v, state)).map((v) => item(v, state));

// "Data: 3 min ago", or "Board unreachable: data 3 min ago", or that nothing was read yet.
export function heard(state) {
  if (!state.heard) return t('foot.never');
  const age = waited(state.heard);
  return t(unreachable(state.fails) ? 'foot.unreachable' : 'foot.data', { age });
}

export const languageButton = () =>
  html`<span class="ic">${icon('lang')}</span>${wordOf(nextLanguage(), 'lang.switch')}`;
