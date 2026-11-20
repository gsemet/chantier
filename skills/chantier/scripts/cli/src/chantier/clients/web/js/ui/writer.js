// The surface's writer, drawn: a pill at the foot of the sidebar, a dot beside the project picker
// on the phone, and the panel both open. Pure functions of the store's state; the events are in
// writer-events.js. Drawn only on a planning surface (`board.surface`); the writer entry is read
// as it is, `{state: "off"}` with none.
import { html } from '../core/dom.js';
import { age, hhmm } from '../core/format.js';
import { t } from '../model/words.js';
import { icon } from './icons.js';

// The colour class of a state: two states share blue, three share red, `off` is grey as offline.
const TONES = {
  synced: 'synced',
  syncing: 'pending',
  pending: 'pending',
  offline: 'offline',
  off: 'offline',
  conflict: 'blocked',
  blocked: 'blocked',
  stopped: 'blocked',
};

export const groupOf = (state) => {
  const board = state.board;
  return board?.surface && board.writer ? board.writer : null;
};

const known = (group) => (group.state in TONES ? group.state : 'off');

export const label = (group) => t(`writer.state.${known(group)}`);

// The line under the pill's title: the age of the last push, or what the state asks.
export function subtitle(group, now) {
  const state = known(group);
  if (state === 'synced') {
    const ago = age(group.last_push?.at, now);
    return ago ? t('writer.sub.synced', { age: ago }) : t('writer.sub.idle');
  }
  return t(`writer.sub.${state}`, { n: group.pending ?? 0 });
}

const title = (group) => t('writer.title', { state: label(group) });

const dotOf = (group) => html`<span class="adot ${TONES[known(group)]}"></span>`;

const box = (content) => html`<div class="aw ko">${content}</div>`;

// Why it needs a hand, and the way out.
function trouble(group) {
  if (group.state === 'blocked') {
    return box(t('writer.box.blocked', { reason: group.reason ?? '', text: group.text ?? '' }));
  }
  if (group.state === 'conflict') {
    const files = (group.conflict?.files ?? []).join(', ');
    return box(t('writer.box.conflict', { files }));
  }
  if (group.state === 'stopped') return box(t('writer.box.stopped', { reason: group.text ?? '' }));
  return '';
}

const row = (name, value) => html`<dt>${t(name)}</dt><dd>${value}</dd>`;

const at = (stamp) => (stamp ? hhmm(stamp) : '—');

const details = (group) =>
  html`<dl>${row('writer.since', at(group.since))}${row('writer.last_push', at(group.last_push?.at))}${row('writer.pending', String(group.pending ?? 0))}${row('writer.ahead', String(group.ahead ?? 0))}</dl>`;

const syncButton = (busy) =>
  html`<button class="abtn pri" type="button" data-writer-sync${busy ? html` disabled` : ''}>${t('writer.sync')}</button>`;

// The panel: the state, why it needs a hand, the facts, the one button. With no writer, or a stopped
// one (it refuses a sync), the button is not offered.
export function panel(group, ui) {
  const failed = ui.error ? html`<div class="aw ko" role="alert">${ui.error}</div>` : '';
  const action =
    group.state === 'off' || group.state === 'stopped'
      ? ''
      : html`<div class="aa">${syncButton(ui.busy)}</div>`;
  const off = group.state === 'off' ? html`<div class="aw">${t('writer.box.off')}</div>` : '';
  return html`<div class="apop" role="dialog" aria-label="${title(group)}"><div class="ah">${dotOf(group)}<b>${title(group)}</b></div>${trouble(group)}${off}${group.state === 'off' ? '' : details(group)}${action}${failed}</div>`;
}

const open = (state) => state.writer.open;

// The pill at the sidebar's foot, with the panel above it when it is open.
export function pill(state) {
  const group = groupOf(state);
  if (!group) return '';
  return html`<button class="asy" type="button" data-writer="toggle" data-key="writer-pill" aria-haspopup="dialog" aria-expanded="${open(state)}">${dotOf(group)}<span><b>${title(group)}</b><small>${subtitle(group, state.now)}</small></span><span class="car">${icon('chev')}</span></button>${open(state) ? panel(group, state.writer) : ''}`;
}

// The dot beside the project picker: only the colour, titled with the state.
export function dot(state) {
  const group = groupOf(state);
  if (!group) return '';
  return html`<button class="asyd" type="button" data-writer="toggle" data-key="writer-dot" aria-haspopup="dialog" aria-expanded="${open(state)}" title="${title(group)}" aria-label="${title(group)}">${dotOf(group)}</button>${open(state) ? panel(group, state.writer) : ''}`;
}
