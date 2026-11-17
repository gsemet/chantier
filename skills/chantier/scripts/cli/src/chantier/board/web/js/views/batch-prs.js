// The Batch's one PR column: the PRs to review, then the drafts (in the order the mode merges
// them). Nothing under the drafts: the merged PRs stay on their CRs' nodes.
import { html } from '../core/dom.js';
import { prLists, reviewHint } from '../model/semantics.js';
import { t } from '../model/words.js';
import { dot } from '../ui/parts.js';
import { prCard } from './batch-pr-card.js';

// A stack reads on a rail: its PRs sit on one another.
const wrap = (batch, cards) =>
  batch.mode === 'stack' ? html`<div class="stackrail">${cards}</div>` : cards;

function reviewColumn(batch) {
  const { review, drafts } = prLists(batch);
  const cards = review.map((c, i) => prCard(c, batch, i, false));
  const list = review.length
    ? html`<div class="hint">${reviewHint(batch)} ${t('prs.click')}</div>${wrap(batch, cards)}`
    : html`<div class="none">${t('prs.nothing')}</div>`;
  const sub = drafts.length
    ? html`<div class="prsub">${t('prs.drafts')} · ${drafts.length}</div>${wrap(
        batch,
        drafts.map((c, i) => prCard(c, batch, i, true)),
      )}`
    : '';
  return html`<div class="prcol"><h3>${dot('var(--state-ready)')}${t('prs.review')}<span class="c">${review.length}</span></h3>${list}${sub}</div>`;
}

export const prsBlock = (state) => html`<div class="prs">${reviewColumn(state.data.batch)}</div>`;
