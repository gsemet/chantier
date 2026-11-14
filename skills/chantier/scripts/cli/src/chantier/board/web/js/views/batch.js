// The Batch view: five figures, the mode band, the graph of the CRs by dependency and the PR
// columns. The graph's arrows are measured, so they are drawn in `after` and on a resize.
//   render(state) returns the view's markup; mount(root, state) returns a cleanup;
//   after(root, state) runs after each paint.

import { html } from '../core/dom.js';
import { usd } from '../core/format.js';
import { snapshot } from '../core/store.js';
import { counts, modeWords, steeringWord } from '../model/semantics.js';
import { t } from '../model/words.js';
import { bindOpen } from '../ui/open.js';
import { empty, kpi, meter } from '../ui/parts.js';
import { bindLight, drawEdges, graphBlock } from './batch-graph.js';
import { prsBlock } from './batch-prs.js';

const MODES = ['stack', 'series', 'parallel'];

function figures(batch) {
  const c = counts(batch);
  const spent = meter([{ n: batch.spent_usd ?? 0, color: 'var(--blue)' }], batch.budget_usd);
  return html`<div class="bhead">${kpi({ label: t('batch.batch'), value: batch.id, sub: `${batch.state} · ${t(`mode.${batch.mode}`)} · ${steeringWord(batch)}` })}${kpi({ label: t('batch.slots'), value: `${batch.slots?.taken ?? 0}/${batch.slots?.total ?? 0}`, sub: t('batch.queued', { n: c.queued }) })}${kpi({ label: t('batch.working'), value: c.working, sub: t('batch.blocked', { n: c.blocked }) })}${kpi({ label: t('batch.handed_ready'), value: c.ready, sub: t('batch.review_merged', { a: c.review, b: c.merged }) })}${kpi({ label: t('batch.spent'), value: usd(batch.spent_usd), extra: spent, sub: t('batch.of_budget', { budget: usd(batch.budget_usd) }) })}</div>`;
}

function modeBand(batch) {
  const words = modeWords(batch.mode);
  const switches = MODES.map(
    (m) => html`<span class="${m === batch.mode ? 'on' : ''}">${t(`mode.${m}`)}</span>`,
  );
  return html`<div class="mode mode-${batch.mode}"><span class="mb">${words.name}</span><span>${words.text}</span><span class="ms">${switches}</span></div>`;
}

export function render(state) {
  const batch = state.data.batch;
  if (!batch) return empty(t('batch.none'));
  return html`<div class="batch">${figures(batch)}${modeBand(batch)}<div class="bwrap"><div class="gscroll">${graphBlock(batch)}</div>${prsBlock(state)}</div></div>`;
}

const rowsNow = () => snapshot().data?.batch?.crs ?? [];

// The arrows follow the layout: a resize redraws them, once per frame.
export function mount(root) {
  let frame = 0;
  const onResize = () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => drawEdges(root, rowsNow()));
  };
  window.addEventListener('resize', onResize);
  const off = [bindOpen(root), bindLight(root, rowsNow)];
  return () => {
    window.removeEventListener('resize', onResize);
    cancelAnimationFrame(frame);
    for (const stop of off) stop();
  };
}

export function after(root, state) {
  if (state.data.batch) drawEdges(root, state.data.batch.crs);
}
