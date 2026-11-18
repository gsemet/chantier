// The Batch view: four figures, the mode strip, the legend, three tabs on the same batch (the graph
// of the CRs by dependency, the Gantt, the time cards) and the PR column. The graph's arrows are
// measured, so they are drawn in `after` and on a resize. The Gantt and the time cards are modules
// of their own, imported when their tab is first opened; a tab's module has
// `render(state)`, `mount(root)` (returns a cleanup) and `after(root, state)`.
//   render(state) returns the view's markup; mount(root, state) returns a cleanup;
//   after(root, state) runs after each paint.

import { $, delegate, html } from '../core/dom.js';
import { usd } from '../core/format.js';
import { TABS } from '../core/router.js';
import { snapshot, update } from '../core/store.js';
import { mergedOf, recordRows, shownRecord, totalOf } from '../model/history.js';
import { counts, modeWords, noCrYet, STATE_ORDER, steeringWord } from '../model/semantics.js';
import { t } from '../model/words.js';
import { bindOpen } from '../ui/open.js';
import { empty, kpi, meter, stateIcon } from '../ui/parts.js';
import { bindLight, drawEdges, graphBlock } from './batch-graph.js';
import { bindGateLinks } from './batch-pr-card.js';
import { prsBlock } from './batch-prs.js';

const MODES = ['stack', 'series', 'parallel'];

// "States and arrows": a grey pill that opens a tooltip on hover and on focus. It stays on top of
// every tab: the Gantt's segments use the same colours.
const legend = () =>
  html`<div class="lgrow"><span class="lgpill" tabindex="0" aria-describedby="lgtip">${t('batch.legend')}<span class="tip" id="lgtip" role="tooltip">${STATE_ORDER.map((s) => html`<span class="k">${stateIcon(s)}${t(`state.${s}`)}</span>`)}<span class="k an">${t('batch.arrow')}</span></span></span><span class="lghint">${t('batch.legend_hint')}</span></div>`;

// The tabs are the one chip in its toggle form: filled when on, outlined grey when off.
const tabBar = (current) =>
  html`<div class="tabs" role="tablist" aria-label="${t('batch.tabs')}">${TABS.map((id) => html`<button type="button" role="tab" id="tab-${id}" class="tag tab${id === current ? '' : ' off'}" aria-selected="${id === current}" aria-controls="tabpanel" tabindex="${id === current ? 0 : -1}" data-tab="${id}" data-key="tab-${id}">${t(`batch.tab_${id}`)}</button>`)}</div>`;

const panelOf = (tab, content) =>
  html`<div role="tabpanel" id="tabpanel" aria-labelledby="tab-${tab}">${content}</div>`;

// The modules of the Gantt and the time cards, each imported on its tab's first opening. An entry
// holds the module once there, or `failed` after a failed import (the next opening tries again).
const LOADERS = {
  gantt: () => import('./batch-gantt.js'),
  cards: () => import('./batch-timecards.js'),
};
const entries = new Map();

function entryOf(tab) {
  if (!entries.has(tab)) {
    const entry = { module: null, failed: false };
    entries.set(tab, entry);
    LOADERS[tab]().then(
      (module) => {
        entry.module = module;
        update({});
      },
      () => {
        entry.failed = true;
        update({});
      },
    );
  }
  return entries.get(tab);
}

// The panel of a live batch's Gantt or time cards: the module once loaded, else a short line.
function lazyTab(state) {
  const entry = entryOf(state.batchTab);
  if (entry.module) return entry.module.render(state);
  return html`<p class="note">${t(entry.failed ? 'batch.tab_failed' : 'batch.tab_loading')}</p>`;
}

// "N queued", and the CR the batch would start next when it names one.
const slotsSub = (batch, c) => {
  const next = batch.crs.find((r) => r.next_to_start);
  const queued = t('batch.queued', { n: c.queued });
  return next ? t('batch.queued_next', { q: queued, cr: next.cr }) : queued;
};

function figures(batch) {
  const c = counts(batch);
  const spent = meter([{ n: batch.spent_usd ?? 0, color: 'var(--accent)' }], batch.budget_usd);
  return html`<div class="bhead">${kpi({ label: t('batch.slots'), value: `${batch.slots?.taken ?? 0}/${batch.slots?.total ?? 0}`, sub: slotsSub(batch, c) })}${kpi({ label: t('batch.working'), value: c.working, sub: t('batch.blocked', { n: c.blocked }) })}${kpi({ label: t('batch.handed_ready'), value: c.ready, sub: t('batch.review_merged', { a: c.review, b: c.merged }) })}${kpi({ label: t('batch.spent'), value: usd(batch.spent_usd), extra: spent, sub: t('batch.of_budget', { budget: usd(batch.budget_usd) }) })}</div>`;
}

// The strip names the mode and the steering ("Stack · Foreman"), its sentence, and the three modes.
function modeBand(batch) {
  const words = modeWords(batch.mode);
  const switches = MODES.map(
    (m) => html`<span class="${m === batch.mode ? 'on' : ''}">${t(`mode.${m}`)}</span>`,
  );
  return html`<div class="mode"><span class="mb">${words.name} · ${steeringWord(batch)}</span><span>${words.text}</span><span class="ms">${switches}</span></div>`;
}

