// The Kanban's priority filter row: "Priorities", one toggle for the Inbox and one for each of P1 to
// P4, all on at the start. A toggle off hides that bucket's items from the Inbox, Backlog and Grill
// columns; 3-ready, the batch's CRs and the Done column are never filtered. The choice is the page's
// state for the session (`priorityFilter` in the store), written nowhere, as the label filter is.
import { delegate, html } from '../core/dom.js';
import { snapshot, update } from '../core/store.js';
import { FILTERED } from '../model/columns.js';
import { t } from '../model/words.js';
import { priorityChip } from '../ui/parts.js';

export function priorityRow(state) {
  const on = state.priorityFilter;
  const buttons = FILTERED.map((b) =>
    priorityChip(b, {
      button: true,
      on: on.includes(b),
      attrs: html`data-pf="${b}" data-key="pf-${b}"`,
    }),
  );
  return html`<div class="lfil" role="group" aria-label="${t('priority.title')}"><span class="lt">${t('priority.title')}</span>${buttons}</div>`;
}

// Toggle a bucket. Returns the function that removes the listener.
export const bindPriority = (root) =>
  delegate(root, 'click', '[data-pf]', (_, button) => {
    const bucket = button.dataset.pf;
    const now = snapshot().priorityFilter;
    update({
      priorityFilter: FILTERED.filter((b) => (b === bucket ? !now.includes(b) : now.includes(b))),
    });
  });
