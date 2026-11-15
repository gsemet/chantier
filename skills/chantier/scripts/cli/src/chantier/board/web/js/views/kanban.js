// The Kanban view: seven columns, from the inbox to the CRs merged. A card opens its folder. What a
// column holds is written once, in model/columns.js (the header's figures count the same).
//   render(state) returns the view's markup; mount(root, state) returns a cleanup.

import { html } from '../core/dom.js';
import { bindFilter, filterRow } from '../labels/filter.js';
import { bindPriority, priorityRow } from '../labels/priority.js';
import {
  backlogItems,
  doneMore,
  doneRows,
  grillItems,
  handedCrs,
  inboxItems,
  progressCrs,
  readyItems,
  visible,
} from '../model/columns.js';
import { defaultBranch } from '../model/semantics.js';
import { labelsOf } from '../model/triage.js';
import { t } from '../model/words.js';
import { bindOpen } from '../ui/open.js';
import { dot } from '../ui/parts.js';
import { backlogCard, crCard, doneCard } from './kanban-cards.js';

// A column: its key, colour, sub-line and the cards it holds (already drawn).
const col = (key, color, sub, cards, more = {}) => ({ key, color, sub, cards, ...more });

// The columns. The Done column also carries its own count (the merged total) and its foot.
function columns(state) {
  const { batch, backlog } = state.data;
  const labels = labelsOf(backlog);
  const items = (list) =>
    visible(list, state.priorityFilter, state.labelFilter).map((x) =>
      backlogCard(state, x, labels),
    );
  const crs = (rows) => rows.map((c) => crCard(state, c));
  const progressSub = t(batch ? 'kanban.progress_sub' : 'kanban.progress_none', {
    batch: batch?.id,
  });
  const handedSub = t('kanban.handed_sub', { branch: defaultBranch(batch) });
  const more = doneMore(state.data);
  const foot = more ? html`<div class="none">${t('kanban.more', { n: more })}</div>` : '';
  return [
    col('inbox', 'var(--grey)', t('kanban.inbox_sub'), items(inboxItems(backlog))),
    col('backlog', 'var(--brown)', t('kanban.backlog_sub'), items(backlogItems(backlog))),
    col('grill', 'var(--amber)', t('kanban.grill_sub'), items(grillItems(backlog))),
    col('ready', 'var(--violet)', t('kanban.ready_sub'), items(readyItems(backlog))),
    col('progress', 'var(--blue)', progressSub, crs(progressCrs(batch))),
    col('handed', 'var(--green)', handedSub, crs(handedCrs(batch))),
    col(
      'done',
      'var(--ink3)',
      t('kanban.done_sub'),
      doneRows(state.data).map((m) => doneCard(state, m)),
      { count: state.data.merged_total ?? 0, foot },
    ),
  ];
}

// The Inbox column's button: it opens the New dialog (wired once for the page, in main.js).
const newIdea = html`<div class="colact"><button type="button" class="btn" data-new>${t('new.kanban')}</button></div>`;

const column = (c) =>
  html`<section class="col" data-key="col-${c.key}"><div class="colh">${dot(c.color)}<h2>${t(`kanban.${c.key}`)}</h2><span class="c">${c.count ?? c.cards.length}</span><span class="place"></span></div>${c.key === 'inbox' ? newIdea : ''}<div class="colsub">${c.sub}</div><div class="cards">${c.cards.length ? c.cards : html`<div class="none">${t('kanban.empty')}</div>`}${c.foot ?? ''}</div></section>`;

export function render(state) {
  const cols = columns(state);
  const shown = cols.filter((c) => c.key !== 'done').reduce((n, c) => n + c.cards.length, 0);
  const count = t('kanban.count', { n: shown, m: state.data.merged_total ?? 0 });
  return html`<div class="kanban"><div class="filters"><span class="place">${filterRow(state)}${priorityRow(state)}</span><span class="count">${count}</span></div><div class="board">${cols.map(column)}</div></div>`;
}

export function mount(root) {
  const offs = [bindOpen(root), bindFilter(root), bindPriority(root)];
  return () => {
    for (const off of offs) off();
  };
}
