// The Dashboard view: the figures of one project's closed batches (on All projects, of every
// project's, summed per batch number), one point per batch, on two
// tabs (Productivity, Spending) and a range (the last 10, the last 20, all). Read-only: the figures
// are the server's (`dashboard.get`, board/dashboard_page.py) and this view only draws them. The
// tab and the range are in the address (`dt=`, `dr=`); the Spending tab's switch is Costs' own.
//   render(state) returns the view's markup; mount(root) returns a cleanup.

import { $, delegate, html } from '../core/dom.js';
import { ALL, DASH_RANGES, DASH_TABS, go } from '../core/router.js';
import { snapshot } from '../core/store.js';
import { t } from '../model/words.js';
import { bindCharts } from '../ui/chart.js';
import { empty } from '../ui/parts.js';
import { projectsOf } from '../ui/picker.js';
import { bindSpendBy } from './costs-models.js';
import { startFeed } from './dashboard-feed.js';
import { bindTop, spending } from './dashboard-spend.js';
import { productivity } from './dashboard-tiles.js';

const tabBar = (current) =>
  html`<div class="tabs" role="tablist" aria-label="${t('dashboard.tabs')}">${DASH_TABS.map((id) => html`<button type="button" role="tab" id="dash-tab-${id}" class="tag tab${id === current ? '' : ' off'}" aria-selected="${id === current}" aria-controls="dash-panel" tabindex="${id === current ? 0 : -1}" data-dash-tab="${id}" data-key="dash-tab-${id}">${t(`dashboard.tab_${id}`)}</button>`)}</div>`;

// The range selector: the Costs card's segmented control (`.seg`), reused as it is.
const rangeBar = (current) =>
  html`<div class="seg" role="group" aria-label="${t('dashboard.range')}">${DASH_RANGES.map((id) => html`<button type="button" data-dash-range="${id}" data-key="dash-range-${id}" aria-pressed="${id === current}">${t(`dashboard.range_${id}`)}</button>`)}</div>`;

// On All projects, one line per project with a running or paused batch, each leading to that
// project's Costs.
function liveAll(state) {
  const lines = projectsOf(state)
    .filter((p) => p.batch && ['running', 'paused'].includes(p.batch.state))
    .map((p) => {
      const [before, after] = t('dashboard.live_all', {
        project: p.id,
        batch: p.batch.id,
        link: '{link}',
      }).split('{link}');
      return html`<p class="mut">${before}<button type="button" class="dlink" data-dash-costs="${p.id}" data-key="dash-live-${p.id}">${t('dashboard.live_link')}</button>${after}</p>`;
    });
  return html`${lines}`;
}

// On All projects, one link per project opens that project's Dashboard on the same tab and range.
function perProject(state) {
  const links = projectsOf(state).map(
    (p) =>
      html`<button type="button" class="dlink" data-dash-project="${p.id}" data-key="dash-project-${p.id}">${p.id}</button>`,
  );
  return html`<p class="mut dprojects" data-key="dash-projects">${t('dashboard.per_project')} ${links}</p>`;
}

// The running or paused batch has no point: one line says so and leads to Costs.
function live(state) {
  if (state.project === ALL) return liveAll(state);
  const batch = state.data?.batch?.id;
  if (!batch) return '';
  const [before, after] = t('dashboard.live', { batch, link: '{link}' }).split('{link}');
  return html`<p class="mut">${before}<button type="button" class="dlink" data-go="costs" data-key="dash-live">${t('dashboard.live_link')}</button>${after}</p>`;
}

const problem = (d, kept) =>
  html`<div class="derr" data-key="dash-error">${t('dashboard.error', { error: d.error })} ${kept ? t('dashboard.error_kept') : ''}</div>`;

// What the tab shows under the head: the loading line until the answer for this project and this
// range is there, the error, the empty state, or the tiles.
function body(state) {
  const d = state.dashboard;
  const fit = d?.answer && d.project === state.project && d.range === state.dashRange;
  if (!fit) return d?.error ? problem(d, false) : empty(t('stats.loading'));
  const a = d.answer;
  const err = d.error ? problem(d, true) : '';
  if (a.closed_total === 0) return html`${err}${empty(t('dashboard.none'))}`;
  const tiles =
    state.dashTab === 'spending'
      ? spending(a, state.spendBy ?? 'model', state.project === ALL)
      : productivity(a);
  return html`${err}<div class="dgrid dgrid-${state.dashTab}">${tiles}</div>`;
}

export function render(state) {
  const tab = state.dashTab;
  const projects = state.project === ALL ? perProject(state) : '';
  return html`<div class="dash"><div class="dhead">${tabBar(tab)}${rangeBar(state.dashRange)}</div>${projects}${live(state)}<div role="tabpanel" id="dash-panel" aria-labelledby="dash-tab-${tab}">${body(state)}</div></div>`;
}

// Left and right move between the tabs: the next tab is clicked, as a pointer would.
function arrows(event, tab) {
  const step = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
  if (!step) return;
  const next =
    DASH_TABS[
      (DASH_TABS.indexOf(tab.dataset.dashTab) + step + DASH_TABS.length) % DASH_TABS.length
    ];
  const button = $(`[data-dash-tab="${next}"]`, tab.parentElement);
  event.preventDefault();
  button?.click();
  button?.focus();
}

// A tab or a range chosen is a move of the address (Back returns to the previous one), unless it
// is the one already shown.
function choose(key, value) {
  const state = snapshot();
  if (value !== (key === 'dt' ? state.dashTab : state.dashRange))
    go({ view: 'dashboard', [key]: value });
}

export function mount(root) {
  const offs = [
    delegate(root, 'click', '[data-dash-project]', (_, b) => {
      const { dashTab, dashRange } = snapshot();
      go({ project: b.dataset.dashProject, view: 'dashboard', dt: dashTab, dr: dashRange });
    }),
    delegate(root, 'click', '[data-dash-costs]', (_, b) =>
      go({ project: b.dataset.dashCosts, view: 'costs' }),
    ),
    delegate(root, 'click', '[data-dash-tab]', (_, b) => choose('dt', b.dataset.dashTab)),
    delegate(root, 'click', '[data-dash-range]', (_, b) => choose('dr', b.dataset.dashRange)),
    delegate(root, 'keydown', '[role="tab"]', arrows),
    bindSpendBy(root),
    bindCharts(root),
    bindTop(root),
    startFeed(),
  ];
  return () => {
    for (const off of offs) off();
  };
}
