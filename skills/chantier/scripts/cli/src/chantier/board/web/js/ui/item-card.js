// The card of an item of the backlog, the same markup for the Kanban and for Triage: the bucket's
// priority tag, the slug, the title, the labels, the description, the files and the stage word.
// A view adds what is its own through `extra`: `classes` and `attrs` on the card, `lead` and
// `badges` in the top row, `foot` after the stage word. Pure: markup from an item.
import { html } from '../core/dom.js';
import { title } from '../core/format.js';
import { labelTags } from '../labels/tags.js';
import { stageWord } from '../model/grill.js';
import { t, tn } from '../model/words.js';
import { icon } from './icons.js';
import { tag } from './parts.js';

const count = (files) => (Array.isArray(files) ? files.length : (files ?? 0));

export const files = (n) => html`<span>${icon('file')} ${tn('card.files', count(n))}</span>`;

const nameOf = (bucket) => (bucket === 'inbox' ? t('priority.inbox') : bucket);

// `labels`: the project's labels, in order (a label's colour is its place in the list).
export function itemCard(item, bucket, labels, extra = {}) {
  const { classes = '', attrs = '', lead = '', badges = '', foot = '' } = extra;
  const tags = labelTags(item, labels);
  return html`<div class="card${classes}" ${attrs}><div class="row-tags">${lead}${tag(`pri-${bucket}`, nameOf(bucket))}<span class="lbl">${item.item}</span>${badges}</div><div class="ttl">${title(item.title)}</div><span class="place">${tags}</span><div class="desc">${item.description ?? ''}</div><div class="meta">${files(item.files)}<span class="r">${stageWord(item)}</span>${foot}</div></div>`;
}
