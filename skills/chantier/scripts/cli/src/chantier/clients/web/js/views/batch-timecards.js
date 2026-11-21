// The Batch time cards: one paper card per CR, as a punched time card. Each round is one stamped
// line (coder, inspector), then the verifier line, the PR and the cost; the card's own stamps say
// merged, ready or working, and a CR at its third round or more is stamped as reworked.
import { html } from '../core/dom.js';
import { hhmm, prNumber, shortDate, title, usd } from '../core/format.js';
import { vstate } from '../model/semantics.js';
import { crKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { card } from '../ui/card.js';
import { opener } from '../ui/open.js';

const REWORK_FROM = 3;
const READY = ['ready', 'draft', 'local'];

const stamp = (time, word) =>
  html`<span class="tc-stamp">${time} ▣ ${t(`timecard.${word}`)}</span>`;

// The stamped lines: a time carries its date when the day is not the previous stamp's.
function lines(times) {
  let last = null;
  const at = (iso) => {
    const dated = last && new Date(last).toDateString() !== new Date(iso).toDateString();
    last = iso;
    return dated ? `${shortDate(iso)} ${hhmm(iso)}` : hhmm(iso);
  };
  const rounds = times.rounds.map((r) => {
    const insp = r.inspector_at
      ? stamp(at(r.inspector_at), 'insp')
      : html`<span class="tc-stamp">…</span>`;
    return html`<div class="tc-line"><b class="tc-r">R${r.n}</b>${stamp(at(r.coder_at), 'coder')}${insp}</div>`;
  });
  if (!times.verifier_at && !times.verdict_at) return rounds;
  const word = String(times.verdict).toUpperCase() === 'VERIFIED' ? 'verified' : 'unverified';
  const verdict = times.verdict_at ? html`<b class="tc-verdict">${t(`timecard.${word}`)}</b>` : '';
  const when = at(times.verifier_at ?? times.verdict_at);
  return [...rounds, html`<div class="tc-line">${stamp(when, 'verifier')}${verdict}</div>`];
}

// The card's stamps: its state's (merged, ready or working; the others have only their badge) and
// the rework one at its own place.
function stamps(c) {
  const state = vstate(c);
  const kind = state === 'merged' ? 'merged' : READY.includes(state) ? 'ready' : state;
  const out = ['merged', 'ready', 'working'].includes(kind)
    ? [{ kind, text: t(`timecard.${kind}`) }]
    : [];
  if (c.round >= REWORK_FROM)
    out.push({ kind: 'rework', text: t('timecard.reworked', { n: c.round }) });
  return out;
}

const timecard = (c) =>
  card({
    variants: ['paper'],
    priority: c.stage,
    attrs: html`data-id="${c.cr}" ${opener(crKey(c), 'tc-')}`,
    top: html`<span class="tag cr">${c.cr}</span><span class="tc-no">${t('timecard.number', { n: /\d+/.exec(c.cr)?.[0] ?? c.cr })}</span><span class="tc-cap">${t('timecard.title')}</span>`,
    title: title(c.title),
    body: lines(c.times),
    meta: html`<span>${c.pr ? html`PR ${prNumber(c.pr)}` : t('timecard.no_pr')}</span>`,
    end: html`<span>${t('timecard.rounds', { n: c.round })}</span><span>${usd(c.cost_usd)}</span>`,
    stamps: stamps(c),
  });

export function render(state) {
  return html`<div class="tcards">${state.data.batch.crs.map(timecard)}</div>`;
}
