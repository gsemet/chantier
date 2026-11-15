// The header: the title of the view, the stats line, and the notice for a key the board refused.
import { html } from '../core/dom.js';
import { ALL } from '../core/router.js';
import { grillItems, handedCrs, inboxItems, progressCrs } from '../model/columns.js';
import { t, tn } from '../model/words.js';
import { entry } from '../views/registry.js';
import { projectsOf } from './picker.js';

const figure = (n, word) => html`<span><b>${n}</b> ${t(word)}</span>`;
const counted = (n, word) => html`<span><b>${n}</b> ${tn(word, n)}</span>`;

// The figures of the whole surface, on All projects.
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
  if (state.project === ALL) return state.board ? overall(state) : t('stats.loading');
  return state.data ? of(state.data) : t('stats.loading');
}

export const title = (state) => t(state.project === ALL ? 'nav.overview' : entry(state.view).word);

export const notice = (state) => (state.denied ? t('notice.key') : '');
