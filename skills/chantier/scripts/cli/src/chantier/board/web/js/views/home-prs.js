// Home, the open PRs block, and under it the blocked CRs with their reason.
import { html } from '../core/dom.js';
import { prNumber } from '../core/format.js';
import { crsOf } from '../model/semantics.js';
import { crKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { opener } from '../ui/open.js';
import { stateTag } from '../ui/parts.js';

const prRow = (c) =>
  html`<div class="x" ${opener(crKey(c), 'pr-')}>${stateTag(c)}<b>${c.cr}</b><span class="ell">${c.title}</span><span class="r">${prNumber(c.pr)}</span></div>`;

const blockedRow = (c) =>
  html`<div class="x" ${opener(crKey(c), 'bl-')}><b>${c.cr}</b><span class="ell">${c.blocked ?? ''}</span></div>`;

export function prsBlock(state) {
  const rows = crsOf(state.data.batch);
  const prs = rows.filter((c) => c.pr && c.state !== 'merged');
  const blocked = rows.filter((c) => c.state === 'blocked');
  const list = prs.length ? prs.map(prRow) : html`<div class="none">${t('home.none')}</div>`;
  const stuck = blocked.length
    ? html`<h3>${t('home.blocked_head')}</h3><div class="list">${blocked.map(blockedRow)}</div>`
    : '';
  return html`<section class="block side"><h2>${t('home.open_prs')} <span class="sub">${prs.length}</span></h2><div class="list">${list}</div>${stuck}</section>`;
}
