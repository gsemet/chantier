// Home, the batch block: its state and mode, the bar of its CRs by state, the four small figures.
import { html } from '../core/dom.js';
import { age, usd } from '../core/format.js';
import { counts, heartbeat, noCrYet, steeringFactoryWord } from '../model/semantics.js';
import { t } from '../model/words.js';
import { dot, meter, stateIcon, tag } from '../ui/parts.js';

const PARTS = [
  ['merged', 'home.merged'],
  ['ready', 'home.handed'],
  ['draft', 'home.draft'],
  ['local', 'home.local'],
  ['working', 'home.working'],
  ['blocked', 'home.blocked'],
  ['queued', 'home.queued'],
];

// The batch meter reads in the accent's shades; a blocked CR keeps its state's red.
const SHADES = {
  merged: 'var(--accent-dark)',
  ready: 'var(--accent)',
  draft: 'var(--accent-mid)',
  local: 'var(--accent-light)',
  working: 'var(--ink3)',
  blocked: 'var(--state-blocked)',
  queued: 'var(--queued-bar)',
};
const colorOf = (state) => SHADES[state];

function bar(batch) {
  const c = counts(batch);
  const parts = PARTS.map(([state]) => ({ n: c[state], color: colorOf(state) }));
  const legend = PARTS.map(
    ([state, word]) => html`<span>${dot(colorOf(state))}${t(word, { n: c[state] })}</span>`,
  );
  return html`${meter(parts, c.total)}<div class="legend">${legend}</div>`;
}

function sign(batch, now) {
  if (noCrYet(batch)) return { text: '—', late: false }; // nothing is due while no CR is held
  const beat = heartbeat(batch, now);
  if (beat.stopped) return { text: t('home.stopped'), late: true };
  if (beat.minutes == null) return { text: '—', late: false };
  return { text: t('time.ago', { age: t('time.min', { n: beat.minutes }) }), late: beat.late };
}

function figures(batch, now) {
  const beat = sign(batch, now);
  const who = batch.steering === 'direct' ? 'home.sign_cos' : 'home.sign_foreman';
  const none = noCrYet(batch) && batch.spent_usd == null; // no spend to show, so no meter
  const spent = none
    ? ''
    : meter([{ n: batch.spent_usd ?? 0, color: 'var(--accent)' }], batch.budget_usd);
  const figure = none ? t('batch.spent_none_yet') : usd(batch.spent_usd);
  const opened = batch.created ? t('time.ago', { age: age(batch.created, now) }) : '—';
  return html`<div class="mini"><div><small>${t('home.spent')}</small><b>${figure}</b> <span class="mut">/ ${usd(batch.budget_usd)}</span>${spent}</div><div><small>${t('home.slots')}</small><b>${batch.slots?.taken ?? 0}/${batch.slots?.total ?? 0}</b></div><div><small>${t(who)}</small><b class="${beat.late ? 'late' : ''}">${beat.text}</b></div><div><small>${t('home.opened')}</small><b>${opened}</b></div></div>`;
}

export function batchBlock(state) {
  const batch = state.data.batch;
  if (!batch) {
    return html`<section class="block wide"><h2>${t('batch.batch')}</h2><div class="empty">${t('home.no_batch')}</div></section>`;
  }
  const running = batch.state === 'running';
  const head = html`<h2>${batch.id} ${tag('st', html`${stateIcon(running ? 'working' : 'queued')}${batch.state}`)}<span class="sub">${t(`mode.${batch.mode}`)} · ${steeringFactoryWord(batch)}</span><button class="more" type="button" data-go="batch">${t('home.see_batch')}</button></h2>`;
  const body = noCrYet(batch)
    ? html`<p class="note">${t(batch.factory ? 'batch.no_cr_yet_factory' : 'batch.no_cr_yet')}</p>`
    : bar(batch);
  return html`<section class="block wide">${head}${body}${figures(batch, state.now)}</section>`;
}
