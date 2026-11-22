// The chart component (DESIGN.md "Components"): lines and stacked bars, one point per slot, as
// inline SVG written here and styled in css/components/chart.css only. No library, no `style`
// attribute: a colour or a count reaches the sheet through `data-vars`.
//   lineChart(spec) and stackChart(spec) return markup; bindCharts(root) (ui/chart-read.js) binds
//   the reading of a point.
// A spec is { id, label, points, series, values, format, unpriced }: `points` are the answer's
// { batch, n, closed, unpriced }; `values` is aligned with `points` (null, a number for a
// one-series chart, or a dict keyed by series); `series` are { key, word, color, dash }, `color`
// a token (`var(--…)`); `format(value)` writes a value; `unpriced` marks a point the record says
// is not all priced in its reading.
import { html, raw, vars } from '../core/dom.js';
import { dayOf } from '../model/history.js';
import { t } from '../model/words.js';

export { bindCharts } from './chart-read.js';

const SLOT = 100; // a point's width in the viewBox; the viewBox is stretched to the tile
const HEIGHT = 100;
const BAR = 60;
const MANY = 12; // up to this many points every batch number is written
const FIFTH = 5;

const numeric = (v) => typeof v === 'number' && Number.isFinite(v);

// A series' figure in a point's value, or null.
function figure(value, key) {
  const v = value !== null && typeof value === 'object' ? value[key] : value;
  return numeric(v) ? v : null;
}

const sum = (list) => list.reduce((n, v) => n + v, 0);

const centre = (i) => i * SLOT + SLOT / 2;

const level = (v, top) => +(HEIGHT - (v / top) * HEIGHT).toFixed(2);

// The top of the y axis: the largest value (the largest stack), never zero.
function topOf(spec) {
  const totals = spec.values.map((value) => {
    const all = spec.series.map((s) => figure(value, s.key) ?? 0);
    return spec.stacked ? sum(all) : Math.max(0, ...all);
  });
  return Math.max(0, ...totals) || 1;
}

const colored = (s) => vars({ '--c': s.color });

// A series' points as the runs of neighbours that hold a figure: a run of one is a mark only.
function runsOf(points) {
  const runs = [];
  const run = [];
  for (const p of points) {
    if (p) run.push(p);
    else if (run.length) runs.push(run.splice(0));
  }
  if (run.length) runs.push(run);
  return runs;
}

function lineOf(spec, s, top) {
  const dots = spec.values.map((value, i) => {
    const v = figure(value, s.key);
    return v === null ? null : { x: centre(i), y: level(v, top) };
  });
  const lines = runsOf(dots)
    .filter((run) => run.length > 1)
    .map((run) => `M${run.map((p) => `${p.x} ${p.y}`).join('L')}`)
    .map((d) => html`<path class="chart-line${s.dash ? ' chart-dash' : ''}" d="${d}" />`);
  const marks = dots
    .filter(Boolean)
    .map((p) => html`<path class="chart-mark" d="M${p.x} ${p.y}h0" />`);
  return html`<g data-vars="${colored(s)}">${lines}${marks}</g>`;
}

// One bar: its segments in the series' order, the first at the bottom.
function barOf(spec, value, i, top) {
  let base = 0;
  const rects = spec.series.flatMap((s) => {
    const v = figure(value, s.key);
    if (v === null || v <= 0) return [];
    const y = level(base + v, top);
    const h = +((v / top) * HEIGHT).toFixed(2);
    base += v;
    return [
      html`<rect class="chart-bar" x="${i * SLOT + (SLOT - BAR) / 2}" y="${y}" width="${BAR}" height="${h}" data-vars="${colored(s)}" />`,
    ];
  });
  return html`<g>${rects}</g>`;
}

// The text of a point: its batch, its day when the record holds one, each series' figure.
function reading(spec, p, i) {
  const value = spec.values[i];
  const day = typeof p.closed === 'string' ? dayOf(p.closed) : '';
  const head = [t('dashboard.batch_n', { n: p.n ?? p.batch }), day].filter(Boolean).join(', ');
  const have = spec.series.map((s) => ({ s, v: figure(value, s.key) })).filter((x) => x.v !== null);
  const items = have.map(({ s, v }) => `${s.word} ${spec.format(v)}`);
  if (have.length > 1 && spec.stacked) {
    items.push(t('dashboard.total_of', { x: spec.format(sum(have.map((x) => x.v))) }));
  }
  if (!items.length) items.push(t('dashboard.no_figure'));
  if (spec.unpriced && p.unpriced) items.push(t('costs.unpriced'));
  return `${head}: ${items.join(', ')}`;
}

function columns(spec) {
  const last = spec.points.length - 1;
  const cols = spec.points.map(
    (p, i) =>
      html`<button type="button" class="chart-col" tabindex="${i === last ? 0 : -1}" aria-label="${reading(spec, p, i)}" data-key="chart-${spec.id}-${i}"></button>`,
  );
  return html`<div class="chart-cols" role="group" aria-label="${spec.label}">${cols}</div>`;
}

// The batch numbers under the plot: all of them for a short range, else the first, the last and
// every fifth (not one right before the last).
function labels(spec) {
  const n = spec.points.length;
  const shown = (i) => n <= MANY || i === 0 || i === n - 1 || (i % FIFTH === 0 && n - 1 - i > 1);
  const cells = spec.points.map((p, i) => html`<span>${shown(i) ? (p.n ?? '') : ''}</span>`);
  return html`<div class="chart-x" aria-hidden="true">${cells}</div>`;
}

function legend(spec) {
  const swatch = (s) =>
    spec.stacked
      ? html`<span class="chart-sq" data-vars="${colored(s)}"></span>`
      : html`<svg class="chart-swatch" viewBox="0 0 16 8" aria-hidden="true" data-vars="${colored(s)}"><path class="chart-line${s.dash ? ' chart-dash' : ''}" d="M0 4h16" /></svg>`;
  const items = spec.series.map((s) => html`<li>${swatch(s)}<span>${s.word}</span></li>`);
  return html`<ul class="chart-legend">${items}</ul>`;
}

function chart(spec, stacked) {
  const full = { ...spec, stacked };
  const top = topOf(full);
  const n = spec.points.length;
  const drawn = stacked
    ? spec.values.map((value, i) => (value == null ? '' : barOf(full, value, i, top)))
    : spec.series.map((s) => lineOf(full, s, top));
  const hint = t('dashboard.read_hint');
  return html`<figure class="chart" data-vars="${vars({ '--n': String(n) })}"><p class="chart-read" aria-live="polite" data-hint="${hint}">${hint}</p><div class="chart-body"><div class="chart-y" aria-hidden="true"><span>${spec.format(top)}</span><span>${spec.format(0)}</span></div><div class="chart-plot"><svg class="chart-svg" viewBox="0 0 ${n * SLOT} ${HEIGHT}" preserveAspectRatio="none" aria-hidden="true">${raw(drawn.map(String).join(''))}</svg>${columns(full)}</div>${labels(full)}<span class="chart-axis" aria-hidden="true">${t('dashboard.axis')}</span></div>${legend(full)}</figure>`;
}

export const lineChart = (spec) => chart(spec, false);

export const stackChart = (spec) => chart(spec, true);
