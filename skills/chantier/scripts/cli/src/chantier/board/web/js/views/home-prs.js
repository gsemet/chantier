// Home, the open PRs block, and under it the blocked CRs with their reason.
import { html } from '../core/dom.js';
import { isMergeRequest, prNumber, safeUrl, title } from '../core/format.js';
import { crsOf, openPr } from '../model/semantics.js';
import { crKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { opener } from '../ui/open.js';
import { stateTag } from '../ui/parts.js';

// The row is a link to the PR or MR (a box when it has no web address); the CR's number inside it
// opens the CR's folder and leaves the link alone.
function prRow(c) {
  const inner = html`${stateTag(c)}<b ${opener(crKey(c), 'pr-')} title="${t('pr.folder')}">${c.cr}</b><span class="ell" title="${title(c.title)}">${title(c.title)}</span><span class="r">${prNumber(c.pr)}</span>`;
  const url = safeUrl(c.pr);
  if (!url) return html`<div class="x">${inner}</div>`;
  const words = isMergeRequest(url) ? t('mr.open') : t('pr.open');
  return html`<a class="x" href="${url}" target="_blank" rel="noopener" data-key="prl-${c.cr}" title="${words}">${inner}</a>`;
}

const blockedRow = (c) =>
  html`<div class="x" ${opener(crKey(c), 'bl-')}><b>${c.cr}</b><span class="ell">${c.blocked ?? ''}</span></div>`;

export function prsBlock(state) {
  const rows = crsOf(state.data.batch);
  const prs = rows.filter(openPr);
  const blocked = rows.filter((c) => c.state === 'blocked');
  const list = prs.length ? prs.map(prRow) : html`<div class="none">${t('home.none')}</div>`;
  const stuck = blocked.length
    ? html`<h3>${t('home.blocked_head')}</h3><div class="list">${blocked.map(blockedRow)}</div>`
    : '';
  return html`<section class="block side"><h2>${t('home.open_prs')} <span class="sub">${prs.length}</span></h2><div class="list">${list}</div>${stuck}</section>`;
}
