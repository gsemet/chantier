// The label filter row: "Labels", one toggle per label of the project, "show all" when a filter is
// on. The filter is the page's state for the session (`labelFilter` in the store), written nowhere.
// Triage and Kanban draw it and share it.
import { delegate, html } from '../core/dom.js';
import { snapshot, update } from '../core/store.js';
import { findItem, labelsOf, passes } from '../model/triage.js';
import { t } from '../model/words.js';
import { colorVars } from './tags.js';

export function filterRow(state) {
  const all = labelsOf(state.data?.backlog);
  if (!all.length) return '';
  const on = state.labelFilter;
  const buttons = all.map(
    (l) =>
      html`<button type="button" class="lab lbtn${on.includes(l) ? ' on' : ''}" aria-pressed="${on.includes(l)}" data-lf="${l}" data-key="lf-${l}" data-vars="${colorVars(all, l)}">${l}</button>`,
  );
  const clear = on.length
    ? html`<button type="button" class="lclr" data-lf="" data-key="lf-clear">${t('labels.all')}</button>`
    : '';
  return html`<div class="lfil" role="group" aria-label="${t('labels.title')}"><span class="lt">${t('labels.title')}</span>${buttons}${clear}</div>`;
}

// Toggle a label; an empty one clears the filter. Returns the function that removes the listener.
export const bindFilter = (root) =>
  delegate(root, 'click', '[data-lf]', (_, button) => {
    const label = button.dataset.lf;
    const state = snapshot();
    const now = state.labelFilter;
    const toggled = now.includes(label) ? now.filter((l) => l !== label) : [...now, label];
    const next = label ? toggled : [];
    // A post-it the filter hides leaves the selection.
    const selection = state.selection.filter((s) => {
      const item = findItem(state.data?.backlog, s);
      return item && passes(item, next);
    });
    update({ labelFilter: next, selection });
  });
