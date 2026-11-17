// The header: the breadcrumb bar, the title of the view with its stats line, and the notice for a
// key the board refused.
import { html } from '../core/dom.js';
import { ALL } from '../core/router.js';
import { grillItems, handedCrs, inboxItems, progressCrs } from '../model/columns.js';
import { t, tn } from '../model/words.js';
import { entry } from '../views/registry.js';
import { stateIcon } from './parts.js';
import { projectsOf, surfaceName } from './picker.js';

const figure = (n, word) => html`<span><b>${n}</b> ${t(word)}</span>`;
const counted = (n, word) => html`<span><b>${n}</b> ${tn(word, n)}</span>`;

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
    ),
    counted(
      sum((p) => p.working.length),
      'stats.crs',
    ),
  ];
}

// The figures of one project, each the count of the Kanban column of the same name (the filters of
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

export const title = (state) =>
  state.project === ALL ? surfaceName(state) : t(entry(state.view).word);

export const notice = (state) => (state.denied ? t('notice.key') : '');

const sepc = html`<span class="sepc" aria-hidden="true">/</span>`;

// The breadcrumb: the project (or the surface), then the view; on the Batch view the batch's id and
// a grey chip with its state.
export function crumbs(state) {
  const all = state.project === ALL;
  const first = all ? surfaceName(state) : state.project;
  const page = t(entry(state.view).word);
  const batch = !all && state.view === 'batch' ? state.data?.batch : null;
  if (batch) {
    const shown = batch.state === 'running' ? 'working' : 'queued';
    const chip = html`<span class="chip">${stateIcon(shown)}${t(`state.${shown}`)}</span>`;
    return html`<span>${first}</span>${sepc}<span>${page}</span>${sepc}<span class="cur">${batch.id}</span>${chip}`;
  }
  return html`<span>${first}</span>${sepc}<span class="cur">${page}</span>`;
}

// The shadow under the bar, once the main area has scrolled away from its top.
export function bindScroll(main, head) {
  const mark = () => head.classList.toggle('scrolled', main.scrollTop > 0);
  main.addEventListener('scroll', mark, { passive: true });
  mark();
}
