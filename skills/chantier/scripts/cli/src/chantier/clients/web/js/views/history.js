// The History view: what was done in a day, a week or a month of the project shown, from the
// closed records, the archived CRs' steps and the running batch. Read only: the page writes
// nothing. The period and the date are in the address (`hp=`, `hd=`); the server answers on the
// `history` topic in the browser's time zone (history-feed.js), and the answer is kept in
// `state.historyPage`. Top to bottom: the head (period, choices, previous, next, Today), five
// figures, the events grouped by local day, and the foot's quiet lines.
//   render(state) returns the view's markup; mount(root) returns a cleanup.

import { delegate, html } from '../core/dom.js';
import { hhmm, prNumber, safeUrl, title } from '../core/format.js';
import { go, HISTORY_PERIODS } from '../core/router.js';
import { snapshot, subscribe, update } from '../core/store.js';
import { money } from '../model/receipt.js';
import { crsOf } from '../model/semantics.js';
import { language, t, tn } from '../model/words.js';
import { bindOpen, opener } from '../ui/open.js';
import { empty, kpi, stateIcon, tag } from '../ui/parts.js';
import { askedKey, startFeed } from './history-feed.js';

// The state chip's variant of each kind of event: no new colour.
const VARIANT = { merged: 'merged', dropped: 'blocked', opened: 'draft', release: 'ready' };
const KINDS = ['merged', 'dropped', 'opened', 'releases'];
const COUNT_WORDS = {
  merged: 'history.n_merged',
  dropped: 'history.n_dropped',
  opened: 'history.n_opened',
  releases: 'history.n_releases',
};

// A date `YYYY-MM-DD` as a day with no zone: formatted in UTC so that no offset shifts it.
const at = (day) => new Date(`${day}T12:00:00Z`);
const format = (day, options) =>
  new Intl.DateTimeFormat(language(), { ...options, timeZone: 'UTC' }).format(at(day));

// The period's name in the board's language.
function name(answer) {
  if (answer.period === 'week') {
    return t('history.week_of', { date: format(answer.date, { dateStyle: 'long' }) });
  }
  if (answer.period === 'month') return format(answer.date, { month: 'long', year: 'numeric' });
  return format(answer.date, { dateStyle: 'full' });
}

const periodChip = (value, current) =>
  html`<button type="button" class="lab lbtn${value === current ? ' on' : ''}" aria-pressed="${value === current}" data-hp="${value}" data-key="hp-${value}">${t(`history.${value}`)}</button>`;

function head(answer, state) {
  const current = state.historyPeriod ?? HISTORY_PERIODS[0];
  const chips = HISTORY_PERIODS.map((p) => periodChip(p, current));
  const off = answer.next ? '' : 'disabled';
  const prev = html`<button type="button" class="btn" data-hd="${answer.prev}" data-key="hd-prev" aria-label="${t('history.prev')}" title="${t('history.prev')}">‹</button>`;
  const next = html`<button type="button" class="btn" data-hd="${answer.next ?? ''}" data-key="hd-next" aria-label="${t('history.next')}" title="${t('history.next')}" ${off}>›</button>`;
  const today = html`<button type="button" class="btn" data-today data-key="hd-today">${t('history.today')}</button>`;
  return html`<div class="hhead"><h2 class="hname">${name(answer)}</h2><div class="hchoices" role="group" aria-label="${t('history.period')}">${chips}</div><div class="hmoves">${prev}${next}${today}</div></div>`;
}

// The five figures; the cost carries the note and the link to Costs.
function totals(answer) {
  const n = answer.totals;
  const figure = (key) => kpi({ label: t(`history.${key}`), value: n[key] });
  const cost = money(n.cost_usd, n.cost_partial ? { calls: 1 } : {});
  const link = html`<button type="button" class="btn" data-go="costs" data-key="history-costs">${t('history.cost_see')}</button>`;
  const costKpi = kpi({
    label: t('history.cost'),
    value: cost,
    sub: t('history.cost_note'),
    extra: link,
  });
  return html`<div class="hkpis">${KINDS.map(figure)}${costKpi}</div>`;
}

// Where a dropped CR went, when the record says.
function destination(to) {
  if (!to) return '';
  if (to === '6-trash') return t('history.to_trash');
  if (to === '3-ready') return t('history.to_ready');
  if (to === '1-inbox') return t('history.to_inbox');
  const found = /^2-backlog\/(P\d)$/.exec(to);
  return found ? t('history.to_backlog', { priority: found[1] }) : '';
}

// The key a row opens: the running batch's CR by its own key, any other CR by the History's,
// and nothing when the record holds no folder.
function openKey(e, state) {
  const running = state.data?.batch;
  if (running?.id === e.batch && crsOf(running).some((c) => c.cr === e.cr)) return `c:${e.cr}`;
  return e.folder ? `h:${e.cr}` : null;
}

const fact = (text) => (text ? html`<span>${text}</span>` : '');

