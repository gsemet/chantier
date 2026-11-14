// The project picker: the button that names the project shown, and the menu it opens. The menu
// lists "All projects" first, then each project of the planning surface.
import { html } from '../core/dom.js';
import { ALL } from '../core/router.js';
import { t } from '../model/words.js';
import { icon } from './icons.js';
import { live, mark } from './parts.js';

export const projectsOf = (state) => state.board?.projects ?? [];

// More than one project: only then is there something to pick.
export const canPick = (state) => projectsOf(state).length > 1;

export const current = (state) => projectsOf(state).find((p) => p.id === state.project) ?? null;

const totalReviews = (projects) => projects.reduce((n, p) => n + p.to_review.length, 0);

// A project's line: its batch and state, and how many items wait in its intake.
export function lineOf(project) {
  if (!project.batch) return `${t('project.no_batch')} · ${project.inbox} ${t('stats.intake')}`;
  const state = project.running ? t('project.running') : project.batch.state;
  return t('project.line', { batch: project.batch.id, state, n: project.inbox });
}

// The button: the project's mark, its name and a line, and a caret when there is a menu.
export function trigger(state, cls) {
  const all = state.project === ALL;
  const project = current(state);
  const name = all ? t('project.all') : (project?.id ?? '…');
  const sub = all
    ? t('project.all_sub', { n: totalReviews(projectsOf(state)) })
    : project
      ? lineOf(project)
      : '';
  const caret = canPick(state) ? html`<span class="car">${icon('chev')}</span>` : '';
  const face = all ? html`<span class="mark all">${icon('overview')}</span>` : mark(name);
  const body = html`${face}<span><b>${name}</b><small>${sub}</small></span>${caret}`;
  if (!canPick(state)) return html`<div class="${cls}">${body}</div>`;
  return html`<button class="${cls}" type="button" data-menu="toggle" data-key="${cls}-picker" aria-haspopup="true" aria-expanded="${state.menu}" title="${t('project.change')}">${body}</button>`;
}

// The check mark of the current line.
const ok = () => html`<span class="ok">${icon('check')}</span>`;

const row = (project, state) =>
  html`<button class="row${project.id === state.project ? ' on' : ''}" type="button" data-project="${project.id}" role="menuitem">${mark(project.id)}<span><b>${project.id}</b>${project.running ? live() : ''}<small>${lineOf(project)}</small></span>${project.id === state.project ? ok() : ''}</button>`;

// The open menu, or nothing.
export function menu(state) {
  if (!state.menu || !canPick(state)) return '';
  const projects = projectsOf(state);
  const all = html`<button class="row${state.project === ALL ? ' on' : ''}" type="button" data-project="${ALL}" role="menuitem"><span class="mark all">${icon('overview')}</span><span><b>${t('project.all')}</b><small>${t('project.all_sub', { n: totalReviews(projects) })}</small></span>${state.project === ALL ? ok() : ''}</button>`;
  return html`<div class="menu" role="menu"><div class="cap">${t('project.head', { n: projects.length })}</div>${all}${projects.map((p) => row(p, state))}</div>`;
}
