// The Overview view (All projects): one line per project of the planning surface, a table on a
// desktop and cards on a phone. A click on a line opens the project; a CR link opens its PR only.
//   render(state) returns the view's markup; mount(root, state) returns a cleanup.

import { delegate, html } from '../core/dom.js';
import { age, safeUrl, usd } from '../core/format.js';
import { t } from '../model/words.js';
import { empty, mark, meter } from '../ui/parts.js';
import { projectsOf } from '../ui/picker.js';

const none = '—';

// A CR to review: a link to its PR when the address is a web one, else plain text.
const prLink = (e) => {
  const url = safeUrl(e.pr);
  return url
    ? html`<a class="prlink" href="${url}" target="_blank" rel="noopener" title="${e.title}">${e.cr}</a>`
    : html`<span class="prlink">${e.cr}</span>`;
};

const batchOf = (p) =>
  p.batch
    ? html`<b>${p.batch.id}</b> <span class="mut">${p.running ? t('project.running') : p.batch.state}</span>`
    : html`<span class="mut">${t('project.no_batch')}</span>`;

const workingOf = (p) =>
  html`${p.working.length}${p.blocked.length ? html` · <span class="bad">${t('overview.blocked', { n: p.blocked.length })}</span>` : ''}`;

const progressOf = (p) =>
  p.total
    ? html`<div class="mbar">${meter([{ n: p.merged, color: 'var(--violet)' }], p.total)}</div><span class="mut">${t('overview.merged', { a: p.merged, b: p.total })}</span>`
    : none;

const spentOf = (p) =>
  p.batch
    ? html`${usd(p.spent_usd)}<div class="mbar">${meter([{ n: p.spent_usd ?? 0, color: 'var(--blue)' }], p.budget_usd)}</div>`
    : none;

const dataOf = (p, now) => {
  const at = age(p.last_event_at, now);
  return at ? t('time.ago', { age: at }) : none;
};

const row = (p, now) =>
  html`<tr data-project="${p.id}" tabindex="0" data-key="row-${p.id}"><td class="who">${mark(p.id)}<b>${p.id}</b></td><td>${batchOf(p)}</td><td class="num">${workingOf(p)}</td><td>${p.to_review.length ? p.to_review.map(prLink) : none}</td><td>${progressOf(p)}</td><td class="num">${spentOf(p)}</td><td class="num">${p.inbox} · ${p.backlog}</td><td class="mut">${dataOf(p, now)}</td></tr>`;

const head = ['project', 'batch', 'working', 'review', 'progress', 'spent', 'intake', 'data'].map(
  (k) =>
    html`<th class="${['working', 'spent', 'intake'].includes(k) ? 'num' : ''}">${t(`overview.${k}`)}</th>`,
);

const card = (p, now) =>
  html`<div class="apc" data-project="${p.id}" tabindex="0" data-key="card-${p.id}"><div class="apt">${mark(p.id)}<b>${p.id}</b><span class="mut">${p.batch ? p.batch.id : t('project.no_batch')}</span></div><div class="aps"><span>${t('overview.card_working', { n: p.working.length })}</span><span>${t('overview.card_review', { n: p.to_review.length })}</span><span>${t('overview.card_intake', { n: p.inbox })}</span><span class="mut">${dataOf(p, now)}</span></div></div>`;

export function render(state) {
  const projects = projectsOf(state);
  if (!projects.length) return empty(t('stats.loading'));
  return html`<div class="overview"><p class="note">${t('overview.note')}</p><div class="tbl wide"><table><thead><tr>${head}</tr></thead><tbody>${projects.map((p) => row(p, state.now))}</tbody></table></div><div class="cards">${projects.map((p) => card(p, state.now))}</div></div>`;
}

// A PR link opens the PR only: the click does not reach the line that opens the project.
export function mount(root) {
  return delegate(root, 'click', 'a.prlink', (event) => event.stopPropagation());
}
