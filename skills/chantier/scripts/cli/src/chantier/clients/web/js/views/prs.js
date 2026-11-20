// The PRs view: the PRs of the batch shown as the forge says they are now, one row each, against
// the record, with the batch navigator, a state filter and a sort. The page only reads: nothing
// here writes a folder, git or the forge. The view has its own feed (prs-feed.js), one per batch
// shown; the forge's answer is kept in `state.prs`.
//   render(state) returns the view's markup; mount(root) returns a cleanup.

import { html } from '../core/dom.js';
import { age } from '../core/format.js';
import { snapshot, subscribe, update } from '../core/store.js';
import { shownId } from '../model/history.js';
import { t } from '../model/words.js';
import { bindOpen } from '../ui/open.js';
import { empty } from '../ui/parts.js';
import { startFeed } from './prs-feed.js';
import { bindFilter, chips, filtered, sorted } from './prs-filter.js';
import { prRow } from './prs-row.js';

const count = (rows, state) => rows.filter((r) => r.state === state).length;

// A closed batch is read once; the others are read again every 10 s until every PR is done.
function refresh(answer) {
  if (answer.closed) return html`<span class="tag">${t('pv.closed_batch')}</span>`;
  if (answer.all_done) return html`<span>${t('pv.stopped')}</span>`;
  return html`<span>${t('pv.refreshing')}</span>`;
}

function head(answer) {
  const rows = answer.rows;
  const merged = count(rows, 'merged');
  const closed = count(rows, 'closed');
  const total = Math.max(rows.length, 0);
  const progress = t('pv.progress', { done: merged + closed, total, merged, closed });
  const paused = answer.paused ? html`<span class="tag waits">${t('pv.paused')}</span>` : '';
  const read = answer.read_at
    ? html`<span>${t('pv.read', { age: age(answer.read_at, answer.now) })}</span>`
    : html`<span>${t('pv.reading')}</span>`;
  return html`<div class="pvhead"><b>${t('pv.batch', { batch: answer.batch })}</b>${paused}<span>${progress}</span>${refresh(answer)}${read}</div>`;
}

// The forge's error, with the last good read still shown under it.
const problem = (answer) =>
  answer.error
    ? html`<div class="pverr" data-key="pv-error">${t('pv.error', { error: answer.error })} ${answer.rows.length ? t('pv.error_kept') : ''}</div>`
    : '';

// The rows the filter keeps, in the sort's order; one line when the filter hides them all.
function list(answer, state) {
  const shown = sorted(filtered(answer.rows, state.prsState), state.prsSort);
  if (!shown.length) return empty(t('pv.nomatch'));
  const rows = shown.map((r) => prRow(r, answer.now, answer.read_at, state.prsSort));
  return html`<div class="pvrows">${rows}</div>`;
}

function body(state) {
  const answer = state.prs;
  if (answer.unread) return problem(answer);
  if (!answer.batch) return html`${problem(answer)}${empty(t('pv.none'))}`;
  if (!answer.rows.length && !answer.error) return html`${head(answer)}${empty(t('pv.nopr'))}`;
  return html`${head(answer)}${problem(answer)}${chips(state)}${answer.rows.length ? list(answer, state) : ''}`;
}

export function render(state) {
  if (!state.prs) return html`<div class="prview">${empty(t('stats.loading'))}</div>`;
  return html`<div class="prview">${body(state)}</div>`;
}

const shownOf = (state) => shownId(state.data, state.batchId);

// The id the feed asks for: none for the batch in 4-batch/ (or none shown), the server picks.
const askedOf = (state, shown) => (shown && shown !== state.data?.batch?.id ? shown : null);

export function mount(root) {
  const offOpen = bindOpen(root);
  const offFilter = bindFilter(root);
  let shown = shownOf(snapshot());
  let stop = () => {};
  // Another batch's rows never stay under the shown batch's name: loading, then a read at once.
  const begin = () => {
    if (snapshot().prs && snapshot().prs.batch !== shown) update({ prs: null });
    stop = startFeed(askedOf(snapshot(), shown));
  };
  begin();
  const unsub = subscribe((state) => {
    const now = shownOf(state);
    if (now === shown) return;
    shown = now;
    stop(); // the feed of the old batch never keeps writing prs
    if (state.prs?.batch !== now) update({ prs: null });
    begin();
  });
  return () => {
    offOpen();
    offFilter();
    unsub();
    stop();
  };
}
