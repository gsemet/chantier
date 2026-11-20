// One Triage card: the Kanban's item card (ui/item-card.js) with Triage's extras added to it: a check
// mark when picked, the late-summary clock and the "modified" mark in the top row, the origin badge and the "open"
// button in the band, the mark "pending", and the attributes the drag and the selection need.
// Pure: it returns markup from an item and a context; `bind` code lives in selection.js and drag.js.
import { html } from '../core/dom.js';
import { stageOf } from '../model/grill.js';
import { itemKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { icon } from '../ui/icons.js';
import { itemCard } from '../ui/item-card.js';

const MARKS = { spec: '✓', auto: '⚡' };

// The grill mark of the legend and of a column's counts.
export const mark = (stage) =>
  html`<span class="gs ${stage}" aria-hidden="true">${MARKS[stage] ?? ''}</span>`;

const late = (item) =>
  item.late
    ? html`<span class="late" title="${t('postit.late')}" role="img" aria-label="${t('postit.late')}">${icon('clock')}</span>`
    : '';

const origin = (item) =>
  item.origin
    ? html`<span class="tag badge origin" title="${t('postit.origin')}">${item.origin.ref ?? item.origin.kind}</span>`
    : '';

// The mark of a card the journal says changed: inside the top row, at its right.
const modified = (yes) => (yes ? html`<span class="chgm">${t('postit.modified')}</span>` : '');

const openButton = (item, slug) =>
  html`<button type="button" class="open" data-open="${itemKey(item)}" data-key="tri-open-${slug}" title="${t('postit.open')}" aria-label="${t('postit.open')}">${icon('expand')}</button>`;

// `ctx`: { column, selected, pending, modified, labels } (the column the card sits in, sets and
// lists of slugs).
export function postit(item, ctx) {
  const slug = item.item;
  const sel = ctx.selected.includes(slug);
  const busy = ctx.pending.includes(slug);
  const classes = `pi${ctx.modified.has(slug) ? ' chg' : ''}`;
  const variants = ['pick-up', sel && 'picked', busy && 'pending'];
  const label = `${slug}, ${item.title ?? ''}${sel ? `, ${t('postit.selected')}` : ''}`;
  const attrs = html`draggable="${!busy}" tabindex="0" role="group" aria-label="${label}" aria-busy="${busy}" data-slug="${slug}" data-key="pi-${slug}" title="${t(`postit.${stageOf(item)}`)}"`;
  return itemCard(item, ctx.column, ctx.labels, {
    classes,
    variants,
    attrs,
    picked: sel,
    badges: html`${late(item)}${modified(ctx.modified.has(slug))}`,
    foot: html`${origin(item)}${openButton(item, slug)}`,
  });
}
