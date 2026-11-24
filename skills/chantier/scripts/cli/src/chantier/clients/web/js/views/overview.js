// The Overview view (the surface): one line per project of the planning surface, a table on a
// desktop and cards on a phone. A click on a line opens the project; a CR link opens its PR only.
//   render(state) returns the view's markup; mount(root, state) returns a cleanup.

import { delegate, html } from '../core/dom.js';
import { age, hhmm, prNumber, safeUrl, title, usd } from '../core/format.js';
import { t, tf } from '../model/words.js';
import { card } from '../ui/card.js';
import { empty, live, mark, meter, stateIcon, tag } from '../ui/parts.js';
import { pathsOf, projectsOf, sharedForge } from '../ui/picker.js';
import { VARIANT } from './history-filter.js';
import { surfaceBlock } from './home-project.js';

const none = '—';

// A CR to review: a link to its PR when the address is a web one, else plain text.
const prLink = (e) => {
  const url = safeUrl(e.pr);
  return url
    ? html`<a class="prlink" href="${url}" target="_blank" rel="noopener" title="${title(e.title)}">${e.cr} <span aria-hidden="true">↗</span></a>`
    : html`<span class="prlink">${e.cr}</span>`;
};

// "batch-NN · state", with the batch's mode under it.
const batchOf = (p) =>
  p.batch
    ? html`<b>${p.batch.id}</b> · ${p.batch.state}${p.batch.mode ? html`<br /><small class="mut">${p.batch.mode}</small>` : ''}`
    : html`<span class="mut">${t('project.no_batch')}</span>`;

const workingOf = (p) =>
  html`${p.working.length}${p.blocked.length ? html` · <span class="bad">${t('overview.blocked', { n: p.blocked.length })}</span>` : ''}`;

const progressOf = (p) =>
  p.total
    ? html`<div class="mbar">${meter([{ n: p.merged, color: 'var(--accent)' }], p.total)}</div><small class="mut">${t('overview.merged', { a: p.merged, b: p.total })}</small>`
    : none;

// The spend, with "/ budget" under it.
const spentOf = (p) =>
  p.batch ? html`${usd(p.spent_usd)}<br /><small class="mut">/ ${usd(p.budget_usd)}</small>` : none;

// The age of the project's last event; a dash when no batch runs there.
const dataOf = (p, now) => {
  const at = p.batch ? age(p.last_event_at, now) : '';
  return at ? t('time.ago', { age: at }) : none;
};

const row = (p, now) =>
  html`<tr data-project="${p.id}" tabindex="0" data-key="row-${p.id}"><td class="who">${mark(p.id)}<div class="wtx"><div class="wnm"><b>${p.id}</b>${p.running ? live() : ''}</div>${pathsOf(p)}</div></td><td>${batchOf(p)}</td><td class="num">${workingOf(p)}</td><td>${p.to_review.length ? p.to_review.map(prLink) : none}</td><td>${progressOf(p)}</td><td class="num">${spentOf(p)}</td><td class="num">${p.inbox} · ${p.backlog}</td><td class="mut">${dataOf(p, now)}</td></tr>`;

const head = (forge) =>
  ['project', 'batch', 'working', 'review', 'progress', 'spent', 'intake', 'data'].map(
    (k) =>
      html`<th class="${['working', 'spent', 'intake'].includes(k) ? 'num' : ''}">${tf(forge, `overview.${k}`)}</th>`,
  );

const counted = (forge, key, n) => {
  const [before, after] = tf(forge, key, { n: '\u0001' }).split('\u0001');
  return html`${before}<b>${n}</b>${after}`;
};

const sums = (p) => [
  counted(p.forge, 'overview.card_review', p.to_review.length),
  counted(p.forge, 'overview.card_working', p.working.length),
  html`<b>${p.batch ? usd(p.spent_usd) : none}</b>`,
  counted(p.forge, 'overview.card_intake', p.inbox),
];

