// Home, the activity block: the last events of the batch, newest first.
import { html } from '../core/dom.js';
import { hhmm } from '../core/format.js';
import { eventLine } from '../model/events.js';
import { t } from '../model/words.js';

const FEED_ROWS = 25;

const row = (e) => {
  const line = eventLine(e);
  return html`<li><span class="t">${hhmm(e.t)}</span><span class="ic ${line.tone}">${line.mark}</span><span>${line.body}</span></li>`;
};

export function activityBlock(state) {
  const batch = state.data.batch;
  const events = [...(state.data.events ?? [])].reverse().slice(0, FEED_ROWS);
  const body = events.length ? events.map(row) : html`<li class="none">${t('home.none')}</li>`;
  return html`<section class="block wide"><h2>${t('home.activity')} <span class="sub">${batch?.id ?? ''}</span></h2><ul class="feed">${body}</ul></section>`;
}
