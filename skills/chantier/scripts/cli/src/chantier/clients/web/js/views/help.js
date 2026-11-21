// The Help view: the board's concepts and the agents' roles, as two groups of cards; a click (or
// Enter) opens a short detail under the group, kept in the address (`&h=<topic>`). It shows no
// project data and calls no server operation: every word is an i18n key (i18n/en-help.js).
//   render(state) returns the view's markup; mount(root) returns a cleanup; after(root, state)
//   moves the focus to the detail when a topic opens, back to its card when it closes.

import { delegate, html } from '../core/dom.js';
import { closeTopic, go } from '../core/router.js';
import { snapshot } from '../core/store.js';
import { t } from '../model/words.js';
import { card } from '../ui/card.js';
import { icon } from '../ui/icons.js';
import { TOPICS } from './help-topics.js';

// The body: paragraphs split by a blank line, a paragraph of `- ` lines is a list.
function blocks(text) {
  return text.split('\n\n').map((block) => {
    const lines = block.split('\n');
    if (!lines.every((l) => l.startsWith('- '))) return html`<p>${block}</p>`;
    return html`<ul>${lines.map((l) => html`<li>${l.slice(2)}</li>`)}</ul>`;
  });
}

function topicCard(topic, open) {
  const id = topic.id;
  const attrs = html`data-help="${id}" data-key="help-${id}" tabindex="0" role="button" aria-expanded="${open ? 'true' : 'false'}" aria-controls="help-detail"`;
  return card({
    classes: 'help-card',
    heading: 'h3',
    title: t(`help.${id}.name`),
    desc: t(`help.${id}.line`),
    variants: [open && 'sel'],
    attrs,
  });
}

function detail(topic) {
  const id = topic.id;
  const attrs = html`id="help-detail" tabindex="-1"`;
  const more = topic.doc
    ? html`<a href="${topic.doc}" target="_blank" rel="noopener" data-key="help-more">${t('help.read_more')} ${icon('ext')}</a>`
    : '';
  const end = html`<button type="button" class="btn" data-help-close data-key="help-close">${t('help.close')}</button>`;
  return card({
    as: 'section',
    classes: 'help-detail',
    heading: 'h3',
    title: t(`help.${id}.name`),
    body: blocks(t(`help.${id}.body`)),
    meta: more,
    end,
    attrs,
  });
}

function group(name, open) {
  const topics = TOPICS.filter((x) => x.group === name);
  const shown = topics.find((x) => x.id === open);
  return html`<h2>${t(`help.${name}`)}</h2><div class="help-grid">${topics.map((x) => topicCard(x, x.id === open))}</div>${shown ? detail(shown) : ''}`;
}

export function render(state) {
  const open = state.helpTopic;
  return html`<div class="help"><p class="help-intro">${t('help.intro')}</p>${group('concepts', open)}${group('roles', open)}</div>`;
}

let last = null; // the topic open at the last call of `after`

// A card, or its Enter or Space: open it, switch to it, or (the open one) close it.
function choose(id) {
  const open = snapshot().helpTopic;
  if (open === id) closeTopic();
  else go({ topic: id }, { replace: Boolean(open) });
}

export function mount(root, state) {
  last = state.helpTopic;
  const stops = [
    delegate(root, 'click', '[data-help]', (_, el) => choose(el.dataset.help)),
    delegate(root, 'keydown', '[data-help]', (event, el) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      choose(el.dataset.help);
    }),
    delegate(root, 'click', '[data-help-close]', () => closeTopic()),
  ];
  return () => {
    for (const stop of stops) stop();
  };
}

export function after(root, state) {
  const now = state.helpTopic;
  if (now === last) return;
  const before = last;
  last = now;
  const target = now
    ? root.querySelector('#help-detail')
    : root.querySelector(`[data-key="help-${before}"]`);
  target?.focus({ preventScroll: false });
}
