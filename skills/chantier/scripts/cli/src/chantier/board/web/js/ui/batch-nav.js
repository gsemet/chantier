// The batch navigator, next to the title of the Costs, Batch and PRs pages: `‹ batch-04 ›` and, when the
// page is not on the latest batch, a "Latest" pill. The batch shown is in the address (`b=`).
import { html } from '../core/dom.js';
import { ALL, BATCH_VIEWS } from '../core/router.js';
import { batchSequence, shownId } from '../model/history.js';
import { t } from '../model/words.js';

// The markup of the navigator, or an empty string where the page has none.
export function navigator(state) {
  if (state.project === ALL || !state.data || !BATCH_VIEWS.includes(state.view)) return '';
  const seq = batchSequence(state.data);
  if (!seq.length) return '';
  const shown = shownId(state.data, state.batchId);
  const at = seq.indexOf(shown);
  const latest = seq.length - 1;
  const arrow = (word, glyph, id, off) =>
    html`<button class="bn-arrow" type="button" data-batch-go="${id ?? ''}" aria-label="${t(word)}" ${off ? 'disabled' : ''}>${glyph}</button>`;
  const pill =
    at === latest
      ? ''
      : html`<button class="bn-pill" type="button" data-batch-go="">${t('batchnav.latest')}</button>`;
  return html`${arrow('batchnav.prev', '‹', seq[at - 1], at <= 0)}<span class="bn-id">${shown}</span>${arrow('batchnav.next', '›', seq[at + 1], at >= latest)}${pill}`;
}