function event(e, state) {
  const key = openKey(e, state);
  const variant = VARIANT[e.kind] ?? 'queued';
  const chip = tag(`st ${variant}`, html`${stateIcon(variant)}${t(`history.kind.${e.kind}`)}`);
  const ended = e.kind !== 'opened';
  const rounds = ended && e.rounds != null ? fact(tn('history.rounds', e.rounds)) : '';
  const cost = ended ? fact(money(e.cost_usd, e.cost_unpriced)) : '';
  const version = e.version ? fact(t('history.version', { version: e.version })) : '';
  const url = safeUrl(e.pr);
  const pr = url
    ? html`<a href="${url}" target="_blank" rel="noopener" data-key="hpr-${e.cr}-${e.kind}">${prNumber(url)}</a>`
    : '';
  const batch = e.batch
    ? html`<button type="button" class="hbatch" data-hb="${e.batch}" data-key="hb-${e.cr}-${e.kind}" title="${t('history.batch_open', { batch: e.batch })}">${e.batch}</button>`
    : '';
  const top = html`<div class="top"><span class="hat">${hhmm(e.at)}</span>${chip}${tag('cr', e.cr)}</div>`;
  const line = html`<div class="nt" title="${title(e.title)}">${title(e.title)}</div>`;
  const facts = html`<div class="facts">${batch}${rounds}${cost}${fact(destination(e.to))}${version}${pr}</div>`;
  const attrs = key ? opener(key, 'h-') : html`data-key="hrow-${e.cr}-${e.kind}"`;
  return html`<div class="hrow" ${attrs}>${top}${line}${facts}</div>`;
}

function counts(day) {
  return KINDS.filter((k) => day.counts[k])
    .map((k) => t(COUNT_WORDS[k], { n: day.counts[k] }))
    .join(' · ');
}

function dayBlock(day, state) {
  const label = format(day.day, { weekday: 'long', day: 'numeric', month: 'long' });
  const rows = day.items.map((e) => event(e, state));
  return html`<section class="hday"><h3><span>${label}</span><span class="hcounts">${counts(day)}</span></h3><div class="hrows">${rows}</div></section>`;
}

function foot(answer) {
  const lines = [];
  if (answer.undated > 0) {
    const costs = html`<button type="button" class="btn" data-go="costs" data-key="history-undated-costs">${t('history.cost_see')}</button>`;
    lines.push(
      html`<div class="hfoot" data-key="history-undated">${tn('history.undated', answer.undated)}${costs}</div>`,
    );
  }
  if (answer.unreadable > 0) {
    lines.push(
      html`<div class="hfoot" data-key="history-unreadable">${tn('history.unreadable', answer.unreadable)}</div>`,
    );
  }
  return html`${lines}`;
}

// The read's error, with the last good answer still shown under it.
const problem = (page) =>
  page.error
    ? html`<div class="herr" data-key="history-error">${t('history.error', { error: page.error })} ${page.unread ? '' : t('history.error_kept')}</div>`
    : '';

function body(state) {
  const page = state.historyPage;
  if (page.unread) return problem(page);
  const list = page.days.length
    ? html`${page.days.map((d) => dayBlock(d, state))}`
    : empty(t('history.empty'));
  return html`${head(page, state)}${problem(page)}${totals(page)}${list}${foot(page)}`;
}

export function render(state) {
  if (!state.historyPage) return html`<div class="histview">${empty(t('stats.loading'))}</div>`;
  return html`<div class="histview">${body(state)}</div>`;
}

const periodOf = (state) => state.historyPeriod ?? HISTORY_PERIODS[0];

export function mount(root) {
  const offBatch = delegate(root, 'click', '[data-hb]', (_, el) =>
    go({ view: 'batch', batch: el.dataset.hb }),
  );
  // The clicks of a row's own links never open the row: this comes before the opener on the root.
  const offStop = ['click', 'keydown'].map((type) =>
    delegate(root, type, '.hrow a, .hrow button', (event) => event.stopImmediatePropagation()),
  );
  const offOpen = bindOpen(root);
  const offPeriod = delegate(root, 'click', '[data-hp]', (_, el) =>
    go({ hp: el.dataset.hp === HISTORY_PERIODS[0] ? null : el.dataset.hp }),
  );
  const offMove = delegate(root, 'click', '[data-hd]', (_, el) => {
    if (el.dataset.hd) go({ hd: el.dataset.hd });
  });
  const offToday = delegate(root, 'click', '[data-today]', () => go({ hd: null }));
  let key = askedKey(periodOf(snapshot()), snapshot().historyDate);
  let stop = () => {};
  // Another period's answer never stays under the shown period's name: loading, then a read.
  const begin = () => {
    const now = snapshot();
    if (now.historyPage && now.historyPage.asked !== key) update({ historyPage: null });
    stop = startFeed(periodOf(now), now.historyDate);
  };
  begin();
  const unsub = subscribe((state) => {
    const next = askedKey(periodOf(state), state.historyDate);
    if (next === key) return;
    key = next;
    stop(); // the feed of the old period never keeps writing the page
    begin();
  });
  return () => {
    for (const off of [...offStop, offBatch, offOpen, offPeriod, offMove, offToday]) off();
    unsub();
    stop();
  };
}
