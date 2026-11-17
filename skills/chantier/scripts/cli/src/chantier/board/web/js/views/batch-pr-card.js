// The cards of the Batch's PR columns. A card is a link to the PR when its address is a web one,
// else a plain box. The folder control opens the CR's folder and leaves the link alone.
import { delegate, html } from '../core/dom.js';
import { prNumber, safeUrl, usd } from '../core/format.js';
import {
  baseOf,
  draftWhy,
  gateLink,
  gateWords,
  isFix,
  isRelease,
  placeOf,
} from '../model/semantics.js';
import { crKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { icon } from '../ui/icons.js';
import { opener } from '../ui/open.js';

// The card's outer element: a link, or a box when the PR has no web address.
function shell(c, cls, inner) {
  const url = safeUrl(c.pr);
  const names = `prc card ${cls}`;
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

// The long gate's line: its words, and for a covered CR a link to the PR of the CR that validates
// it. The card is a link already: the inner one is a span that `bindGateLinks` opens.
function gateLine(c) {
  const words = gateWords(c);
  if (!words) return '';
  const url = gateLink(c);
  const text = url
    ? html`<span class="gl" data-gate-pr="${url}" tabindex="0" role="link" title="${t('gate.open')}">${words}</span>`
    : html`<span>${words}</span>`;
  return html`<span class="gate"><span class="lbl">${t('gate.label')}</span>${text}</span>`;
}

// A click, or Enter, on a gate link opens the validating PR and leaves the card's own link alone.
export function bindGateLinks(root) {
  const go = (event, element) => {
    event.preventDefault();
    event.stopPropagation();
    window.open(element.dataset.gatePr, '_blank', 'noopener');
  };
  const offClick = delegate(root, 'click', '[data-gate-pr]', go);
  const offKey = delegate(root, 'keydown', '[data-gate-pr]', (event, element) => {
    if (event.key === 'Enter') go(event, element);
  });
  return () => {
    offClick();
    offKey();
  };
}

function body(c, line, why, cost) {
  const second = why ? html`<span>${why}</span>` : '';
  return html`<div class="nt">${c.title}</div><div class="nm"><span>${line}</span>${second}<span class="r">${cost}${folder(c)}</span>${gateLine(c)}</div>`;
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
