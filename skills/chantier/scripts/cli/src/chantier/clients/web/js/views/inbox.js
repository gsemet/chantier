// The Inbox view: what needs the user, one card per entry of the `board` topic's `needs_you`, with
// Open, Snooze, Later and Discard. Open leads to the forge or the folder; the three others are kept
// in this browser (`inbox/marks.js`), and the board writes nothing. On a project and on All projects.
//   render(state) returns the view's markup; mount(root) returns a cleanup; after(root) marks seen.

import { delegate, html } from '../core/dom.js';
import { snapshot, update } from '../core/store.js';
import { entryCard } from '../inbox/entry.js';
import {
  firstSights,
  hide,
  isSeen,
  markShown,
  notifyOn,
  restore,
  setNotify,
} from '../inbox/marks.js';
import { blocked } from '../inbox/watch.js';
import { EVERY, entriesOf, KINDS, split } from '../model/inbox.js';
import { t, tf } from '../model/words.js';
import { bindOpen } from '../ui/open.js';
import { empty, stateIcon } from '../ui/parts.js';
import { projectsOf, sharedForge } from '../ui/picker.js';

const STATE = { question: 'waits', approval: 'working', merge: 'ready', blocked: 'blocked' };

let drawn = []; // the ids of the last draw's list
const fresh = new Set(); // the ids that were new when drawn, kept while the page stays mounted
let folded = false; // the hidden list is unfolded: a redraw keeps it so

const toggle = (kind, on) =>
  html`<button type="button" class="tag st ${STATE[kind]}${on ? '' : ' off'}" aria-pressed="${on}" data-ik="${kind}" data-key="ik-${kind}">${stateIcon(STATE[kind])}${t(`inbox.kind.${kind}`)}</button>`;

const filter = (state) =>
  html`<div class="lfil" role="group" aria-label="${t('inbox.filter')}"><span class="lt">${t('inbox.filter')}</span>${KINDS.map((k) => toggle(k, state.inboxKinds.includes(k)))}</div>`;

// The notification button, only where the browser offers notifications and the address is secure.
function notifyControl(state) {
  if (!('Notification' in window && window.isSecureContext)) return '';
  if (state.inboxNotifyBlocked || Notification.permission === 'denied') {
    return html`<p class="inbox-note">${t('inbox.notify_denied')}</p>`;
  }
  const on = notifyOn() && Notification.permission === 'granted';
  const word = t(on ? 'inbox.notify_off_button' : 'inbox.notify_on');
  return html`<div class="inbox-notify"><button type="button" class="btn small" data-inbox-notify data-key="inbox-notify">${word}</button></div>`;
}

export function render(state) {
  const scope = state.project;
  const entries = entriesOf(state.board, scope, firstSights());
  const { shown, hidden } = split(entries, state.inboxMarks, Date.now());
  const list = shown.filter((e) => state.inboxKinds.includes(e.kind));
  drawn = list.map((e) => e.id);
  for (const e of list) if (!isSeen(e.id)) fresh.add(e.id);
  const card = (e, marked = null) => entryCard(e, { state, scope, isNew: fresh.has(e.id), marked });
  const forge = scope === EVERY ? sharedForge(projectsOf(state)) : state.data?.forge;
  const lead = html`<p class="inbox-lead"><b>${t('inbox.lead')}</b><span class="inbox-sub">${tf(forge, 'inbox.sub')}</span></p>`;
  const body = list.length ? list.map((e) => card(e)) : empty(t('inbox.none'));
  const open = folded ? html` open` : '';
  const away = hidden.length
    ? html`<details class="inbox-hidden"${open}><summary>${t('inbox.hidden', { n: hidden.length })}</summary>${hidden.map((e) => card(e, state.inboxMarks[e.id]))}</details>`
    : '';
  return html`<div class="inbox">${lead}${notifyControl(state)}${filter(state)}<div class="inbox-list">${body}</div>${away}</div>`;
}

function toggleKind(kind) {
  const on = snapshot().inboxKinds;
  update({ inboxKinds: KINDS.filter((k) => (k === kind ? !on.includes(k) : on.includes(k))) });
}

// A click asks the browser's leave; a throw or a rejection reads as denied.
async function toggleNotify() {
  if (notifyOn()) {
    setNotify(false);
    update({ inboxTick: Date.now() });
    return;
  }
  try {
    const answer = await Notification.requestPermission();
    if (answer === 'denied') blocked();
    if (answer !== 'granted') return;
    setNotify(true);
    update({ inboxTick: Date.now() });
  } catch {
    blocked();
  }
}

export function mount(root) {
  const stops = [
    bindOpen(root),
    delegate(root, 'click', '[data-inbox]', (_, el) => {
      const { inbox, inboxId } = el.dataset;
      if (inbox === 'restore') restore(inboxId);
      else hide(inboxId, inbox);
    }),
    delegate(root, 'click', '[data-ik]', (_, el) => toggleKind(el.dataset.ik)),
    delegate(root, 'click', '[data-inbox-notify]', toggleNotify),
  ];
  const remember = (event) => {
    if (event.target.matches('.inbox-hidden')) folded = event.target.open;
  };
  root.addEventListener('toggle', remember, true); // `toggle` does not bubble
  return () => {
    for (const stop of stops) stop();
    root.removeEventListener('toggle', remember, true);
    fresh.clear();
    folded = false;
  };
}

// The list the page drew is now seen; this writes the browser's storage and redraws nothing.
export const after = () => markShown(drawn);
