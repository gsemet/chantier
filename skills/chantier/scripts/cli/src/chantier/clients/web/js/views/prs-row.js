// One row of the PRs view: a PR read on the forge, set against the CR the record keeps for it.
import { html } from '../core/dom.js';
import { age, prNumber, safeUrl, title } from '../core/format.js';
import { crKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { icon } from '../ui/icons.js';
import { opener } from '../ui/open.js';
import { stateIcon, tag } from '../ui/parts.js';

const TAGS = { open: 'queued', draft: 'draft', merged: 'merged', closed: 'blocked' };

// The checks' icon, as a state's: green is ready, failing is blocked, running waits.
const CHECK_ICON = { green: 'ready', failing: 'blocked', running: 'waits' };

const folder = (row) =>
  html`<span class="fold" ${opener(crKey(row), 'pv-')} title="${t('pr.folder')}" aria-label="${t('pr.folder')}">${icon('folder')}</span>`;

const kind = (row) => (row.kind ? tag('rel', t(`kind.${row.kind}`)) : '');

// The checks as the forge says them. A check the forge has not computed yet is "being checked",
// never "none".
function checks(row) {
  if (row.state === 'merged' || row.state === 'closed') return '';
  if (row.checking) return html`<span class="wait">${stateIcon('waits')}${t('pv.checking')}</span>`;
  const cls = row.checks === 'failing' ? 'bad' : '';
  const mark = CHECK_ICON[row.checks];
  return html`<span class="${cls}">${mark ? stateIcon(mark) : ''}${t(`pv.checks.${row.checks}`)}</span>`;
}

const conflict = (row) => {
  if (row.state === 'merged' || row.state === 'closed' || row.checking) return '';
  return row.conflicting
    ? html`<span class="bad">${t('pv.conflicting')}</span>`
    : html`<span>${t('pv.clean')}</span>`;
};

// Where a merged PR went: the branch, and the CR whose branch it is when it is one.
function into(row) {
  const m = row.merged_into;
  if (!m) return '';
  const words = m.cr
    ? t('pv.into_cr', { branch: m.branch, cr: m.cr })
    : t('pv.into', { branch: m.branch });
  return html`<span>${words}</span>`;
}

const readyNow = (row) => {
  if (row.state === 'merged' || row.state === 'closed') return '';
  return row.ready_now
    ? html`<span class="ok">${t('pv.ready_yes')}</span>`
    : html`<span>${t('pv.ready_no')}</span>`;
};

// The date the row is sorted by (opened, last activity); under the other sorts, the merge or
// close date.
const SORT_DATE = {
  opened: ['opened_at', 'pv.opened_ago'],
  activity: ['updated_at', 'pv.active_ago'],
};

const when = (row, now, sort) => {
  const [field, word] = SORT_DATE[sort] ?? [];
  if (field && row[field]) return html`<span>${t(word, { age: age(row[field], now) })}</span>`;
  if (row.state === 'merged' && row.merged_at) {
    return html`<span>${t('pv.merged_ago', { age: age(row.merged_at, now) })}</span>`;
  }
  if (row.state === 'closed' && row.closed_at) {
    return html`<span>${t('pv.closed_ago', { age: age(row.closed_at, now) })}</span>`;
  }
  return '';
};

const WHY = {
  merged: 'pv.merged_not_recorded',
  draft: 'pv.dis.draft',
  closed: 'pv.dis.closed',
  conflicting: 'pv.dis.conflicting',
  failing: 'pv.dis.failing',
};

const disagreement = (row) => (row.why ? html`<div class="why">${t(WHY[row.why])}</div>` : '');

// The time of the forge read the row comes from, by the answer's own clock.
const readAt = (readTime, now) =>
  readTime ? html`<span>${t('pv.read', { age: age(readTime, now) })}</span>` : '';

// The row is a link to the PR (a box when it has no web address); the folder icon inside opens the
// CR's folder, as on the Batch view. `sort` is the page's sort: the row shows the date it is
// sorted by.
export function prRow(row, now, readTime, sort) {
  const number = html`<b>${prNumber(row.pr)}</b>`;
  const top = html`<div class="top">${number}<span class="tag cr">${row.cr}</span>${kind(row)}${tag('st', html`${stateIcon(TAGS[row.state] ?? 'queued')}${t(`pv.state.${row.state}`)}`)}${folder(row)}</div>`;
  const facts = html`<div class="facts">${conflict(row)}${checks(row)}${into(row)}${readyNow(row)}${when(row, now, sort)}${readAt(readTime, now)}</div>`;
  const inner = html`${top}<div class="nt" title="${title(row.title)}">${title(row.title)}</div>${facts}${disagreement(row)}`;
  const names = 'pvrow';
  const url = safeUrl(row.pr);
  if (!url) return html`<div class="${names}" data-key="pv-${row.cr}">${inner}</div>`;
  return html`<a class="${names}" data-key="pv-${row.cr}" href="${url}" target="_blank" rel="noopener" title="${t('pr.open')}">${inner}</a>`;
}
