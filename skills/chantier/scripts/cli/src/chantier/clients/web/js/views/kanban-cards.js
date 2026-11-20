// The cards of the Kanban for a CR of the batch and for a merged one (the item's card is shared with
// Triage: ui/item-card.js). Each has empty `place` elements that a later change fills, and opens
// its folder.
import { html } from '../core/dom.js';
import { slug, title, usd } from '../core/format.js';
import { roundLimit, roundText, vstate } from '../model/semantics.js';
import { crKey, doneKey, isOpenKey, itemKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { card } from '../ui/card.js';
import { icon } from '../ui/icons.js';
import { files, itemCard, waitsMeta } from '../ui/item-card.js';
import { opener } from '../ui/open.js';
import { nextTag, stateIcon } from '../ui/parts.js';

// One bar per round of the CR's limit; the rounds taken are filled with the accent.
function bars(c, batch) {
  const total = roundLimit(c, batch) || Math.max(c.round, 1);
  const cells = Array.from(
    { length: total },
    (_, i) => html`<i class="${i < c.round ? 'on' : ''}"></i>`,
  );
  return html`<div class="bars">${cells}</div>`;
}

// The card of an item of the backlog, opened on a click: the shared card with the open mark.
export function backlogCard(state, { item, bucket }, labels) {
  const key = itemKey(item);
  const variants = [isOpenKey(state, key) && 'sel'];
  return itemCard(item, bucket, labels, { variants, attrs: opener(key) });
}

// The card of a merged CR: its id, title, batch and merge date; it opens its folder.
export function doneCard(state, m) {
  const key = doneKey(m);
  const day = (m.when ?? '').slice(0, 10) || '—';
  return card({
    variants: [isOpenKey(state, key) && 'sel'],
    attrs: opener(key),
    top: html`<span class="tag cr">${m.cr ?? ''}</span><span class="lbl">${m.batch ?? ''}</span>`,
    title: title(m.title),
    meta: html`<span>${t('card.merged', { day })}</span>`,
  });
}

// The card of a CR of the batch.
export function crCard(state, c) {
  const key = crKey(c);
  const batch = state.data.batch;
  const deps = c.after?.length
    ? html`<span>${icon('dep')} ${t('card.deps', { n: c.after.length })}</span>`
    : '';
  const phase = c.phase ? html`<span class="step" title="${t('step')}">${c.phase}</span>` : '';
  return card({
    variants: [isOpenKey(state, key) && 'sel'],
    attrs: opener(key),
    top: html`<span class="tag cr">${c.cr}</span>${nextTag(c)}<span class="lbl">${slug(c.folder)}</span><span class="place"></span>`,
    title: title(c.title),
    desc: c.description ?? '',
    body: bars(c, batch),
    meta: html`${phase}<span>${t('card.round', { r: roundText(c, batch) })}</span>${files(c.files)}${deps}${waitsMeta(c.open_waits)}`,
    end: html`<span title="${t(`state.${vstate(c)}`)}">${stateIcon(c)}</span>${usd(c.cost_usd)}`,
  });
}
