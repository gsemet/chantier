// The Home view: the main state at a glance, in five blocks. The attention tiles come from the
// TILES list: a later change adds a tile by adding a function to it, nothing else changes.
//   render(state) returns the view's markup; mount(root, state) returns a cleanup.

import { delegate, html } from '../core/dom.js';
import { countOf } from '../journal/journal.js';
import { counts } from '../model/semantics.js';
import { t } from '../model/words.js';
import { bindOpen } from '../ui/open.js';
import { kpi } from '../ui/parts.js';
import { backlogBlock } from './home-backlog.js';
import { batchBlock } from './home-batch.js';
import { activityBlock } from './home-feed.js';
import { prsBlock } from './home-prs.js';

const reviewTile = (state) => {
  const c = counts(state.data.batch);
  return kpi({
    tone: c.review ? 'go' : 'calm',
    label: t('home.review'),
    value: c.review,
    sub: c.review ? t('home.review_go') : t('home.review_none', { n: c.ready }),
    go: 'batch',
  });
};

const waitingTile = (state) => {
  const batch = state.data.batch;
  const blocked = counts(batch).blocked;
  const asks = batch?.asks_unread ?? 0;
  return kpi({
    tone: blocked + asks ? 'hot' : 'calm',
    label: t('home.waiting'),
    value: blocked + asks,
    sub: t('home.waiting_sub', { blocked, asks }),
    go: 'batch',
  });
};

const nextTile = (state) => {
  const n = (state.data.backlog?.['3-ready'] ?? []).length;
  return kpi({
    tone: n ? 'go' : 'calm',
    label: t('home.next'),
    value: n,
    sub: t('home.next_sub'),
    go: 'kanban',
  });
};

// What the board wrote in the backlog since the user's last "rescan" to the Chief of Staff.
const writtenTile = (state) => {
  const n = countOf(state);
  return kpi({
    tone: n ? 'go' : 'calm',
    label: t('home.written'),
    value: n,
    sub: t(n ? 'home.written_sub' : 'home.written_none'),
    go: 'triage',
  });
};

// Each tile is a function of the state that returns markup.
export const TILES = [reviewTile, waitingTile, nextTile, writtenTile];

export const render = (state) =>
  html`<div class="home"><div class="tiles">${TILES.map((tile) => tile(state))}</div><div class="blocks">${batchBlock(state)}${prsBlock(state)}${activityBlock(state)}${backlogBlock(state)}</div></div>`;

// A CR row opens its folder; a PR link opens the PR only.
export function mount(root) {
  const off = bindOpen(root);
  const stop = delegate(root, 'click', 'a', (event) => event.stopPropagation());
  return () => {
    off();
    stop();
  };
}
