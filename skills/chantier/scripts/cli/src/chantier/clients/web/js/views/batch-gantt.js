// The Batch Gantt: one line per CR on a real time scale, from the batch's start to now. A CR's bar
// is split into segments, one per period in a state, in that state's colour; the open segment runs
// to the "now" line, hatched. A CR that has not started is a cross at the right edge. The arrows
// are the graph's (`edges`), vertical. The label cards are laid out by the browser; the time area
// is one SVG drawn after paint from their measured rows, and again on a resize.
import { $, html, setHtml } from '../core/dom.js';
import { hhmm, shortDate, title } from '../core/format.js';
import { snapshot } from '../core/store.js';
import { edges, STATE_ORDER, vstate } from '../model/semantics.js';
import { crKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { card } from '../ui/card.js';
import { opener } from '../ui/open.js';
import { badge, bindLight, marker, relight } from './batch-graph.js';

const BAR = 16; // the height of a bar, in pixels
const END = 5; // the radius of the end mark and the half size of the cross
const HEAD = 22; // the height of the axis labels' band
const LABEL_PX = 56; // the room an axis label needs
const MINUTE = 60000;
const HOUR = 3600000;
const DAY = 24 * HOUR;

const rowsNow = () => snapshot().data?.batch?.crs ?? [];

// The axis: from the batch's start (its `created`, else its first event; never after a CR's start)
// to the server's instant. `pct(iso)` is an instant's place on it, in [0, 100].
function scaleOf(state) {
  const { batch, events } = state.data;
  const now = Date.parse(state.now);
  const starts = [batch.created ?? events?.[0]?.t, ...batch.crs.map((c) => c.times.started_at)];
  const start = Math.min(now, ...starts.filter(Boolean).map((iso) => Date.parse(iso)));
  const span = Math.max(now - start, MINUTE);
  const pct = (iso) => Math.min(100, Math.max(0, ((Date.parse(iso) - start) / span) * 100));
  return { start, now, pct };
}

// The whole hours of the axis (whole days when it spans more than 48 h), labelled in local time;
// only every few of them when the area is narrow.
function ticksOf({ start, now, pct }, width) {
  const days = now - start > 2 * DAY;
  const at = new Date(start);
  at.setMinutes(0, 0, 0);
  if (days) at.setHours(0);
  const all = [];
  for (;;) {
    if (days) at.setDate(at.getDate() + 1);
    else at.setHours(at.getHours() + 1);
    if (at.getTime() > now) break;
    all.push(at.getTime());
  }
  const every = Math.max(1, Math.ceil(all.length / Math.max(1, Math.floor(width / LABEL_PX))));
  return all.map((ms, i) => ({
    x: pct(new Date(ms).toISOString()),
    label: i % every ? '' : (days ? shortDate : hhmm)(new Date(ms).toISOString()),
  }));
}

// The label cell: the one card, compact, with its priority chip, CR chip, title and state badge.
const label = (c) =>
  card({
    classes: 'glabel',
    variants: ['compact'],
    priority: c.priority,
    attrs: html`data-id="${c.cr}" ${opener(crKey(c), 'gantt-')}`,
    top: html`<span class="tag cr">${c.cr}</span>${badge(c)}`,
    title: title(c.title),
  });

export function render(state) {
  const rows = state.data.batch.crs;
  return html`<div class="gscroll" data-scroll="gantt"><div class="gt" data-key="gantt"><div class="gt-labels"><div class="gt-axis"></div>${rows.map(label)}</div><div class="gt-area"><svg class="edges gt-svg" aria-hidden="true"></svg></div></div></div><p class="note">${t('batch.hover')}</p>`;
}

const defs = () =>
  html`<defs>${marker()}${STATE_ORDER.map((s) => html`<pattern id="hatch-${s}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line class="hatch ${s}" x1="0" y1="0" x2="0" y2="6"></line></pattern>`)}</defs>`;

// One segment: solid in its state's colour, or hatched when it is the CR's open one (then in the
// row's visible state, so it matches the badge).
function segment(c, s, scale, cy) {
  const open = s.to === null;
  const state = open ? vstate(c) : s.state;
  const x = scale.pct(s.from);
  const width = (open ? 100 : scale.pct(s.to)) - x;
  const span = t('batch.gantt_span', {
    from: hhmm(s.from),
    to: open ? t('batch.gantt_now') : hhmm(s.to),
  });
  const fill = open ? `url(#hatch-${state})` : 'currentColor';
  return html`<rect class="seg ${state}" x="${x}%" y="${cy - BAR / 2}" width="${width}%" height="${BAR}" rx="3" fill="${fill}"><title>${t(`state.${state}`)} ${span}</title></rect>`;
}

const cross = (width, cy) =>
  html`<g class="cross queued"><title>${t('batch.gantt_not_started')}</title><line x1="${width - 2 * END}" y1="${cy - END}" x2="${width - 2}" y2="${cy + END}"></line><line x1="${width - 2 * END}" y1="${cy + END}" x2="${width - 2}" y2="${cy - END}"></line></g>`;

// A started CR's bar: its segments, its start time at the left end and, once finished, its end
// time and a round end mark (merged green, cancelled grey).
function bar(c, scale, cy) {
  const { started_at: from, ended_at: to, segments } = c.times;
  const top = cy - BAR / 2 - 4;
  const end = to
    ? html`<circle class="mark ${c.state === 'cancelled' ? 'queued' : 'merged'}" cx="${scale.pct(to)}%" cy="${cy}" r="${END}" fill="currentColor"></circle><text class="gt-t" x="${scale.pct(to)}%" y="${top}" text-anchor="end">${hhmm(to)}</text>`
    : '';
  return html`${segments.map((s) => segment(c, s, scale, cy))}<text class="gt-t" x="${scale.pct(from)}%" y="${top}">${hhmm(from)}</text>${end}`;
}

// The arrow of one dependency: vertical, at the waiting CR's start (the right edge when it has not
// started), from the row it waits for to its own, the head on its bar.
function arrow([from, to], rows, ys, scale, width) {
  const waiting = rows.find((c) => c.cr === to);
  const x = waiting.times.started_at
    ? (scale.pct(waiting.times.started_at) * width) / 100
    : width - 1;
  const down = ys.get(to) > ys.get(from);
  const end = ys.get(to) + (down ? -BAR / 2 - 1 : BAR / 2 + 1);
  return html`<path data-from="${from}" data-to="${to}" d="M${x},${ys.get(from)} L${x},${end}" marker-end="url(#ar)"></path>`;
}

function drawn(root, state) {
  const rows = state.data.batch.crs;
  const area = $('.gt-area', root).getBoundingClientRect();
  const ys = new Map(
    rows.map((c) => {
      const box = $(`.gt-labels [data-id="${CSS.escape(c.cr)}"]`, root).getBoundingClientRect();
      return [c.cr, box.top - area.top + box.height / 2];
    }),
  );
  const scale = scaleOf(state);
  const ticks = ticksOf(scale, area.width);
  const lines = ticks.map(
    (k) =>
      html`<line class="gt-tick" x1="${k.x}%" y1="${HEAD}" x2="${k.x}%" y2="${area.height}"></line><text class="gt-t" x="${k.x}%" y="${HEAD - 8}" text-anchor="middle">${k.label}</text>`,
  );
  const guides = rows.map(
    (c) =>
      html`<line class="gt-tick" x1="0" y1="${ys.get(c.cr)}" x2="100%" y2="${ys.get(c.cr)}"></line>`,
  );
  const bars = rows.map((c) =>
    c.times.started_at ? bar(c, scale, ys.get(c.cr)) : cross(area.width, ys.get(c.cr)),
  );
  const now = html`<line class="gt-now" x1="100%" y1="0" x2="100%" y2="${area.height}"></line><text class="gt-now-t" x="100%" y="${HEAD - 8}" text-anchor="end">${t('batch.gantt_now')}</text>`;
  const arrows = edges(rows).map((pair) => arrow(pair, rows, ys, scale, area.width));
  return { area, markup: html`${defs()}${guides}${lines}${now}${bars}${arrows}` };
}

// Draw the time area for the live batch's rows; the light in force is put back.
export function after(root, state) {
  const svg = $('svg.gt-svg', root);
  if (!svg) return;
  const { area, markup } = drawn(root, state);
  svg.setAttribute('width', area.width);
  svg.setAttribute('height', area.height);
  setHtml(svg, markup);
  relight(root, state.data.batch.crs);
}

// A resize or the font's arrival changes the rows' heights: the area is drawn again, once per frame.
export function mount(root) {
  let frame = 0;
  const onResize = () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => after(root, snapshot()));
  };
  window.addEventListener('resize', onResize);
  let alive = true;
  document.fonts?.ready.then(() => alive && onResize());
  const stop = bindLight(root, rowsNow);
  return () => {
    alive = false;
    window.removeEventListener('resize', onResize);
    cancelAnimationFrame(frame);
    stop();
  };
}
