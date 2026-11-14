// The Kanban view: five columns, from the inbox to the CRs handed back. A card opens its folder.
//   render(state) returns the view's markup; mount(root, state) returns a cleanup.

import { html } from '../core/dom.js';
import { crsOf, defaultBranch } from '../model/semantics.js';
import { t } from '../model/words.js';
import { bindOpen } from '../ui/open.js';
import { dot } from '../ui/parts.js';
import { crCard, itemCard } from './kanban-cards.js';

const PRIORITIES = ['P1', 'P2', 'P3', 'P4'];
const PROGRESS = ['blocked', 'working', 'queued'];

const itemsIn = (backlog, buckets) =>
  buckets.flatMap((b) => (backlog?.[b] ?? []).map((item) => ({ item, bucket: b })));

const inProgress = (batch) => PROGRESS.flatMap((s) => crsOf(batch).filter((c) => c.state === s));

// The columns: name, sub-line, colour and the cards they hold (already drawn).
function columns(state) {
  const { batch, backlog } = state.data;
  const items = (buckets) =>
    itemsIn(backlog, buckets).map((x) => itemCard(state, x.item, x.bucket));
  const crs = (rows) => rows.map((c) => crCard(state, c));
  const progressSub = batch
    ? t('kanban.progress_sub', { batch: batch.id })
    : t('kanban.progress_none');
  return [
    { key: 'intake', color: 'var(--grey)', sub: t('kanban.intake_sub'), cards: items(['inbox']) },
    { key: 'grill', color: 'var(--amber)', sub: t('kanban.grill_sub'), cards: items(PRIORITIES) },
    { key: 'ready', color: 'var(--violet)', sub: t('kanban.ready_sub'), cards: items(['3-ready']) },
    { key: 'progress', color: 'var(--blue)', sub: progressSub, cards: crs(inProgress(batch)) },
    {
      key: 'handed',
      color: 'var(--green)',
      sub: t('kanban.handed_sub', { branch: defaultBranch(batch) }),
      cards: crs(crsOf(batch).filter((c) => c.state === 'ready')),
    },
  ];
}

const column = (col) =>
  html`<section class="col" data-key="col-${col.key}"><div class="colh">${dot(col.color)}<h2>${t(`kanban.${col.key}`)}</h2><span class="c">${col.cards.length}</span><span class="place"></span></div><div class="colsub">${col.sub}</div><div class="cards">${col.cards.length ? col.cards : html`<div class="none">${t('kanban.empty')}</div>`}</div></section>`;

export function render(state) {
  const cols = columns(state);
  const shown = cols.reduce((n, col) => n + col.cards.length, 0);
  const count = t('kanban.count', { n: shown, m: state.data.merged_total ?? 0 });
  return html`<div class="kanban"><div class="filters"><span class="place"></span><span class="count">${count}</span></div><div class="board">${cols.map(column)}</div></div>`;
}

export const mount = (root) => bindOpen(root);
