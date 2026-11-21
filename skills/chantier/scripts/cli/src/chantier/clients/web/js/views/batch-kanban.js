// The Batch page's Kanban: the batch's three folders, `1-pending`, `2-actives` and `3-done`, as three
// columns of the project Kanban's CR cards. Pure and read-only: a card opens its folder, nothing is
// dragged (the folders move by the CLI's lifecycle). A CR whose row has no `stage` among the three
// (cancelled, or moved out by `order drop`) is in no column; the Graph tab still draws it.
//   kanbanBlock(state, rows) returns the panel's markup.

import { html } from '../core/dom.js';
import { t } from '../model/words.js';
import { column } from '../ui/column.js';
import { crCard } from './kanban-cards.js';

const number = (c) => Number.parseInt(String(c.cr).replace(/\D/g, ''), 10) || 0;
const byNumber = (a, b) => number(a) - number(b);
// The last merged first; a tie or a missing `merged_at` falls back to the CR number.
const byMerged = (a, b) => {
  const [x, y] = [a.merged_at || '', b.merged_at || ''];
  return x === y ? byNumber(a, b) : x < y ? 1 : -1;
};

const COLUMNS = [
  { folder: '1-pending', stage: 'pending', color: 'var(--grey)', sort: byNumber },
  { folder: '2-actives', stage: 'actives', color: 'var(--blue)', sort: byNumber },
  { folder: '3-done', stage: 'done', color: 'var(--ink3)', sort: byMerged },
];

export function kanbanBlock(state, rows) {
  const columns = COLUMNS.map(({ folder, stage, color, sort }) => {
    const cards = rows.filter((c) => c.stage === folder).sort(sort);
    return column({
      key: `bcol-${stage}`,
      name: t(`batch.kanban_${stage}`),
      color,
      count: cards.length,
      sub: t(`batch.kanban_${stage}_sub`),
      body: cards.length
        ? html`${cards.map((c) => crCard(state, c))}`
        : html`<div class="none">${t('kanban.empty')}</div>`,
    });
  });
  return html`<div class="kanban bkanban" data-key="bkanban"><div class="board">${columns}</div></div>`;
}
