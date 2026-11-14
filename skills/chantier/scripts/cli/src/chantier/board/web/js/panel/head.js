// The panel's head: the close button, the facts row, the title, the folder's path and its file
// count, and the empty place the editor will fill.
import { html } from '../core/dom.js';
import { title, usd } from '../core/format.js';
import { stageWord } from '../model/grill.js';
import { roundText } from '../model/semantics.js';
import { t, tn } from '../model/words.js';
import { icon } from '../ui/icons.js';
import { stateTag, tag } from '../ui/parts.js';

// The facts of a CR of the batch: its tag, state, round, cost and open dependencies.
const crFacts = (c, batch) =>
  html`${tag('cr', c.cr)}${stateTag(c)}<span class="lbl">${t('card.round', { r: roundText(c, batch) })}</span><span class="lbl">${usd(c.cost_usd)}</span>${c.after?.length ? html`<span class="lbl">${t('panel.after', { n: c.after.length })}</span>` : ''}`;

// The facts of an item of the backlog: its priority, slug and grill state.
const itemFacts = (target) => {
  const name = target.bucket === 'inbox' ? t('priority.inbox') : target.bucket;
  return html`${tag(`pri-${target.bucket}`, name)}<span class="lbl">${target.row.item}</span><span class="lbl">${stageWord(target.row)}</span>`;
};

export function head(target, batch, count) {
  const facts = target.kind === 'cr' ? crFacts(target.row, batch) : itemFacts(target);
  return html`<div class="ph"><div class="row-tags">${facts}<span class="grow"></span><span class="place" data-place="panel-actions"></span><button class="x" type="button" data-close aria-label="${t('panel.close')}">${icon('close')}</button></div><h2>${title(target.title)}</h2><div class="path">${target.folder}/ · ${tn('panel.files', count)}</div></div>`;
}
