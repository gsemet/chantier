// The Configuration view's Timing tab: read-only, one card per host, each setting once with a
// value per column (a shipped default grey, a value set in chantier.yaml teal with a dot, a
// setting the column never reads "not used"). Its tabs and legend sit on one line.

import { html } from '../core/dom.js';
import { t } from '../model/words.js';
import { empty } from '../ui/parts.js';

export const TABS = ['models', 'timing'];
const SETTINGS = ['steering_wake', 'cache_ttl', 'ci_reruns'];
const HASH = { models: '', timing: '#timing' };

// The tab the address names: Models unless its fragment says Timing.
export const tabOf = (hash) => (hash === HASH.timing ? 'timing' : 'models');

// The address of a tab, keeping the page's own path and query.
export const tabAddress = (tab) => `${location.pathname}${location.search}${HASH[tab]}`;

export function tabs(current) {
  const buttons = TABS.map(
    (id) =>
      html`<button class="ttab${id === current ? ' on' : ''}" type="button" data-tab="${id}">${t(`config.tab_${id}`)}</button>`,
  );
  return html`<div class="ttabs">${buttons}<span class="tleg"><span><span class="tv">${t('config.leg_default')}</span></span><span><span class="tv set"><i></i>${t('config.leg_set')}</span></span></span></div>`;
}

// One cell: a pill, or "not used" with no pill.
function cell(c) {
  if (c.not_used) return html`<span class="tnu">${t('config.not_used')}</span>`;
  if (c.default) return html`<span class="tv">${c.text}</span>`;
  return html`<span class="tv set" title="${c.layer}: ${c.src}"><i></i>${c.text}</span>`;
}

function row(setting, host) {
  const cells = host.columns.map((col) => cell(setting.columns[col.id]));
  return html`<div class="trow"><div>${t(`config.timing_${setting.id}`)}<small>${t(`config.timing_${setting.id}.text`)}</small></div>${cells}</div>`;
}

function card(host) {
  const head = host.columns.map((col) => html`<span>${col.name}</span>`);
  const rows = SETTINGS.map((id) => row({ id, ...host.settings[id] }, host));
  return html`<section class="hcard"><h3>${host.name}</h3><div class="trow th"><span>${t('config.th_setting')}</span>${head}</div>${rows}</section>`;
}

export function timingTab(view) {
  if (!view.timing) return empty(t('config.timing_unreadable'));
  return html`<div class="tcards">${Object.values(view.timing).map(card)}</div>`;
}
