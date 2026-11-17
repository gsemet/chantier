// The Batch view: four figures, the mode strip, the graph of the CRs by dependency and the PR
// column. The graph's arrows are measured, so they are drawn in `after` and on a resize.
//   render(state) returns the view's markup; mount(root, state) returns a cleanup;
//   after(root) runs after each paint.

import { html } from '../core/dom.js';
import { usd } from '../core/format.js';
import { snapshot } from '../core/store.js';
import { mergedOf, recordRows, shownRecord, totalOf } from '../model/history.js';
import { counts, modeWords, steeringWord } from '../model/semantics.js';
import { t } from '../model/words.js';
import { bindOpen } from '../ui/open.js';
import { empty, kpi, meter } from '../ui/parts.js';
import { bindLight, drawEdges, graphBlock } from './batch-graph.js';
import { bindGateLinks } from './batch-pr-card.js';
import { prsBlock } from './batch-prs.js';

const MODES = ['stack', 'series', 'parallel'];

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

// The Batch page on a closed batch: its graph from the record, with its arrows; no PR column.
function recorded(rec, state) {
  const line = DEPS_LINE[rec.after_source];
  const note = line ? html`<p class="note">${t(line)}</p>` : '';
  const mode = rec.mode ? modeBand(rec) : '';
  return html`<div class="batch">${recordFigures(rec)}${mode}<div class="bwrap one"><div class="gcol">${note}${graphBlock(recordRows(rec), rec, state.now, true)}</div></div></div>`;
}

export function render(state) {
  const record = shownRecord(state.data, state.batchId);
  if (record) return recorded(record, state);
  const batch = state.data.batch;
  if (!batch) return empty(t('batch.none'));
  return html`<div class="batch">${figures(batch)}${modeBand(batch)}<div class="bwrap"><div class="gcol">${graphBlock(batch.crs, batch, state.now)}</div>${prsBlock(state)}</div></div>`;
}

// The rows the page draws now: a closed record's, or the live batch's.
function rowsNow() {
  const { data, batchId } = snapshot();
  const record = shownRecord(data, batchId);
  return record ? recordRows(record) : (data?.batch?.crs ?? []);
}

// The arrows follow the layout: a resize redraws them, once per frame.
export function mount(root) {
  let frame = 0;
  const onResize = () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => drawEdges(root, rowsNow()));
  };
  window.addEventListener('resize', onResize);
  // The font changes the nodes' sizes: the arrows are drawn again once it is loaded.
  let alive = true;
  document.fonts?.ready.then(() => alive && onResize());
  const off = [bindOpen(root), bindLight(root, rowsNow), bindGateLinks(root)];
  return () => {
    alive = false;
    window.removeEventListener('resize', onResize);
    cancelAnimationFrame(frame);
    for (const stop of off) stop();
  };
}

export function after(root) {
  drawEdges(root, rowsNow());
}
