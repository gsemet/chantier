// The surface's autosync, drawn: a pill at the foot of the sidebar, a dot beside the project picker
// on the phone, and the panel both open. Pure functions of the store's state; the events are in
// autosync-events.js. With no autosync (`present: false`) nothing is drawn.
import { html } from '../core/dom.js';
import { age, hhmm } from '../core/format.js';
import { t } from '../model/words.js';
import { icon } from './icons.js';

export const groupOf = (state) => {
  const group = state.board?.autosync;
  return group?.present ? group : null;
};

export const label = (group) => t(`autosync.state.${group.state}`);

// The line under the pill's title: the age of the last push, or what the state asks.
export function subtitle(group, now) {
  if (group.state === 'active') {
    const ago = age(group.last_push, now);
    return ago ? t('autosync.sub.active', { age: ago }) : t('autosync.sub.idle');
  }
  return t(`autosync.sub.${group.state}`, { n: 1 });
}

// The buttons the panel offers: none while blocked (the Chief of Staff restarts it).
export function actions(group) {
  if (group.state === 'stopped') return ['start'];
  return group.state === 'blocked' ? [] : ['stop'];
}

const title = (group) => t('autosync.title', { state: label(group) });

const dotOf = (group) => html`<span class="adot ${group.state}"></span>`;

const box = (kind, content) => html`<div class="aw ${kind}">${content}</div>`;

const incident = (group, busy) =>
  group.state === 'approval' && group.incident
    ? box(
        'wa',
        html`${t('autosync.incident', { id: group.incident.id, message: group.incident.message })}<button class="abtn pri" type="button" data-autosync-approve="${group.incident.id}"${busy ? html` disabled` : ''}>${t('autosync.approve')}</button>`,
      )
    : '';

// The server names a member by a neutral word; the board's own server is translated here.
const who = (name) => (name === 'board' ? t('autosync.who.board') : name);

const members = (group) =>
  group.participants.length
    ? group.participants.map((m) => who(m.name)).join(', ')
    : t('autosync.none');

const details = (group) => {
  const stopped = group.state === 'stopped';
  const leader = stopped || !group.leader ? '—' : who(group.leader);
  const last = group.last_push ? hhmm(group.last_push) : '—';
  return html`<dl><dt>${t('autosync.leader')}</dt><dd>${leader}</dd><dt>${t('autosync.members')}</dt><dd>${members(group)}</dd><dt>${t('autosync.last_push')}</dt><dd>${last}</dd></dl>`;
};

const button = (act, busy) =>
  html`<button class="abtn${act === 'start' ? ' pri' : ''}" type="button" data-autosync-act="${act}"${busy ? html` disabled` : ''}>${t(`autosync.${act}`)}</button>`;

// The panel: the state, why it is blocked, the group, the incident to approve, the actions.
export function panel(group, ui) {
  const blocked =
    group.state === 'blocked' ? box('ko', t('autosync.box.blocked', { reason: group.reason })) : '';
  const failed = ui.error ? html`<div class="aw ko" role="alert">${ui.error}</div>` : '';
  return html`<div class="apop" role="dialog" aria-label="${title(group)}"><div class="ah">${dotOf(group)}<b>${title(group)}</b></div>${blocked}${details(group)}${incident(group, ui.busy)}<div class="aa">${actions(group).map((a) => button(a, ui.busy))}</div>${failed}</div>`;
}

const open = (state) => state.autosync.open;

// The pill at the sidebar's foot, with the panel above it when it is open.
export function pill(state) {
  const group = groupOf(state);
  if (!group) return '';
  return html`<button class="asy" type="button" data-autosync="toggle" data-key="autosync-pill" aria-haspopup="dialog" aria-expanded="${open(state)}">${dotOf(group)}<span><b>${title(group)}</b><small>${subtitle(group, state.now)}</small></span><span class="car">${icon('chev')}</span></button>${open(state) ? panel(group, state.autosync) : ''}`;
}

// The dot beside the project picker: only the colour, titled with the state.
export function dot(state) {
  const group = groupOf(state);
  if (!group) return '';
  return html`<button class="asyd" type="button" data-autosync="toggle" data-key="autosync-dot" aria-haspopup="dialog" aria-expanded="${open(state)}" title="${title(group)}" aria-label="${title(group)}">${dotOf(group)}</button>${open(state) ? panel(group, state.autosync) : ''}`;
}
