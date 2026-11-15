// The panel's head: the close button, the facts row, the title, the folder's path and its file
// count, and the empty place the editor will fill.
import { html } from '../core/dom.js';
import { title, usd } from '../core/format.js';
import { stageWord } from '../model/grill.js';
import { gateLink, gateWords, roundText } from '../model/semantics.js';
import { t, tn } from '../model/words.js';
import { icon } from '../ui/icons.js';
import { stateTag, tag } from '../ui/parts.js';

// The long gate's fact: its words, linking to the PR of the CR that validates a covered CR.
function gateFact(c) {
  const words = gateWords(c);
  if (!words) return '';
  const label = `${t('gate.label')}: ${words}`;
  const url = gateLink(c);
  if (!url) return html`<span class="lbl">${label}</span>`;
  return html`<a class="lbl" href="${url}" target="_blank" rel="noopener" title="${t('gate.open')}">${label}</a>`;
}

// The facts of a CR of the batch: its tag, state, round, cost, long gate and open dependencies.
const crFacts = (c, batch) =>
  html`${tag('cr', c.cr)}${stateTag(c)}<span class="lbl">${t('card.round', { r: roundText(c, batch) })}</span><span class="lbl">${usd(c.cost_usd)}</span>${gateFact(c)}${c.after?.length ? html`<span class="lbl">${t('panel.after', { n: c.after.length })}</span>` : ''}`;

// The facts of an item of the backlog: its priority, slug and grill state.
const itemFacts = (target) => {
  const name = target.bucket === 'inbox' ? t('priority.inbox') : target.bucket;
  return html`${tag(`pri-${target.bucket}`, name)}<span class="lbl">${target.row.item}</span><span class="lbl">${stageWord(target.row)}</span>`;
};

// The facts of a merged CR: its tag, its batch and its cost.
const doneFacts = (m) =>
  html`${tag('cr', m.cr)}<span class="lbl">${m.batch ?? ''}</span><span class="lbl">${usd(m.cost_usd)}</span>`;

const FACTS = {
  cr: (target, batch) => crFacts(target.row, batch),
  done: (target) => doneFacts(target.row),
  item: (target) => itemFacts(target),
};

export function head(target, batch, count) {
  const facts = FACTS[target.kind](target, batch);
  return html`<div class="ph"><div class="row-tags">${facts}<span class="grow"></span><span class="place" data-place="panel-actions"></span><button class="x" type="button" data-close aria-label="${t('panel.close')}">${icon('close')}</button></div><h2>${title(target.title)}</h2><div class="path">${target.folder}/ · ${tn('panel.files', count)}</div></div>`;
}
