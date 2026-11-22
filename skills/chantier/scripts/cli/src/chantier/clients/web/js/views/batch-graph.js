// The batch graph: the CRs in levels, each CR in its level, ordered within it by a barycentre pass of
// the drawn arrows (its place changes when a wait changes or, while folded, when a CR merges or is
// cancelled), with an arrow from a CR to the one that waits for it. Only the transitive reduction of
// the waits is drawn, and the done CRs are folded behind one chip on a live batch. The arrows are an
// SVG layer measured from the nodes and redrawn after every paint, on a resize and once the font is
// loaded. A hover (or a focus) lights a CR, what it waits for and what waits for it, on the graph
// and on the Gantt (any element that carries a `data-id`). A CR that changed state in the last
// ten minutes carries a small burst. An arrow is a line only: one head is drawn per waiting CR,
// where all its arrows meet, and the lit arrows and heads are drawn again in a layer above the
// cards (`svg.edges.top`), so an arrow that skips a level can be followed end to end.
import { $, $$, delegate, html, setHtml } from '../core/dom.js';
import { age, slug, title, usd } from '../core/format.js';
import {
  gateWords,
  levels,
  mergedAt,
  orderLevels,
  reducedEdges,
  related,
  roundText,
  vstate,
} from '../model/semantics.js';
import { crKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { card, cardMark } from '../ui/card.js';
import { icon } from '../ui/icons.js';
import { opener } from '../ui/open.js';
import { nextTag, stateIcon } from '../ui/parts.js';

const BURST_MS = 10 * 60 * 1000;

// The badge in a node's top right corner: the state's icon and word, both in the state's colour.
export const badge = (c) =>
  html`<span class="sb ${vstate(c)}" title="${t(`state.${vstate(c)}`)}">${stateIcon(c)}<span class="sbw">${t(`state.${vstate(c)}`)}</span></span>`;

// What a merged CR's band adds: when it merged and, when the record holds it, the long gate.
function mergedBand(c, now) {
  if (c.state !== 'merged') return '';
  const gate = gateWords(c);
  const line = gate ? html`<span class="gate">${t('gate.label')}: ${gate}</span>` : '';
  return html`<span>${t('prs.merged_ago', { age: age(mergedAt(c), now) })}</span>${line}`;
}

// A CR of a closed record: its folder, title, badge, rounds, cost and "PR"; no opener, no phase.
const deps = (c) =>
  c.after?.length
    ? html`<span title="${t('batch.waits_for', { list: c.after.join(', ') })}">${icon('dep')} ${c.after.length}</span>`
    : '';
const prMark = (c) => (c.pr ? html`<span>${t('pr.tag')}</span>` : '');

const recordedNode = (c) =>
  card({
    classes: 'node',
    variants: ['compact'],
    attrs: html`data-id="${c.cr}" data-key="node-${c.cr}" tabindex="0"`,
    top: html`<span class="tag cr">${c.cr}</span><span class="lbl">${slug(c.folder)}</span>${badge(c)}`,
    title: title(c.title),
    meta: html`${c.round == null ? '' : html`<span>r${c.round}</span>`}${deps(c)}${prMark(c)}`,
    end: usd(c.cost_usd),
  });

// The burst of a CR whose state changed less than ten minutes before the server's instant: computed
// from the record's own time, so a reload or a tab change neither restarts nor clears it. A
// cancelled CR has no state colour of its own: it takes the queued one.
function spark(c, now) {
  const at = c.times.state_at;
  if (!(Date.parse(now) - Date.parse(at) < BURST_MS)) return '';
  const tone = c.state === 'cancelled' ? 'queued' : vstate(c);
  return html`<span class="spark ${tone}" title="${t('batch.changed_ago', { age: age(at, now) })}">${icon('spark')}</span>`;
}

const node = (c, batch, now) =>
  card({
    classes: 'node',
    variants: ['compact'],
    priority: c.stage,
    attrs: html`data-id="${c.cr}" ${opener(crKey(c), 'node-')}`,
    top: html`<span class="tag cr">${c.cr}</span>${nextTag(c)}<span class="lbl">${slug(c.folder)}</span>${spark(c, now)}${badge(c)}`,
    title: title(c.title),
    body: c.phase ? html`<div class="np" title="${t('step')}">${c.phase}</div>` : '',
    meta: html`<span>r${roundText(c, batch)}</span>${deps(c)}${prMark(c)}`,
    end: usd(c.cost_usd),
    foot: mergedBand(c, now),
  });

const level = (rows, i, draw) => {
  const head = i === 0 ? t('batch.no_dep') : t('batch.level', { i });
  return html`<div class="lvl"><div class="lvlh">${head}</div>${rows.map(draw)}</div>`;
};

const done = (c) => c.state === 'merged' || c.state === 'cancelled';

let unfolded = false; // the done CRs are folded at every page load

export function toggleFold() {
  unfolded = !unfolded;
}

// The bar above the graph: the toggle chip, filled while the done CRs are drawn, outlined while folded.
const foldBar = (rows) => {
  const merged = rows.filter((c) => c.state === 'merged').length;
  const cancelled = rows.filter((c) => c.state === 'cancelled').length;
  const text =
    t('batch.fold_merged', { n: merged }) +
    (cancelled ? ` · ${t('batch.fold_cancelled', { n: cancelled })}` : '');
  const hint = t(unfolded ? 'batch.fold_hide' : 'batch.fold_show');
  return html`<div class="gbar"><button type="button" class="tag st merged${unfolded ? '' : ' off'}" data-fold aria-expanded="${unfolded}" title="${hint}">${text}</button></div>`;
};

// The graph of the live batch's rows, or of a closed record's (`recorded`: rows from `recordRows`).
export function graphBlock(rows, batch, now, recorded = false) {
  const draw = recorded ? recordedNode : (c) => node(c, batch, now);
  const hint = recorded ? '' : html`<p class="note">${t('batch.hover')}</p>`;
  const foldable = !recorded && rows.some(done) && rows.some((c) => !done(c));
  const shown = foldable && !unfolded ? rows.filter((c) => !done(c)) : rows;
  const cols = orderLevels(levels(shown), reducedEdges(shown));
  const bar = foldable ? foldBar(rows) : '';
  return html`${bar}<div class="gscroll"><div class="graph" data-key="graph"><svg class="edges" aria-hidden="true"></svg>${cols.map((r, i) => level(r, i, draw))}<svg class="edges top" aria-hidden="true"></svg></div></div>${hint}`;
}

const TAIL = 12; // the last, straight stretch of an arrow, along which its head points

// One arrow, from the right edge of a CR to the left edge of the one that waits for it: a curve
// that ends level, then a short straight segment that ends on the card's edge, where the head is.
function path(graph, from, to) {
  const g = graph.getBoundingClientRect();
  const a = from.getBoundingClientRect();
  const b = to.getBoundingClientRect();
  const x1 = a.right - g.left;
  const y1 = a.top + a.height / 2 - g.top;
  const x2 = b.left - g.left;
  const y2 = b.top + b.height / 2 - g.top;
  const tail = Math.min(TAIL, Math.max(4, (x2 - x1) / 3));
  const mid = (x1 + x2 - tail) / 2;
  const d = `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2 - tail},${y2} L${x2},${y2}`;
  return html`<path data-from="${from.dataset.id}" data-to="${to.dataset.id}" d="${d}"></path>`;
}

const HEAD = 8; // the head's length and height

// The head of a waiting CR: a triangle whose tip is where its arrows end, the middle of its card's
// left edge, and whose base is 8 px to the left.
function head(graph, to) {
  const g = graph.getBoundingClientRect();
  const b = to.getBoundingClientRect();
  const x = b.left - g.left;
  const y = b.top + b.height / 2 - g.top;
  const d = `M${x - HEAD},${y - HEAD / 2} L${x},${y} L${x - HEAD},${y + HEAD / 2} z`;
  return html`<path class="head" data-to="${to.dataset.id}" d="${d}"></path>`;
}

export const marker = () =>
  html`<defs><marker id="ar" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto"><path class="head" d="M0,0 L10,5 L0,10 z"></path></marker></defs>`;

let lit = null;

// Light a CR and its neighbours, or clear the light with `null`. The lit arrows and heads are copied
// into the top layer, when the root holds one.
export function light(root, rows, id) {
  lit = id;
  const near = id ? related(rows, id) : null;
  for (const n of $$('[data-id]', root)) {
    cardMark(n, 'dim', Boolean(near) && !near.has(n.dataset.id));
    cardMark(n, 'highlight', Boolean(near) && near.has(n.dataset.id) && n.dataset.id !== id);
  }
  lightEdges(root, id);
}

const mark = (e, id, on) => {
  e.classList.toggle('hl', on);
  e.classList.toggle('dim', Boolean(id) && !on);
};

// The arrows and heads of the base layer take the light; the lit ones are copied into the top layer.
function lightEdges(root, id) {
  const arrows = $$('svg.edges:not(.top) path[data-from]', root);
  for (const e of arrows)
    mark(e, id, Boolean(id) && (e.dataset.from === id || e.dataset.to === id));
  // a head is lit when a lit arrow ends at it
  const ends = new Set(arrows.filter((e) => e.classList.contains('hl')).map((e) => e.dataset.to));
  for (const h of $$('svg.edges:not(.top) path.head[data-to]', root))
    mark(h, id, Boolean(id) && ends.has(h.dataset.to));
  const top = $('svg.edges.top', root);
  if (!top) return;
  const on = $$('svg.edges:not(.top) path.hl[data-from], svg.edges:not(.top) path.head.hl', root);
  top.replaceChildren(...on.map((e) => e.cloneNode(true)));
}

// Put the light in force back after a redraw (the Gantt's).
export function relight(root, rows) {
  if (lit) light(root, rows, lit);
}

// Draw the arrows for the batch's rows; the light in force is put back.
export function drawEdges(root, rows) {
  const graph = $('.graph', root);
  const svg = $('svg.edges:not(.top)', root);
  if (!graph || !svg) return;
  const found = (id) => $(`.node[data-id="${CSS.escape(id)}"]`, graph);
  const shown = rows.filter((c) => found(c.cr));
  const paths = reducedEdges(shown)
    .map(([a, b]) => [found(a), found(b)])
    .filter(([a, b]) => a && b);
  const targets = [...new Set(paths.map(([, b]) => b))];
  const layers = $$('svg.edges', root);
  // measured from zero: the layers are children of `.graph` and would otherwise count in its size
  for (const layer of layers) {
    layer.setAttribute('width', 0);
    layer.setAttribute('height', 0);
  }
  for (const layer of layers) {
    layer.setAttribute('width', graph.scrollWidth);
    layer.setAttribute('height', graph.scrollHeight);
  }
  const top = $('svg.edges.top', root);
  if (top) top.replaceChildren();
  setHtml(
    svg,
    html`${paths.map(([a, b]) => path(graph, a, b))}${targets.map((b) => head(graph, b))}`,
  );
  if (lit) light(root, rows, lit);
}

// Hover and focus light a CR; leaving it clears. `rows` is read when the event fires.
export function bindLight(root, rowsNow) {
  const on = (_event, node) => light(root, rowsNow(), node.dataset.id);
  const off = (event, node) => {
    if (!node.contains(event.relatedTarget)) light(root, rowsNow(), null);
  };
  const stops = [
    delegate(root, 'mouseover', '[data-id]', on),
    delegate(root, 'mouseout', '[data-id]', off),
    delegate(root, 'focusin', '[data-id]', on),
    delegate(root, 'focusout', '[data-id]', off),
  ];
  return () => {
    for (const stop of stops) stop();
    lit = null;
  };
}
