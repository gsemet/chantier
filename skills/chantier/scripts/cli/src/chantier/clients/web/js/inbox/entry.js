// One entry of the Inbox as a card: its kind chip, its CR and title, the question or reason, its age
// and the four actions. Open is a link or a button that opens the folder; the others are the device's.
import { html } from '../core/dom.js';
import { age, hhmm, safeUrl, title } from '../core/format.js';
import { EVERY } from '../model/inbox.js';
import { crKey, itemKey } from '../model/targets.js';
import { tf } from '../model/words.js';
import { card } from '../ui/card.js';
import { opener } from '../ui/open.js';
import { mark, stateIcon, tag } from '../ui/parts.js';

const STATE = { question: 'waits', approval: 'working', merge: 'ready', blocked: 'blocked' };
const ACTIONS = ['snooze', 'later', 'discard'];

const button = (attrs, text) =>
  html`<button type="button" class="btn small" ${attrs}>${text}</button>`;

// Open: a PR or MR in a new tab when the entry has a web address, else its folder.
function open(e, scope) {
  const w = (key, params) => tf(e.forge, key, params);
  const url = e.kind === 'approval' || e.kind === 'merge' ? safeUrl(e.pr) : null;
  if (url) {
    return html`<a class="btn small" href="${url}" target="_blank" rel="noopener" title="${w('pr.open')}" data-key="inbox-open-${e.id}">${w('inbox.open')}</a>`;
  }
  if (scope === EVERY) {
    return button(html`data-project="${e.project}" data-key="inbox-go-${e.id}"`, w('inbox.open'));
  }
  const key = e.cr ? crKey({ cr: e.cr }) : itemKey({ item: e.item });
  return button(opener(key, 'inbox-'), w('inbox.open'));
}

// "while it lasts", "until 14:05", "until 08:00" or, for a Later that ends tomorrow, "until tomorrow 08:00".
function until(marked, w) {
  if (marked.how === 'discard') return w('inbox.while');
  const at = new Date(marked.until);
  const tomorrow = marked.how === 'later' && at.toDateString() !== new Date().toDateString();
  return tomorrow ? w('inbox.until_morning') : w('inbox.until', { time: hhmm(at.toISOString()) });
}

function meta(e, now, marked, w) {
  const out = [];
  if (e.since && now) out.push(html`<span>${w('time.ago', { age: age(e.since, now) })}</span>`);
  if (e.kind === 'question') {
    const session = e.session ? w('inbox.session', { title: e.session }) : w('inbox.no_session');
    out.push(html`<span>${session}</span>`);
  }
  if (e.kind === 'merge' && e.merge_place) {
    out.push(
      html`<span>${w('inbox.merge_place', { n: e.merge_place, total: e.merge_total })}</span>`,
    );
  }
  if (marked) out.push(html`<span>${until(marked, w)}</span>`);
  return out;
}

// `ctx`: the page's `state`, the scope (`*` or a project), `isNew`, and the entry's `marked` mark
// when it is in the hidden list.
export function entryCard(e, { state, scope, isNew, marked }) {
  const w = (key, params) => tf(e.forge, key, params);
  const kind = STATE[e.kind];
  const chip = tag(`st ${kind}`, html`${stateIcon(kind)}${w(`inbox.kind.${e.kind}`)}`);
  const from =
    scope === EVERY ? html`<span class="inbox-project">${mark(e.project)}${e.project}</span>` : '';
  const fresh = isNew ? tag('badge', w('inbox.new')) : '';
  const act = (how) => button(html`data-inbox="${how}" data-inbox-id="${e.id}"`, w(`inbox.${how}`));
  const buttons = marked
    ? [
        open(e, scope),
        button(html`data-inbox="restore" data-inbox-id="${e.id}"`, w('inbox.restore')),
      ]
    : [open(e, scope), ...ACTIONS.map(act)];
  const text = e.text ? html`<span class="inbox-text">${e.text}</span>` : '';
  return card({
    classes: 'inbox-entry',
    heading: 'div',
    top: html`${chip}${from}${fresh}`,
    title: `${e.cr ?? e.item} · ${title(e.title)}`,
    body: e.kind === 'merge' ? '' : text,
    meta: meta(e, state.now, marked, w),
    end: buttons,
    variants: [marked && 'compact', marked && 'dim'],
    attrs: html`data-key="inbox-${e.id}"`,
  });
}
