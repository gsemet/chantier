// The Batch's two PR columns: the PRs to review and the drafts (in the order the mode merges
// them), and the merged ones with the earlier batches'.
import { html } from '../core/dom.js';
import { mergedAt, prLists, reviewHint } from '../model/semantics.js';
import { t } from '../model/words.js';
import { dot } from '../ui/parts.js';
import { earlierCard, mergedCard, prCard } from './batch-pr-card.js';

const EARLIER = 4;

// A stack reads on a rail: its PRs sit on one another.
const wrap = (batch, cards) =>
  batch.mode === 'stack' ? html`<div class="stackrail">${cards}</div>` : cards;

function reviewColumn(batch) {
  const { review, drafts } = prLists(batch);
  const cards = review.map((c, i) => prCard(c, batch, i, false));
  const list = review.length ? wrap(batch, cards) : html`<div class="none">${t('prs.none')}</div>`;
  const sub = drafts.length
    ? html`<div class="prsub">${t('prs.drafts')} · ${drafts.length}</div>${wrap(
        batch,
        drafts.map((c, i) => prCard(c, batch, i, true)),
      )}`
    : '';
  return html`<div class="prcol"><h3>${dot('var(--green)')}${t('prs.review')}<span class="c">${review.length}</span></h3><div class="hint">${reviewHint(batch)} ${t('prs.click')}</div>${list}${sub}</div>`;
}

function mergedColumn(batch, state) {
  const own = batch.crs
    .filter((c) => c.state === 'merged' && c.pr)
    .sort((a, b) => (mergedAt(b) ?? '').localeCompare(mergedAt(a) ?? ''));
  const earlier = (state.data.merged ?? []).filter((m) => m.batch !== batch.id).slice(0, EARLIER);
  const list = own.length
    ? own.map((c) => mergedCard(c, state.now))
    : html`<div class="none">${t('prs.none_merged')}</div>`;
  const before = earlier.length
    ? html`<div class="prsub">${t('prs.earlier')}</div>${earlier.map(earlierCard)}`
    : '';
  return html`<div class="prcol"><h3>${dot('var(--violet)')}${t('prs.merged')}<span class="c">${own.length}</span></h3><div class="hint">${t('prs.info')}</div>${list}${before}</div>`;
}

export const prsBlock = (state) =>
  html`<div class="prs">${reviewColumn(state.data.batch)}${mergedColumn(state.data.batch, state)}</div>`;
