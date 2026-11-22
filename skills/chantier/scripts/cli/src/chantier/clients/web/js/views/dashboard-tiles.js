// The Dashboard's tiles: the figure card (ui/parts.js:kpi) with its headline, its chart and its
// coverage, and the four Productivity tiles. The views compute no figure: they write what the
// server's `dashboard.get` answered (board/dashboard_page.py).
//   tile(a, spec) returns one tile; productivity(a) the Productivity tab's four.
import { html } from '../core/dom.js';
import { t } from '../model/words.js';
import { lineChart, stackChart } from '../ui/chart.js';
import { kpi, tag } from '../ui/parts.js';
import { lasted } from './costs-receipt.js';

export const count = (n) => (n == null ? '—' : n.toLocaleString('en-US'));

const oneDecimal = (n) => (n == null ? '—' : n.toFixed(1));

// The part colours of the Costs card (model/spend-by.js), and the grey of what is not split.
export const PART_COLOR = {
  steering: 'var(--accent-dark)',
  drivers: 'var(--accent)',
  workers: 'var(--accent-light)',
  agents: 'var(--accent-light)',
  unsplit: 'var(--queued-bar)',
};

export const partWord = (key) =>
  key === 'unsplit' ? t('dashboard.unsplit') : t(`costs.receipt_part_${key}`);

// A tile: `covered` batches hold its figure; with fewer than two, no chart, only the headline (or a
// dash), the coverage and the few-points line. `note` is a word before the coverage; `extra` and
// `after` are markup before and after the chart.
export function tile(a, spec) {
  const {
    title,
    value,
    covered,
    note = '',
    unpriced = false,
    chart,
    extra = '',
    after = '',
  } = spec;
  const body = covered < 2 ? html`<p class="mut">${t('dashboard.few')}</p>` : chart();
  const cover = t('dashboard.covers', { n: covered, total: a.total });
  const badge = unpriced ? html` ${tag('waits', t('costs.unpriced'), { badge: true })}` : '';
  const sub = html`${note ? `${note} · ` : ''}${cover}${badge}`;
  return kpi({
    label: title,
    value: covered ? value : '—',
    sub,
    extra: html`${extra}${body}${after}`,
  });
}

// One series of a line chart: a token colour, dashed or not.
const line = (key, word, color, dash = false) => ({ key, word, color, dash });

const base = (a, id, title, values, format) => ({
  id,
  label: title,
  points: a.points,
  values,
  format,
});

function crsTile(a) {
  const p = a.productivity.crs;
  const series = [
    line('held', t('dashboard.held'), 'var(--accent-light)', true),
    line('merged', t('dashboard.merged'), 'var(--state-merged)'),
  ];
  return tile(a, {
    title: t('dashboard.crs'),
    value: p.merged == null ? '—' : t('dashboard.crs_value', { merged: p.merged, held: p.held }),
    covered: p.covered,
    chart: () => lineChart({ ...base(a, 'crs', t('dashboard.crs'), p.values, count), series }),
  });
}

function roundsTile(a) {
  const p = a.productivity.rounds;
  const series = [line('v', t('dashboard.rounds_mean'), 'var(--accent)')];
  return tile(a, {
    title: t('dashboard.rounds'),
    value: oneDecimal(p.mean),
    covered: p.covered,
    chart: () =>
      lineChart({ ...base(a, 'rounds', t('dashboard.rounds'), p.values, oneDecimal), series }),
  });
}

function durationTile(a) {
  const p = a.productivity.duration;
  const series = [line('v', t('dashboard.duration'), 'var(--accent)')];
  return tile(a, {
    title: t('dashboard.duration'),
    value: lasted(p.median),
    note: t('dashboard.median'),
    covered: p.covered,
    chart: () =>
      lineChart({ ...base(a, 'duration', t('dashboard.duration'), p.values, lasted), series }),
  });
}

function callsTile(a) {
  const p = a.productivity.calls;
  const series = p.parts.map((key) => ({ key, word: partWord(key), color: PART_COLOR[key] }));
  const title = t('dashboard.calls_title');
  return tile(a, {
    title,
    value: count(p.total),
    covered: p.covered,
    chart: () => stackChart({ ...base(a, 'calls', title, p.values, count), series }),
  });
}

export const productivity = (a) =>
  html`${crsTile(a)}${roundsTile(a)}${durationTile(a)}${callsTile(a)}`;
