// Home, the batch block: its state and mode, the bar of its CRs by state, the four small figures.
import { html } from '../core/dom.js';
import { age, usd } from '../core/format.js';
import { counts, heartbeat, steeringWord } from '../model/semantics.js';
import { t } from '../model/words.js';
import { dot, meter, stateColor, tag } from '../ui/parts.js';

const PARTS = [
  ['merged', 'home.merged'],
  ['ready', 'home.handed'],
  ['draft', 'home.draft'],
  ['local', 'home.local'],
  ['working', 'home.working'],
  ['blocked', 'home.blocked'],
  ['queued', 'home.queued'],
];

const colorOf = (state) => (state === 'queued' ? 'var(--queued-bar)' : stateColor(state));

function bar(batch) {
  const c = counts(batch);
  const parts = PARTS.map(([state]) => ({ n: c[state], color: colorOf(state) }));
  const legend = PARTS.map(
    ([state, word]) => html`<span>${dot(colorOf(state))}${t(word, { n: c[state] })}</span>`,
  );
  return html`${meter(parts, c.total)}<div class="legend">${legend}</div>`;
}

function sign(batch, now) {
  const beat = heartbeat(batch, now);
  if (beat.stopped) return { text: t('home.stopped'), late: true };
  if (beat.minutes == null) return { text: '—', late: false };
  return { text: t('time.ago', { age: t('time.min', { n: beat.minutes }) }), late: beat.late };
}

function figures(batch, now) {
  const beat = sign(batch, now);
  const who = batch.steering === 'direct' ? 'home.sign_cos' : 'home.sign_foreman';
  const spent = meter([{ n: batch.spent_usd ?? 0, color: 'var(--blue)' }], batch.budget_usd);
  const opened = batch.created ? t('time.ago', { age: age(batch.created, now) }) : '—';
  return html`<div class="mini"><div><small>${t('home.spent')}</small><b>${usd(batch.spent_usd)}</b> <span class="mut">/ ${usd(batch.budget_usd)}</span>${spent}</div><div><small>${t('home.slots')}</small><b>${batch.slots?.taken ?? 0}/${batch.slots?.total ?? 0}</b></div><div><small>${t(who)}</small><b class="${beat.late ? 'late' : ''}">${beat.text}</b></div><div><small>${t('home.opened')}</small><b>${opened}</b></div></div>`;
}

export function batchBlock(state) {
  const batch = state.data.batch;
  if (!batch) {
    return html`<section class="block wide"><h2>${t('batch.batch')}</h2><div class="empty">${t('home.no_batch')}</div></section>`;
  }
  const running = batch.state === 'running';
  const head = html`<h2>${batch.id} ${tag(running ? 'working' : 'queued', batch.state)}<span class="sub">${t(`mode.${batch.mode}`)} · ${steeringWord(batch)}</span><button class="more" type="button" data-go="batch">${t('home.see_batch')}</button></h2>`;
  return html`<section class="block wide">${head}${bar(batch)}${figures(batch, state.now)}</section>`;
}
