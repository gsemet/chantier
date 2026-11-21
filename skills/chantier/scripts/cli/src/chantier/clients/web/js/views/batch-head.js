// The Batch page's slot in the title row (`#batch-mode`): the mode and its steering as a pill whose
// tooltip holds the mode's sentence, the "States and arrows" legend pill with its hint, then the
// Stack / Series / Parallel switch at the row's right end. The title row is outside the page's
// `.batch`, so the markup is styled under `.bmode`.
//   batchMode(state) returns the slot's markup, or '' where the page has none.

import { html } from '../core/dom.js';
import { ALL } from '../core/router.js';
import { shownRecord } from '../model/history.js';
import { modeWords, noCrYet, STATE_ORDER, steeringWord } from '../model/semantics.js';
import { t } from '../model/words.js';
import { stateIcon } from '../ui/parts.js';

const MODES = ['stack', 'series', 'parallel'];

// The mode pill names the mode and the steering ("Stack · Foreman"); its sentence is its tooltip.
const modePill = (batch) => {
  const words = modeWords(batch.mode);
  return html`<span class="mpill" tabindex="0" aria-describedby="mtip">${words.name} · ${steeringWord(batch)}<span class="tip" id="mtip" role="tooltip">${words.text}</span></span>`;
};

// The three modes; the current one is `on`. It shows the mode and changes nothing.
const modeSwitch = (batch) =>
  html`<span class="ms">${MODES.map((m) => html`<span class="${m === batch.mode ? 'on' : ''}">${t(`mode.${m}`)}</span>`)}</span>`;

// "States and arrows": a grey pill that opens a tooltip on hover and on focus. It is in the title
// row, so it stays visible on every tab: the Gantt's segments use the same colours.
const legend = () =>
  html`<div class="lgrow"><span class="lgpill" tabindex="0" aria-describedby="lgtip">${t('batch.legend')}<span class="tip" id="lgtip" role="tooltip">${STATE_ORDER.map((s) => html`<span class="k">${stateIcon(s)}${t(`state.${s}`)}</span>`)}<span class="k an">${t('batch.arrow')}</span></span></span><span class="lghint">${t('batch.legend_hint')}</span></div>`;

export function batchMode(state) {
  if (state.project === ALL || state.view !== 'batch' || !state.data) return '';
  const record = shownRecord(state.data, state.batchId);
  if (record)
    return html`${record.mode ? modePill(record) : ''}${legend()}${record.mode ? modeSwitch(record) : ''}`;
  const batch = state.data.batch;
  if (!batch) return '';
  if (noCrYet(batch)) return html`${modePill(batch)}${modeSwitch(batch)}`;
  return html`${modePill(batch)}${legend()}${modeSwitch(batch)}`;
}
