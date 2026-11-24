// The header: the breadcrumb bar, the title of the view with its stats line, and the notice for a
// key the board refused.
import { html } from '../core/dom.js';
import { ALL } from '../core/router.js';
import { grillItems, handedCrs, inboxItems, progressCrs } from '../model/columns.js';
import { shownRecord } from '../model/history.js';
import { t, tf, tn } from '../model/words.js';
import { entry } from '../views/registry.js';
import { stateIcon } from './parts.js';
import { projectsOf, sharedForge, surfaceName } from './picker.js';

const figure = (n, word) => html`<span><b>${n}</b> ${t(word)}</span>`;
const counted = (n, word, forge) =>
  html`<span><b>${n}</b> ${forge ? tf(forge, n === 1 ? `${word}.one` : word, { n }) : tn(word, n)}</span>`;

// The figures of the whole surface, on the overview.
function overall(state) {
  const projects = projectsOf(state);
  const sum = (pick) => projects.reduce((n, p) => n + pick(p), 0);
  return [
    counted(projects.length, 'stats.projects'),
    counted(
      sum((p) => Number(p.running)),
      'stats.batches',
    ),
    counted(
      sum((p) => p.to_review.length),
      'stats.reviews',
      sharedForge(projects),
    ),
    counted(
      sum((p) => p.working.length),
      'stats.crs',
    ),
  ];
}

// The figures of one project, each the count of the Triage column of the same name (the filters of
// the page do not change them): its inbox, its grill, and its batch.
function of(data) {
  const backlog = data.backlog ?? {};
  const base = [
    figure(inboxItems(backlog).length, 'stats.inbox'),
    figure(grillItems(backlog).length, 'stats.grill'),
  ];
  if (!data.batch) return [...base, html`<span>${t('stats.no_batch')}</span>`];
  return [
    ...base,
    figure(progressCrs(data.batch).length, 'stats.progress'),
    figure(handedCrs(data.batch).length, 'stats.handed'),
  ];
}

export function stats(state) {
  if (state.project !== ALL && state.view === 'batch') return '';
  if (state.project === ALL) return state.board ? overall(state) : t('stats.loading');
  return state.data ? of(state.data) : t('stats.loading');
}

// The surface's name heads its Home only; every other page shows its own word.
export const title = (state) =>
  state.project === ALL && state.view === 'home' ? surfaceName(state) : t(entry(state.view).word);

// The line, the field and the button of a refused key (`bindKeyNotice` makes them work).
export const notice = (state) =>
  state.denied
    ? html`<span>${t('notice.key')}</span><input type="text" class="keyfield" data-key-field autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="${t('notice.key_field')}" placeholder="${t('notice.key_field')}"><button type="button" class="btn small" data-key-open>${t('notice.key_open')}</button>`
    : '';

const sepc = html`<span class="sepc" aria-hidden="true">/</span>`;

// The batch the Batch page shows, as { id, word, icon }: a closed record has the grey "closed" chip,
// the running or paused batch its own state.
function shownBatchChip(state) {
  const closed = shownRecord(state.data, state.batchId);
  if (closed) return { id: closed.batch, word: 'state.closed', icon: 'queued' };
  const batch = state.data?.batch;
  if (!batch) return null;
  const icon = batch.state === 'running' ? 'working' : 'queued';
  return { id: batch.id, word: `state.${icon}`, icon };
}

// The breadcrumb: the project (or the surface), then the view; on the Batch view the batch's id and
// a grey chip with its state.
export function crumbs(state) {
  const all = state.project === ALL;
  const first = all ? surfaceName(state) : state.project;
  const page = t(entry(state.view).word);
  const shown = !all && state.view === 'batch' ? shownBatchChip(state) : null;
  if (shown) {
    const chip = html`<span class="chip ${shown.icon}">${stateIcon(shown.icon)}${t(shown.word)}</span>`;
    return html`<span>${first}</span>${sepc}<span>${page}</span>${sepc}<span class="cur">${shown.id}</span>${chip}`;
  }
  return html`<span>${first}</span>${sepc}<span class="cur">${page}</span>`;
}

// The shadow under the bar, once the main area has scrolled away from its top.
export function bindScroll(main, head) {
  const mark = () => head.classList.toggle('scrolled', main.scrollTop > 0);
  main.addEventListener('scroll', mark, { passive: true });
  mark();
}