const projectCard = (p) =>
  card({
    classes: 'apc',
    attrs: html`data-project="${p.id}" tabindex="0" data-key="card-${p.id}"`,
    body: html`<div class="apt">${mark(p.id)}<b>${p.id}</b>${p.running ? live() : ''}<span class="mut">${p.batch ? p.batch.id : t('project.no_batch')}</span></div>`,
    meta: html`<div class="apth">${pathsOf(p)}</div><div class="aps">${sums(p).map((s) => html`<span>${s}</span>`)}</div>`,
  });

// The open PRs of every project, from the project lines (`open_prs`): ready to merge and red CI
// first, in the merge order. The state chip is the state chip's own look and words.
const PR_CHIP = {
  ready: ['ready', 'state.ready'],
  red: ['blocked', 'pv.checks.failing'],
  working: ['working', 'state.working'],
};

const prState = (s) => {
  const [variant, word] = PR_CHIP[s] ?? PR_CHIP.working;
  return tag(`st ${variant}`, html`${stateIcon(variant)}${t(word)}`);
};

function prRow(p, c) {
  const url = safeUrl(c.pr);
  const number = url
    ? html`<a class="prlink r" href="${url}" target="_blank" rel="noopener" data-key="ovp-${p.id}-${c.cr}">${prNumber(c.pr)}</a>`
    : html`<span class="r">${prNumber(c.pr)}</span>`;
  return html`<div class="x" data-project="${p.id}" tabindex="0" data-key="ovr-${p.id}-${c.cr}">${prState(c.state)}${mark(p.id)}<b>${c.cr}</b><span class="ell" title="${title(c.title)}">${title(c.title)}</span>${number}</div>`;
}

function prsBlock(projects) {
  const rows = projects.flatMap((p) => (p.open_prs ?? []).map((c) => prRow(p, c)));
  const list = rows.length ? rows : html`<div class="none">${t('home.none')}</div>`;
  return html`<section class="block side"><h2>${t('home.open_prs')} <span class="sub">${rows.length}</span></h2><div class="list">${list}</div></section>`;
}

// The newest events of every project (the History's own: opened, merged, dropped, releases).
function eventRow(e) {
  const variant = VARIANT[e.kind] ?? 'queued';
  const chip = tag(`st ${variant}`, html`${stateIcon(variant)}${t(`history.kind.${e.kind}`)}`);
  return html`<li data-project="${e.project}" tabindex="0" data-key="ova-${e.project}-${e.cr}-${e.kind}"><span class="t at">${e.at.slice(5, 10)} ${hhmm(e.at)}</span>${mark(e.project)}${chip}<b>${e.cr}</b><span class="ell" title="${title(e.title)}">${title(e.title)}</span></li>`;
}

function activityBlock(events) {
  const body = events.length
    ? events.map(eventRow)
    : html`<li class="none">${t('overview.no_events')}</li>`;
  const more = html`<button type="button" class="btn" data-go="history" data-key="ova-history">${t('overview.history_link')}</button>`;
  return html`<section class="block wide"><h2>${t('home.activity')} <span class="sub">${events.length}</span></h2><ul class="feed">${body}</ul><div class="foot">${more}</div></section>`;
}

export function render(state) {
  const projects = projectsOf(state);
  if (!projects.length) return empty(t('stats.loading'));
  const forge = sharedForge(projects);
  return html`<div class="overview"><div class="tbl wide"><table><thead><tr>${head(forge)}</tr></thead><tbody>${projects.map((p) => row(p, state.now))}</tbody></table></div><div class="cards">${projects.map(projectCard)}</div><p class="note">${tf(forge, 'overview.note')}</p><div class="home"><div class="blocks">${prsBlock(projects)}${activityBlock(state.board?.activity ?? [])}${surfaceBlock(state)}</div></div></div>`;
}

// A PR link opens the PR only: the click does not reach the line that opens the project.
export function mount(root) {
  return delegate(root, 'click', 'a.prlink', (event) => event.stopPropagation());
}
