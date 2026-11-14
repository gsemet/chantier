// The header: the title of the view, the stats line, and the notice for a key the board refused.
import { html } from '../core/dom.js';
import { ALL } from '../core/router.js';
import { toGrill } from '../model/grill.js';
import { byState } from '../model/semantics.js';
import { t } from '../model/words.js';
import { entry } from '../views/registry.js';
import { projectsOf } from './picker.js';

const figure = (n, word) => html`<span><b>${n}</b> ${t(word)}</span>`;

// The figures of the whole surface, on All projects.
function overall(state) {
  const projects = projectsOf(state);
  const sum = (pick) => projects.reduce((n, p) => n + pick(p), 0);
  return [
    figure(projects.length, 'stats.projects'),
    figure(
      sum((p) => Number(p.running)),
      'stats.batches',
    ),
    figure(
      sum((p) => p.to_review.length),
      'stats.reviews',
    ),
    figure(
      sum((p) => p.working.length),
      'stats.crs',
    ),
  ];
}

// The figures of one project: its intake, its grill, and its batch.
function of(data) {
  const backlog = data.backlog ?? {};
  const grill = ['P1', 'P2', 'P3', 'P4'].flatMap((p) => backlog[p] ?? []);
  const base = [
    figure((backlog.inbox ?? []).length, 'stats.intake'),
    figure(toGrill(grill).length, 'stats.grill'),
  ];
  if (!data.batch) return [...base, html`<span>${t('stats.no_batch')}</span>`];
  return [
    ...base,
    figure(byState(data.batch, 'working').length, 'stats.working'),
    figure(byState(data.batch, 'ready').length, 'stats.handed'),
  ];
}

export function stats(state) {
  if (state.project === ALL) return state.board ? overall(state) : t('stats.loading');
  return state.data ? of(state.data) : t('stats.loading');
}

export const title = (state) => t(state.project === ALL ? 'nav.overview' : entry(state.view).word);

export const notice = (state) => (state.denied ? t('notice.key') : '');
