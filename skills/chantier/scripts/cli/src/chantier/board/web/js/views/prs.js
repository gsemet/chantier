// The PRs view: the batch's PRs as the forge says they are now, one row each, against the record.
// The page only reads: nothing here writes a folder, git or the forge. The view has its own feed
// (prs-feed.js); the forge's answer is kept in `state.prs`.
//   render(state) returns the view's markup; mount(root) returns a cleanup.

import { html } from '../core/dom.js';
import { age } from '../core/format.js';
import { t } from '../model/words.js';
import { bindOpen } from '../ui/open.js';
import { empty } from '../ui/parts.js';
import { startFeed } from './prs-feed.js';
import { prRow } from './prs-row.js';

const count = (rows, state) => rows.filter((r) => r.state === state).length;

function refresh(answer) {
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

function body(answer) {
  if (answer.unread) return problem(answer);
  if (!answer.batch) {
    const last = answer.last_batch ? ` ${t('pv.last', { batch: answer.last_batch })}` : '';
    return html`${problem(answer)}${empty(`${t('pv.none')}${last}`)}`;
  }
  if (!answer.rows.length && !answer.error) return html`${head(answer)}${empty(t('pv.nopr'))}`;
  const rows = answer.rows.map((r) => prRow(r, answer.now, answer.read_at));
  return html`${head(answer)}${problem(answer)}<div class="pvrows">${rows}</div>`;
}

export function render(state) {
  if (!state.prs) return html`<div class="prview">${empty(t('stats.loading'))}</div>`;
  return html`<div class="prview">${body(state.prs)}</div>`;
}

export function mount(root) {
  const offOpen = bindOpen(root);
  const stop = startFeed();
  return () => {
    offOpen();
    stop();
  };
}
