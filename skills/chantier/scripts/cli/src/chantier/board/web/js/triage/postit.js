// One post-it's markup: its grill-state mark, the slug, the late-summary clock and the origin badge,
// the title, its labels and a foot with the state's word, the file count and the "open" button.
// Pure: it returns markup from an item and a context; `bind` code lives in selection.js and drag.js.
import { html } from '../core/dom.js';
import { title } from '../core/format.js';
import { labelTags } from '../labels/tags.js';
import { stageOf, stageWord } from '../model/grill.js';
import { itemKey } from '../model/targets.js';
import { t, tn } from '../model/words.js';
import { icon } from '../ui/icons.js';

const MARKS = { spec: '✓', auto: '⚡' };

export const mark = (stage) =>
  html`<span class="gs ${stage}" aria-hidden="true">${MARKS[stage] ?? ''}</span>`;

const filesOf = (item) => (Array.isArray(item.files) ? item.files.length : (item.files ?? 0));

const late = (item) =>
  item.late
    ? html`<span class="late" title="${t('postit.late')}" role="img" aria-label="${t('postit.late')}">${icon('clock')}</span>`
    : '';

const origin = (item) =>
  item.origin
    ? html`<span class="tag badge origin" title="${t('postit.origin')}">${item.origin.ref ?? item.origin.kind}</span>`
    : '';

// `ctx`: { selected, pending, modified, labels } (sets and lists of slugs).
export function postit(item, ctx) {
  const stage = stageOf(item);
  const slug = item.item;
  const sel = ctx.selected.includes(slug);
  const busy = ctx.pending.includes(slug);
  const classes = `pi ${stage}${sel ? ' sel' : ''}${ctx.modified.has(slug) ? ' chg' : ''}${busy ? ' pend' : ''}`;
  const hint = t(`postit.${stage}`);
  const label = `${slug}, ${item.title ?? ''}${sel ? `, ${t('postit.selected')}` : ''}`;
  return html`<div class="${classes}" draggable="${!busy}" tabindex="0" role="group" aria-label="${label}" aria-busy="${busy}" data-slug="${slug}" data-key="pi-${slug}" title="${hint}"><div class="row">${mark(stage)}<span class="sl">${slug}</span>${late(item)}${origin(item)}</div><div class="pt">${title(item.title)}</div>${labelTags(item, ctx.labels)}<div class="pm"><span>${stageWord(item)}</span><span>${icon('file')} ${tn('card.files', filesOf(item))}</span><button type="button" class="open" data-open="${itemKey(item)}" data-key="tri-open-${slug}" title="${t('postit.open')}" aria-label="${t('postit.open')}">${icon('expand')}</button></div></div>`;
}
