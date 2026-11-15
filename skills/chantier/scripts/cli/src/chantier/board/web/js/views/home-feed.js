// Home, the activity block: the last events of the batch, newest first.
import { html } from '../core/dom.js';
import { hhmm, usd } from '../core/format.js';
import { eventLine } from '../model/events.js';
import { closedBatches, dayOf, mergedOf, totalOf } from '../model/history.js';
import { t } from '../model/words.js';

const FEED_ROWS = 25;

const row = (e) => {
  const line = eventLine(e);
  return html`<li><span class="t">${hhmm(e.t)}</span><span class="ic ${line.tone}">${line.mark}</span><span>${line.body}</span></li>`;
};

// With no batch running: the last closed batch, else "none".
function idle(data) {
  const last = closedBatches(data)[0];
  if (!last) return t('home.none');
  return t('home.idle', {
    batch: last.batch,
    closed: dayOf(last.closed) || '—',
    a: mergedOf(last),
    b: totalOf(last),
    cost: usd(last.cost_usd),
  });
}

export function activityBlock(state) {
  const batch = state.data.batch;
  const events = [...(state.data.events ?? [])].reverse().slice(0, FEED_ROWS);
  const none = html`<li class="none">${batch ? t('home.none') : idle(state.data)}</li>`;
  const body = events.length ? events.map(row) : none;
  return html`<section class="block wide"><h2>${t('home.activity')} <span class="sub">${batch?.id ?? ''}</span></h2><ul class="feed">${body}</ul></section>`;
}
