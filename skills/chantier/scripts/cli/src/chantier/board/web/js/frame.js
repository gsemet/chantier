// The frame: the sidebar, the header, the phone's bottom bar, the foot. It redraws only the parts
// whose markup changed, so a focus or a hover is not lost at each refresh.
import { $, html, setHtml } from './dom.js';
import { language, nextLanguage, setLanguage, t, wordOf } from './i18n.js';
import { icon } from './icons.js';
import { silent } from './poll.js';
import { go, VIEWS } from './router.js';
import { snapshot, subscribe } from './store.js';
import { waited } from './time.js';
import * as batch from './views/batch.js';
import * as costs from './views/costs.js';
import * as home from './views/home.js';
import * as kanban from './views/kanban.js';
import * as triage from './views/triage.js';

const MODULES = { home, triage, kanban, batch, costs };
const SEEN = new Map();
let body = null; // what the view area was drawn from

const usd = (n) => (n == null ? '—' : `$${n.toFixed(2)}`);
const mark = (id) => [...id].reduce((sum, c) => sum + c.codePointAt(0), 0) % 6;

// Draw `markup` into `element` unless it is what the element already holds.
function put(element, markup) {
  const text = String(markup);
  if (SEEN.get(element) === text) return;
  SEEN.set(element, text);
  setHtml(element, markup);
}

function countsOf(state) {
  if (!state) return {};
  const items = Object.values(state.backlog).reduce((n, list) => n + list.length, 0);
  const open = (state.batch?.crs ?? []).filter((c) => c.state !== 'merged').length;
  const run = state.batch;
  return {
    triage: items,
    kanban: items + open,
    batch: run?.id ?? '',
    costs: run ? usd(run.spent_usd) : '',
  };
}

const pair = (n, label) => html`<span><b>${n}</b> ${label}</span>`;

function statsOf(state) {
  if (!state) return html`<span>${t('stats.loading')}</span>`;
  const run = state.batch;
  const rows = run?.crs ?? [];
  const by = (word) => rows.filter((c) => c.state === word).length;
  const grilled = ['P1', 'P2', 'P3', 'P4'].reduce((n, p) => n + state.backlog[p].length, 0);
  const batchPart = run
    ? html`<span><b>${run.id}</b> ${run.state}</span>`
    : html`<span>${t('stats.no_batch')}</span>`;
  const spent = run ? html`<span><b>${usd(run.spent_usd)}</b> / ${usd(run.budget_usd)}</span>` : '';
  return html`${pair(state.backlog.inbox.length, t('stats.intake'))}${pair(grilled, t('stats.backlog'))}${batchPart}${pair(by('working'), t('stats.working'))}${pair(by('ready'), t('stats.handed'))}${spent}`;
}

function navOf(kind, current, counts) {
  const cell = (view) => {
    const here = view === current;
    const lead = html`<span class="ic">${icon(view)}</span>${t(`nav.${view}`)}`;
    if (kind === 'bottom') {
      return html`<button class="${here ? 'on' : ''}" type="button" data-v="${view}" aria-current="${here ? 'page' : 'false'}">${lead}</button>`;
    }
    const count = html`<span class="n">${counts[view] ?? ''}</span>`;
    return html`<button class="nav ${here ? 'on' : ''}" type="button" data-v="${view}" aria-current="${here ? 'page' : 'false'}">${lead}${count}</button>`;
  };
  return html`${VIEWS.map(cell)}`;
}

// The project's button: the mark, the name, a caret only when the board serves a surface.
function projectOf(kind, project, surface) {
  if (!project) return html``;
  const caret = surface ? html`<span class="car">${icon('chev')}</span>` : '';
  const mark_ = html`<span class="mark" data-mark="${mark(project)}">${[...project][0]}</span>`;
  const inner = html`${mark_}<b>${project}</b>${caret}`;
  const look = kind === 'side' ? 'ws' : 'pbtn';
  if (!surface) return html`<div class="${look}">${inner}</div>`;
  const label = t('project.change');
  return html`<button class="${look}" type="button" aria-label="${label}" title="${label}">${inner}</button>`;
}

function paintChrome(s) {
  const surface = Boolean(s.board?.surface);
  const counts = countsOf(s.state);
  const view = MODULES[s.view];
  put($('#project-side'), projectOf('side', s.project, surface));
  put($('#project-phone'), projectOf('phone', s.project, surface));
  put($('#views-label'), html`${t('nav.views')}`);
  put($('#side-nav'), navOf('side', s.view, counts));
  put($('#bottom-nav'), navOf('bottom', s.view, counts));
  put($('#title'), html`${t(view.title)}`);
  put($('#stats'), statsOf(s.state));
  put($('#lang'), html`${wordOf(nextLanguage(), 'lang.name')}`);
  document.title = `${t(view.title)} · chantier board`;
}

function paintNotice(s) {
  const notice = $('#notice');
  const text = s.denied ? t('notice.key') : silent(s.fails) ? t('notice.silent') : '';
  notice.hidden = !text;
  put(notice, html`${text}`);
}

export function paintHeard() {
  const s = snapshot();
  const heard = s.heard ? t('heard.at', { age: waited(s.heard) }) : t('heard.never');
  put($('#heard'), html`${heard}`);
}

function paintBody(s) {
  const same = body && body.view === s.view && body.project === s.project && body.state === s.state;
  if (same && body.language === language()) return;
  body = { view: s.view, project: s.project, state: s.state, language: language() };
  MODULES[s.view].render(s, $('#view'));
}

function paint(s) {
  paintChrome(s);
  paintNotice(s);
  paintHeard();
  paintBody(s);
}

function onClick(event) {
  const target = event.target.closest('[data-v]');
  if (target) go({ view: target.dataset.v });
}

function onLanguage() {
  setLanguage(nextLanguage());
  paint(snapshot());
}

// Wire the page once: the clicks, the language button, the store, the foot's clock.
export function mount() {
  document.addEventListener('click', onClick);
  $('#lang').addEventListener('click', onLanguage);
  subscribe(paint);
  setInterval(paintHeard, 1000);
  paint(snapshot());
}
