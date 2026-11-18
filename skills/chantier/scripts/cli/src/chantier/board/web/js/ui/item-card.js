// The card of an item of the backlog, the same markup for the Kanban and for Triage: the bucket's
// priority chip, the slug, the title, the labels, the description, the files and the stage word.
// A view adds what is its own through `extra`: `classes`, `variants` and `attrs` on the card,
// `picked` (the check mark), `badges` in the top row, `foot` after the stage word. Pure.
import { html } from '../core/dom.js';
import { title } from '../core/format.js';
import { labelTags } from '../labels/tags.js';
import { stageWord } from '../model/grill.js';
import { tn } from '../model/words.js';
import { card } from './card.js';
import { icon } from './icons.js';

const count = (files) => (Array.isArray(files) ? files.length : (files ?? 0));

export const files = (n) => html`<span>${icon('file')} ${tn('card.files', count(n))}</span>`;

// `labels`: the project's labels, in order (a label's colour is its place in the list).
export function itemCard(item, bucket, labels, extra = {}) {
  const { classes = '', variants = [], attrs = '', picked = false, badges = '', foot = '' } = extra;
  return card({
    classes,
    variants,
    attrs,
    priority: bucket,
    picked,
    top: html`<span class="lbl">${item.item}</span>${badges}`,
    title: title(item.title),
    labels: html`<span class="place">${labelTags(item, labels)}</span>`,
    desc: item.description ?? '',
    meta: files(item.files),
    end: stageWord(item),
    foot,
  });
}
