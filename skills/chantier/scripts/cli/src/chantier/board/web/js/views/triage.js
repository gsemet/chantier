// The Triage view: the backlog as post-its. The Inbox on the left, the Backlog column of rows P1 to
// P4 in the middle (up is more urgent), 3-ready on the right. A post-it moves by drag and drop or
// from the selection bar, groups, takes labels; every change is written at once and shown as the
// folder holds it. Hidden on "All projects".
//   render(state) returns the view's markup; mount(root, state) returns a cleanup.

import { delegate, html } from '../core/dom.js';
import { bindJournal, journalPanel, loadJournal } from '../journal/journal.js';
import { bindFilter } from '../labels/filter.js';
import { indicator, itemsIn, labelsOf, modifiedSlugs, READY } from '../model/triage.js';
import { bar } from '../triage/bar.js';
import { column, lanes } from '../triage/columns.js';
import { bindDrag } from '../triage/drag.js';
import { undo } from '../triage/groups.js';
import { bindReady } from '../triage/ready.js';
import { bindSelection, selectedNow, selectionBar } from '../triage/selection.js';
import { bindOpen } from '../ui/open.js';

function contextOf(state) {
  const backlog = state.data.backlog;
  const ready = itemsIn(backlog, READY);
  return {
    selected: selectedNow(state),
    pending: state.pending,
    modified: modifiedSlugs(state.journal?.entries),
    labels: labelsOf(backlog),
    filter: state.labelFilter,
    ready,
    indicator: indicator(state.data.next_batch, ready),
    batch: state.data.batch,
  };
}

export function render(state) {
  const backlog = state.data.backlog;
  const ctx = contextOf(state);
  return html`<div class="triage">${bar(state, ctx.indicator)}${journalPanel(state)}<div class="tri">${column(backlog, 'inbox', ctx)}${lanes(backlog, ctx)}${column(backlog, READY, ctx)}</div>${selectionBar(ctx.selected)}</div>`;
}

export function mount(root) {
  loadJournal();
  const offs = [
    bindOpen(root),
    bindFilter(root),
    bindJournal(root),
    bindReady(root),
    bindSelection(root),
    bindDrag(root),
    delegate(root, 'click', '[data-ungroup]', (event, el) => {
      event.stopPropagation();
      undo(el.dataset.ungroup);
    }),
  ];
  return () => {
    for (const off of offs) off();
  };
}
