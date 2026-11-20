// One line of the batch's story, from one event of the record: `{ mark, tone, body }`, the body
// being markup. Every value that comes from the record goes through `html`, so it is escaped.
import { html } from '../core/dom.js';
import { prNumber } from '../core/format.js';
import { t } from './words.js';

const who = (e) => (e.cr ? html`<b>${e.cr}</b> ` : '');
const pass = (e) => e.result === 'pass';
const line = (mark, tone, body) => ({ mark, tone, body });

const TEXT = {
  open: () => line('⊕', '', html`${t('ev.open')}`),
  add: (e) => line('+', '', html`${who(e)}${t('ev.add')}`),
  take: (e) => line('▶', '', html`${who(e)}${t('ev.take')}`),
  round: (e) =>
    line('↻', '', html`${who(e)}${e.round ? t('ev.round', { n: e.round }) : t('ev.round_next')}`),
  gate: (e) =>
    line(
      pass(e) ? '✓' : '✗',
      pass(e) ? 'ok' : 'ko',
      html`${who(e)}${t('ev.gate')} <code>${e.command ?? ''}</code> ${pass(e) ? t('ev.passed') : t('ev.failed')}`,
    ),
  verdict: (e) => {
    const ok = e.result === 'VERIFIED';
    return line(
      ok ? '✓' : '✗',
      ok ? 'ok' : 'ko',
      html`${who(e)}${ok ? t('ev.verified') : t('ev.unverified')}`,
    );
  },
  ship: (e) => line('⇪', 'pr', html`${who(e)}${t('ev.ship', { pr: prNumber(e.pr) })}`),
  handback: (e) =>
    line(
      '⇠',
      e.result === 'ready' ? 'ok' : 'ko',
      html`${who(e)}${t('ev.handback')} ${e.result ?? ''}`,
    ),
  ask: (e) => line('?', 'ko', html`${who(e)}${t('ev.ask')}`),
  order: (e) =>
    e.order_kind === 'merged'
      ? line('⛙', 'ok', html`${who(e)}${t('ev.merged')}`)
      : line(
          '⚑',
          '',
          html`${who(e)}${t('ev.order')} ${e.order_kind ?? ''}${e.note ? ` : ${e.note}` : ''}`,
        ),
  merged: (e) => line('⛙', 'ok', html`${who(e)}${t('ev.merged')}`),
  note: (e) => line('✎', '', html`${who(e)}${t('ev.note')}`),
};

TEXT.pause = TEXT.note;

// An event kind this page does not know shows as its own name.
export const eventLine = (e) =>
  (TEXT[e.kind] ?? ((x) => line('·', '', html`${who(x)}${x.kind}`)))(e);
