// The Dashboard's Spending tab: the cost per merged CR, the spend per batch (by model or by role,
// the Costs card's switch), the outside-the-batches line and the ranking of the most expensive CRs.
//   spending(a, by) returns the tab's markup; bindTop(root) opens a ranked CR's PR in a new tab.
import { delegate, html } from '../core/dom.js';
import { safeUrl, title } from '../core/format.js';
import { parseModel } from '../model/models.js';
import { money } from '../model/receipt.js';
import { t } from '../model/words.js';
import { lineChart, stackChart } from '../ui/chart.js';
import { empty } from '../ui/parts.js';
import { PART_COLOR, partWord, tile } from './dashboard-tiles.js';

const MODES = ['model', 'role'];

// A partly priced figure reads "at least": `money` takes the map of what is not priced.
const cost = (amount, partial) => money(amount, partial ? { calls: 1 } : {});

function switcher(by) {
  const buttons = MODES.map(
    (mode) =>
      html`<button type="button" data-spend-by="${mode}" data-key="spend-by-${mode}" aria-pressed="${by === mode}">${t(`costs.money_by_${mode}`)}</button>`,
  );
  return html`<div class="seg" role="group" aria-label="${t('costs.money_switch')}">${buttons}</div>`;
}

// A model series' word: the model's name and version, or the folded ones, or what is not split.
function modelWord(s) {
  if (s.key === 'unsplit') return t('dashboard.unsplit');
  if (s.key === 'other') return t('dashboard.other_models');
  const m = parseModel(s.models[0]);
  return m.version ? `${m.name} ${m.version}` : m.name;
}

const modelColor = (key) => PART_COLOR[key] ?? `var(--${key === 'other' ? 'm8' : key})`;

function seriesOf(split, by) {
  if (by === 'role') {
    return split.series.map((key) => ({ key, word: partWord(key), color: PART_COLOR[key] }));
  }
  return split.series.map((s) => ({ key: s.key, word: modelWord(s), color: modelColor(s.key) }));
}

function outside(o, a) {
  if (o.usd == null) return t('dashboard.outside_none');
  const line = t('dashboard.outside', { x: cost(o.usd, o.unpriced) });
  return `${line} (${t('dashboard.covers', { n: o.covered, total: a.total })})`;
}

function spendTile(a, by) {
  const s = a.spending.spend;
  const split = s[by];
  const name = t('dashboard.spend');
  const chart = () =>
    stackChart({
      id: 'spend',
      label: name,
      points: a.points,
      values: split.values,
      series: seriesOf(split, by),
      format: (v) => money(v),
      unpriced: true,
    });
  return tile(a, {
    title: name,
    value: cost(s.total, s.unpriced),
    covered: s.covered,
    unpriced: s.unpriced,
    extra: switcher(by),
    chart,
    after: html`<p class="mut">${outside(a.spending.outside, a)}</p>`,
  });
}

function perCrTile(a) {
  const p = a.spending.per_cr;
  const name = t('dashboard.per_cr');
  return tile(a, {
    title: name,
    value: cost(p.ratio, p.unpriced),
    note:
      p.cost == null ? '' : t('dashboard.per_cr_sub', { cost: money(p.cost), merged: p.merged }),
    covered: p.covered,
    unpriced: p.unpriced,
    chart: () =>
      lineChart({
        id: 'per-cr',
        label: name,
        points: a.points,
        values: p.values,
        series: [{ key: 'v', word: name, color: 'var(--accent)' }],
        format: (v) => money(v),
        unpriced: true,
      }),
  });
}

// A ranked CR: its number links to its PR in a new tab when it has one, and so does its row.
function row(c) {
  const url = safeUrl(c.pr);
  const id = url
    ? html`<a href="${url}" target="_blank" rel="noopener"><b>${c.cr}</b></a>`
    : html`<b>${c.cr}</b>`;
  const attrs = url ? html` class="click" data-pr="${url}"` : '';
  const text = title(c.title);
  const rounds = typeof c.rounds === 'number' ? c.rounds : '—';
  return html`<tr${attrs}><td>${id}</td><td class="tt hide-phone"><span class="ct" title="${text}">${text}</span></td><td>${c.batch ?? ''}</td><td class="num">${rounds}</td><td class="num">${cost(c.cost_usd, c.unpriced)}</td></tr>`;
}

function topTable(a) {
  const top = a.spending.top;
  const cells = [
    ['costs.th_cr', ''],
    ['costs.th_title', 'tt hide-phone'],
    ['costs.th_batch', ''],
    ['costs.th_rounds', 'num'],
    ['costs.th_cost', 'num'],
  ];
  const head = cells.map(([word, cls]) => html`<th class="${cls}">${t(word)}</th>`);
  const cover = t('dashboard.covers', { n: top.covered, total: a.total });
  const body = top.rows.length
    ? html`<div class="tbl"><table><thead><tr>${head}</tr></thead><tbody>${top.rows.map(row)}</tbody></table></div>`
    : empty(t('dashboard.top_none'));
  return html`<section class="dtop"><h2 class="h2t">${t('dashboard.top')}</h2><p class="mut">${cover}</p>${body}</section>`;
}

export const spending = (a, by) => html`${perCrTile(a)}${spendTile(a, by)}${topTable(a)}`;

// A click on a ranked row (not on its link) opens the same address in a new tab.
export const bindTop = (root) =>
  delegate(root, 'click', 'tr[data-pr]', (event, rowEl) => {
    if (event.target.closest('a')) return;
    window.open(rowEl.dataset.pr, '_blank', 'noopener');
  });