// A closed record's figures: merged of the total, the dropped ones, the rounds summed, spent against
// the budget; from the record only.
function recordFigures(rec) {
  const rounds = (rec.crs ?? []).reduce((n, c) => n + (c.rounds ?? 0), 0);
  const spent = meter([{ n: rec.cost_usd ?? 0, color: 'var(--accent)' }], rec.budget_usd);
  return html`<div class="bhead">${kpi({ label: t('batch.rec_merged'), value: `${mergedOf(rec)}/${totalOf(rec)}`, sub: t('batch.rec_merged_sub', { n: totalOf(rec) }) })}${kpi({ label: t('batch.rec_dropped'), value: totalOf(rec) - mergedOf(rec), sub: t('state.cancelled') })}${kpi({ label: t('batch.rec_rounds'), value: rounds, sub: t('batch.rec_rounds_sub') })}${kpi({ label: t('batch.spent'), value: usd(rec.cost_usd), extra: spent, sub: t('batch.of_budget', { budget: usd(rec.budget_usd) }) })}</div>`;
}

const DEPS_LINE = { archives: 'batch.deps_partial', none: 'batch.deps_none' };

// The Batch page on a closed batch: its graph from the record, with its arrows; no PR column. Its
// record keeps no events, so the Gantt and the time cards show only a note (nothing is imported).
function recorded(rec, state) {
  const line = DEPS_LINE[rec.after_source];
  const note = line ? html`<p class="note">${t(line)}</p>` : '';
  const mode = rec.mode ? modeBand(rec) : '';
  const graph = graphBlock(recordRows(rec), rec, state.now, true);
  const panel =
    state.batchTab === 'graph' ? graph : html`<p class="note">${t('batch.times_none')}</p>`;
  return html`<div class="batch">${recordFigures(rec)}${mode}<div class="bwrap one"><div class="gcol">${note}${legend()}${tabBar(state.batchTab)}${panelOf(state.batchTab, panel)}</div></div></div>`;
}

export function render(state) {
  const record = shownRecord(state.data, state.batchId);
  if (record) return recorded(record, state);
  const batch = state.data.batch;
  if (!batch) return empty(t('batch.none'));
  if (noCrYet(batch)) {
    return html`<div class="batch">${figures(batch)}${modeBand(batch)}${empty(t('batch.no_cr_yet'))}</div>`;
  }
  const graph = state.batchTab === 'graph';
  const panel = graph ? graphBlock(batch.crs, batch, state.now) : lazyTab(state);
  return html`<div class="batch">${figures(batch)}${modeBand(batch)}<div class="bwrap"><div class="gcol">${legend()}${tabBar(state.batchTab)}${panelOf(state.batchTab, panel)}</div>${prsBlock(state)}</div></div>`;
}

// The rows the page draws now: a closed record's, or the live batch's.
function rowsNow() {
  const { data, batchId } = snapshot();
  const record = shownRecord(data, batchId);
  return record ? recordRows(record) : (data?.batch?.crs ?? []);
}

// The graph tab: the arrows follow the layout, a resize redraws them once per frame, and a hover
// lights a CR.
const graphTab = {
  mount(root) {
    let frame = 0;
    const onResize = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => drawEdges(root, rowsNow()));
    };
    window.addEventListener('resize', onResize);
    // The font changes the nodes' sizes: the arrows are drawn again once it is loaded.
    let alive = true;
    document.fonts?.ready.then(() => alive && onResize());
    const stop = bindLight(root, rowsNow);
    return () => {
      alive = false;
      window.removeEventListener('resize', onResize);
      cancelAnimationFrame(frame);
      stop();
    };
  },
  after: (root) => drawEdges(root, rowsNow()),
};

// The module of the open tab: the graph, the Gantt or the time cards once loaded; none while one is
// loading or when a closed record shows only its note.
function tabModule(state) {
  if (state.batchTab === 'graph') return graphTab;
  if (shownRecord(state.data, state.batchId)) return null;
  return entries.get(state.batchTab)?.module ?? null;
}

// Left and right move between the tabs: the next tab is clicked, as a pointer would.
function arrows(event, tab) {
  const step = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
  if (!step) return;
  const next = TABS[(TABS.indexOf(tab.dataset.tab) + step + TABS.length) % TABS.length];
  const button = $(`[data-tab="${next}"]`, tab.parentElement);
  event.preventDefault();
  button?.click();
  button?.focus();
}

let mounted = null; // the module whose `mount` is live
let unmount = null;

export function mount(root) {
  const off = [
    bindOpen(root),
    bindGateLinks(root),
    delegate(root, 'keydown', '[role="tab"]', arrows),
  ];
  return () => {
    unmount?.();
    mounted = null;
    unmount = null;
    for (const stop of off) stop();
  };
}

// A tab change cleans up the previous tab's listeners and mounts the new one's; a tab that failed
// to load is forgotten once left, so its next opening imports it again.
export function after(root, state) {
  const module = tabModule(state);
  if (module !== mounted) {
    unmount?.();
    mounted = module;
    unmount = module?.mount?.(root, state) ?? null;
  }
  for (const [tab, entry] of entries)
    if (entry.failed && tab !== state.batchTab) entries.delete(tab);
  module?.after?.(root, state);
}
