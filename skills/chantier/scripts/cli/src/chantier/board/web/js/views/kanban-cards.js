// The cards of the Kanban: one for an item of the backlog, one for a CR of the batch. Each has
// empty `place` elements that a later change fills (a source badge, labels), and opens its folder.
import { html, vars } from '../core/dom.js';
import { slug, title, usd } from '../core/format.js';
import { stageWord } from '../model/grill.js';
import { roundLimit, roundText, vstate } from '../model/semantics.js';
import { crKey, isOpenKey, itemKey } from '../model/targets.js';
import { t, tn } from '../model/words.js';
import { icon } from '../ui/icons.js';
import { opener } from '../ui/open.js';
import { stateColor, stateTag, tag } from '../ui/parts.js';

const count = (files) => (Array.isArray(files) ? files.length : (files ?? 0));

const files = (n) => html`<span>${icon('file')} ${tn('card.files', count(n))}</span>`;

// One bar per round of the CR's limit; the rounds taken are filled with the state's colour.
function bars(c, batch) {
  const total = roundLimit(c, batch) || Math.max(c.round, 1);
  const color = stateColor(c);
  const cells = Array.from({ length: total }, (_, i) => {
    const on = i < c.round;
    return html`<i class="${on ? 'on' : ''}" data-vars="${vars({ '--c': color })}"></i>`;
  });
  return html`<div class="bars">${cells}</div>`;
}

// The card of an item of the backlog; `bucket` is the folder it sits in.
export function itemCard(state, item, bucket) {
  const key = itemKey(item);
  const name = bucket === 'inbox' ? t('priority.inbox') : bucket;
  const sel = isOpenKey(state, key) ? ' sel' : '';
  return html`<div class="card${sel}" ${opener(key)}><div class="row-tags">${tag(`pri-${bucket}`, name)}<span class="lbl">${item.item}</span><span class="place"></span></div><div class="ttl">${title(item.title)}</div><span class="place"></span><div class="desc">${item.description ?? ''}</div><div class="meta">${files(item.files)}<span class="r">${stageWord(item)}</span></div></div>`;
}

// The card of a CR of the batch.
export function crCard(state, c) {
  const key = crKey(c);
  const batch = state.data.batch;
  const sel = isOpenKey(state, key) ? ' sel' : '';
  const deps = c.after?.length
    ? html`<span>${icon('dep')} ${t('card.deps', { n: c.after.length })}</span>`
    : '';
  return html`<div class="card st-${vstate(c)}${sel}" ${opener(key)}><div class="row-tags"><span class="tag cr">${c.cr}</span>${stateTag(c)}<span class="lbl">${slug(c.folder)}</span><span class="place"></span></div><div class="ttl">${title(c.title)}</div><div class="desc">${c.description ?? ''}</div>${bars(c, batch)}<div class="meta"><span>${t('card.round', { r: roundText(c, batch) })}</span>${files(c.files)}${deps}<span class="r">${usd(c.cost_usd)}</span></div></div>`;
}
