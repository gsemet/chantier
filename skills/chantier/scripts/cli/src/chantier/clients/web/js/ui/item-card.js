// The card of an item of the backlog, drawn by Triage: the bucket's
// priority chip, the slug, the title, the labels, the description, the files and the stage word.
// A view adds what is its own through `extra`: `classes`, `variants` and `attrs` on the card,
// `picked` (the check mark), `badges` in the top row, `foot` after the stage word, `note` in the meta line. Pure.
import { html } from '../core/dom.js';
import { title } from '../core/format.js';
import { labelTags } from '../labels/tags.js';
import { stageWord } from '../model/grill.js';
import { t, tn } from '../model/words.js';
import { card } from './card.js';
import { icon } from './icons.js';

const count = (files) => (Array.isArray(files) ? files.length : (files ?? 0));

export const files = (n) => html`<span>${icon('file')} ${tn('card.files', count(n))}</span>`;

// The open waits of a CR or of a backlog item (`open_waits`), their types, one line; empty with none.
export const waitsMeta = (list) =>
  list?.length
    ? html`<span>${t('card.waits', { types: list.map((w) => t(`wait.${w.type}`)).join(', ') })}</span>`
    : '';

// `labels`: the project's labels, in order (a label's colour is its place in the list).
export function itemCard(item, bucket, labels, extra = {}) {
  const {
    classes = '',
    variants = [],
    attrs = '',
    picked = false,
    badges = '',
    foot = '',
    note = '',
  } = extra;
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
    meta: html`${files(item.files)}${waitsMeta(item.open_waits)}${note}`,
    end: stageWord(item),
    foot,
  });
}
