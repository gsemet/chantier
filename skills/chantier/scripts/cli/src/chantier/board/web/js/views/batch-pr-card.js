// The cards of the Batch's PR columns. A card is a link to the PR when its address is a web one,
// else a plain box. The folder control opens the CR's folder and leaves the link alone.
import { html } from '../core/dom.js';
import { age, prNumber, safeUrl, usd } from '../core/format.js';
import {
  baseOf,
  draftWhy,
  isFix,
  isRelease,
  mergedAt,
  placeOf,
  vstate,
} from '../model/semantics.js';
import { crKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { icon } from '../ui/icons.js';
import { opener } from '../ui/open.js';

// The card's outer element: a link, or a box when the PR has no web address.
function shell(c, cls, inner) {
  const url = safeUrl(c.pr);
  const names = `prc ${cls} st-${vstate(c)}`;
  if (!url) return html`<div class="${names}">${inner}</div>`;
  return html`<a class="${names}" href="${url}" target="_blank" rel="noopener" title="${t('pr.open')}">${inner}</a>`;
}

const kindTag = (c) => {
  if (isRelease(c)) return html`<span class="tag rel">${t('kind.release')}</span>`;
  return isFix(c) ? html`<span class="tag rel">${t('kind.fix')}</span>` : '';
};

// The place badge: a place in the stack, or the recommended merge order. A merged or draft PR in
// a mode that has no order shows none.
function place(c, batch, index, draft) {
  const p = placeOf(c, batch, index);
  if (!p) return '';
  if (p.kind === 'order' && (draft || batch.mode === 'stack')) return '';
  const text = p.top ? t('prs.top', { n: p.n }) : p.n;
  const hint = p.kind === 'stack' ? t('prs.place') : t('prs.order');
  return html`<span class="pos" title="${hint}">${text}</span>`;
}

const folder = (c) =>
  html`<span class="fold" ${opener(crKey(c), 'fold-')} title="${t('pr.folder')}" aria-label="${t('pr.folder')}">${icon('folder')}</span>`;

function body(c, line, why, cost) {
  const second = why ? html`<span>${why}</span>` : '';
  return html`<div class="nt">${c.title}</div><div class="nm"><span>${line}</span>${second}<span class="r">${cost}</span>${folder(c)}</div>`;
}

// A PR to review or a draft; `index` is its place in the list as drawn.
export function prCard(c, batch, index, draft) {
  const top = html`<div class="top"><b>${prNumber(c.pr)}</b><span class="tag cr">${c.cr}</span>${kindTag(c)}${place(c, batch, index, draft)}</div>`;
  const why = draft ? draftWhy(c) : '';
  return shell(
    c,
    draft ? 'draft' : '',
    html`${top}${body(c, baseOf(c, batch).text, why, usd(c.cost_usd))}`,
  );
}

// A PR of this batch that is merged.
export function mergedCard(c, now) {
  const top = html`<div class="top"><b>${prNumber(c.pr)}</b><span class="tag cr">${c.cr}</span>${kindTag(c)}</div>`;
  const line = t('prs.merged_ago', { age: age(mergedAt(c), now) });
  return shell(c, 'mrg', html`${top}${body(c, line, '', usd(c.cost_usd))}`);
}

// A PR of an earlier batch: the row the board's merged list gives.
export function earlierCard(m) {
  const url = safeUrl(m.pr);
  const inner = html`<div class="top"><b>${prNumber(m.pr)}</b><span class="tag cr">${m.cr}</span><span class="r">${m.batch}</span></div><div class="nt">${m.title}</div>`;
  if (!url) return html`<div class="prc mrg st-merged">${inner}</div>`;
  return html`<a class="prc mrg st-merged" href="${url}" target="_blank" rel="noopener">${inner}</a>`;
}
