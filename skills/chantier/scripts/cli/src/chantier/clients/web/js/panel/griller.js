// The board's Griller in the file panel: the Grill button of an inbox, backlog or ready item, and
// the discussion that takes the file view's place (the tree stays). It watches the `griller` topic
// of the open item, sends the typed text, stops and ends the conversation. The discussion's box is
// built once and kept between redraws of the panel (as the editor's is), with what was typed.
import {
  clientId,
  endConversation,
  getGriller,
  sendMessage,
  stopTurn,
  watchGriller,
} from '../api/griller.js';
import { $, delegate, html, setHtml } from '../core/dom.js';
import { paint } from '../core/paint.js';
import { snapshot, update } from '../core/store.js';
import { confirmLeave } from '../edit/markdown-editor.js';
import { BUCKETS } from '../model/grill.js';
import { t } from '../model/words.js';
import { confirmDialog } from '../ui/dialog.js';
import { toast } from '../ui/toast.js';
import { discussion } from './griller-view.js';

let stopFeed = null; // stops the topic's feed
let watched = null; // the key of the item the feed is for
let box = null; // the discussion's element, kept between redraws
let focusText = false;
let sending = false;
let drawn = 0; // the number of turns last drawn: a new one scrolls to the end

// An item of the inbox, a priority or `3-ready`: never a CR of the batch or a merged one.
export const grillable = (target) => target?.kind === 'item' && BUCKETS.includes(target.bucket);

export const isOn = (state) => Boolean(state.panel && state.grillOn === state.panel.key);

const valueFor = (state) => (state.griller?.key === state.panel?.key ? state.griller : null);

// Whether the panel draws the Grill button. Off as shipped: the discussion cannot be opened from the
// panel while it is off, and the server's Griller stays as it is. Turning it on takes an edit here
// and a release (no configuration key).
export const GRILL_BUTTON = false;

// The head's Grill button; disabled, with the reason in its title, when the server says it cannot.
export function grillAction(state, target) {
  if (!GRILL_BUTTON || !grillable(target)) return '';
  const g = valueFor(state);
  const title = g && !g.available ? g.reason : t('griller.button_title');
  const pressed = isOn(state) ? 'true' : 'false';
  const disabled = !g?.available && !isOn(state) ? html` disabled` : '';
  return html`<button type="button" class="${isOn(state) ? 'btn small pri' : 'btn small'}" data-grill data-key="grill" aria-pressed="${pressed}" title="${title}"${disabled}>${t('griller.button')}</button>`;
}

// The empty place of the discussion in the panel's document region.
export const grillerPlace = () => html`<div class="griller" data-griller></div>`;

const same = (turn, target) => turn?.project === target.project && turn?.item === target.row.item;

function build() {
  box = document.createElement('div');
  box.className = 'gbox';
  setHtml(
    box,
    html`<div class="glog"></div><div class="gform"><textarea class="gtext" rows="3" maxlength="8000" spellcheck="false" aria-label="${t('griller.area')}"></textarea><div class="gbar"><button type="button" class="btn pri" data-g="send">${t('griller.send')}</button><button type="button" class="btn" data-g="stop">${t('griller.stop')}</button><button type="button" class="btn" data-g="end">${t('griller.end')}</button><span class="gmsg" role="status"></span></div></div>`,
  );
}

// What the box shows for the state: the discussion, and which buttons may be used.
function fill(root, state) {
  const g = valueFor(state);
  const here = Boolean(g?.running && same(g.running, state.panel));
  const elsewhere = Boolean(g?.running) && !here;
  const blocked = !g?.available;
  $('.gtext', box).disabled = blocked || here;
  $('[data-g="send"]', box).disabled = blocked || Boolean(g.running) || sending;
  $('[data-g="stop"]', box).hidden = !here;
  $('[data-g="end"]', box).hidden = here;
  $('[data-g="end"]', box).disabled = !g?.conversation;
  $('.gmsg', box).textContent = elsewhere
    ? t('griller.busy', { project: g.running.project, slug: g.running.item })
    : '';
  const turns = g?.conversation?.turns ?? [];
  const changed = paint($('.glog', box), discussion(g, clientId()));
  if (changed && turns.length >= drawn) $('.doc', root)?.scrollTo({ top: 1e9 });
  drawn = turns.length;
}

// A feed the server refused: the one line, shown as an unavailable Griller.
const refused = (key, error) => ({
  key,
  available: false,
  reason: t('griller.lost', { error }),
});

function follow(target) {
  const key = target?.key ?? null;
  if (key === watched) return;
  stopFeed?.();
  stopFeed = null;
  watched = key;
  box = null;
  drawn = 0;
  if (!key) return;
  const keep = (data) => watched === key && update({ griller: { ...data, key } });
  const lost = (error) => watched === key && update({ griller: refused(key, error) });
  stopFeed = watchGriller(target.project, target.row.item, keep, lost);
}

// Called after every draw of the panel: follow the open item, and put the box in its place.
export function syncGriller(root, state) {
  follow(grillable(state.panel) ? state.panel : null);
  const place = $('[data-griller]', root);
  if (!isOn(state) || !place) {
    box = null;
    return;
  }
  if (!box) build();
  fill(root, state);
  if (box.parentNode === place) return;
  place.append(box);
  if (focusText) $('.gtext', box).focus({ preventScroll: true });
  focusText = false;
}

async function toggle() {
  if (!(await confirmLeave())) return;
  const state = snapshot();
  focusText = !isOn(state);
  update({ grillOn: isOn(state) ? null : state.panel.key });
}

// Read the value again now (the topic's push may be up to 2 s away).
async function refresh(target) {
  try {
    const data = await getGriller(target.project, target.row.item);
    if (snapshot().panel?.key === target.key) update({ griller: { ...data, key: target.key } });
  } catch {
    // the topic's next push says it
  }
}

async function run(target, action) {
  try {
    await action();
  } catch (error) {
    toast(error.message, { error: true });
  }
  await refresh(target);
}

async function send(target) {
  const field = $('.gtext', box);
  const text = field.value;
  if (!text.trim() || sending) return;
  sending = true;
  await run(target, async () => {
    await sendMessage(target.project, target.row.item, text);
    field.value = '';
  });
  sending = false;
  update({});
}

async function end(target) {
  const ok = await confirmDialog({
    title: t('griller.end_title'),
    note: t('griller.end_note'),
    confirm: t('griller.end_confirm'),
  });
  if (ok) await run(target, () => endConversation(target.project, target.row.item));
}

export function bindGriller(root) {
  const offs = [
    delegate(root, 'click', '[data-grill]', toggle),
    delegate(root, 'click', '[data-g]', (_, button) => {
      const target = snapshot().panel;
      const what = button.dataset.g;
      if (what === 'send') send(target);
      if (what === 'stop') run(target, () => stopTurn(target.project, target.row.item));
      if (what === 'end') end(target);
    }),
    delegate(root, 'keydown', '.gtext', (event) => {
      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        send(snapshot().panel);
      }
    }),
  ];
  return () => {
    for (const unbind of offs) unbind();
  };
}
