// The batch graph: the CRs in levels, each CR in its place for its whole life (its level, then the
// record's order), with an arrow from a CR to the one that waits for it. The arrows are an SVG
// layer measured from the nodes and redrawn after every paint, on a resize and once the font is
// loaded. A hover (or a focus) lights a CR, what it waits for and what waits for it.
import { $, $$, delegate, html, setHtml } from '../core/dom.js';
import { age, slug, title, usd } from '../core/format.js';
import {
  gateWords,
  levels,
  mergedAt,
  related,
  roundText,
  STATE_ORDER,
  vstate,
} from '../model/semantics.js';
import { crKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { icon } from '../ui/icons.js';
import { opener } from '../ui/open.js';
import { nextTag, stateIcon } from '../ui/parts.js';

// The badge in a node's top right corner: the state's icon and word, both in the state's colour.
const badge = (c) =>
  html`<span class="sb ${vstate(c)}">${stateIcon(c)}${t(`state.${vstate(c)}`)}</span>`;

// What a merged CR's band adds: when it merged and, when the record holds it, the long gate.
function mergedBand(c, now) {
  if (c.state !== 'merged') return '';
  const gate = gateWords(c);
  const line = gate ? html`<span class="gate">${t('gate.label')}: ${gate}</span>` : '';
  return html`<span>${t('prs.merged_ago', { age: age(mergedAt(c), now) })}</span>${line}`;
}

// A CR of a closed record: its folder, title, badge, rounds, cost and "PR"; no opener, no phase.
const recordedNode = (c) =>
  html`<div class="node card" data-id="${c.cr}" data-key="node-${c.cr}" tabindex="0"><div class="row-tags"><span class="tag cr">${c.cr}</span><span class="lbl">${slug(c.folder)}</span>${badge(c)}</div><div class="nt">${title(c.title)}</div><div class="nm">${c.round == null ? '' : html`<span>r${c.round}</span>`}${c.after?.length ? html`<span>${icon('dep')} ${c.after.length}</span>` : ''}${c.pr ? html`<span>PR</span>` : ''}<span class="r">${usd(c.cost_usd)}</span></div></div>`;

const node = (c, batch, now) =>
  html`<div class="node card" data-id="${c.cr}" ${opener(crKey(c), 'node-')}><div class="row-tags"><span class="tag cr">${c.cr}</span>${nextTag(c)}<span class="lbl">${slug(c.folder)}</span>${badge(c)}</div><div class="nt">${title(c.title)}</div>${c.phase ? html`<div class="np" title="${t('step')}">${c.phase}</div>` : ''}<div class="nm"><span>r${roundText(c, batch)}</span>${c.after?.length ? html`<span>${icon('dep')} ${c.after.length}</span>` : ''}${c.pr ? html`<span>PR</span>` : ''}<span class="r">${usd(c.cost_usd)}</span>${mergedBand(c, now)}</div></div>`;

const level = (rows, i, draw) => {
  const head = i === 0 ? t('batch.no_dep') : t('batch.level', { i });
  return html`<div class="lvl"><div class="lvlh">${head}</div>${rows.map(draw)}</div>`;
};

// "States and arrows": a grey pill that opens a tooltip on hover and on focus.
const legend = () =>
  html`<div class="lgrow"><span class="lgpill" tabindex="0" aria-describedby="lgtip">${t('batch.legend')}<span class="tip" id="lgtip" role="tooltip">${STATE_ORDER.map((s) => html`<span class="k">${stateIcon(s)}${t(`state.${s}`)}</span>`)}<span class="k an">${t('batch.arrow')}</span></span></span><span class="lghint">${t('batch.legend_hint')}</span></div>`;

// The graph of the live batch's rows, or of a closed record's (`recorded`: rows from `recordRows`).
export function graphBlock(rows, batch, now, recorded = false) {
  const draw = recorded ? recordedNode : (c) => node(c, batch, now);
  const hint = recorded ? '' : html`<p class="note">${t('batch.hover')}</p>`;
  return html`${legend()}<div class="gscroll"><div class="graph" data-key="graph"><svg class="edges" aria-hidden="true"></svg>${levels(rows).map((r, i) => level(r, i, draw))}</div></div>${hint}`;
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
  return html`<path data-from="${from.dataset.id}" data-to="${to.dataset.id}" d="${d}" marker-end="url(#ar)"></path>`;
}

const marker = () =>
  html`<defs><marker id="ar" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto"><path class="head" d="M0,0 L10,5 L0,10 z"></path></marker></defs>`;

let lit = null;

// Light a CR and its neighbours, or clear the light with `null`.
export function light(root, rows, id) {
  lit = id;
  const near = id ? related(rows, id) : null;
  for (const n of $$('.node', root)) {
    n.classList.toggle('dim', Boolean(near) && !near.has(n.dataset.id));
    n.classList.toggle('hl', Boolean(near) && near.has(n.dataset.id) && n.dataset.id !== id);
  }
  for (const e of $$('svg.edges path[data-from]', root)) {
    const on = id && (e.dataset.from === id || e.dataset.to === id);
    e.classList.toggle('hl', Boolean(on));
    e.classList.toggle('dim', Boolean(id) && !on);
  }
}

// Draw the arrows for the batch's rows; the light in force is put back.
export function drawEdges(root, rows) {
  const graph = $('.graph', root);
  const svg = $('svg.edges', root);
  if (!graph || !svg) return;
  const found = (id) => $(`.node[data-id="${CSS.escape(id)}"]`, graph);
  const paths = rows.flatMap((c) =>
    (c.after ?? []).map((d) => [found(d), found(c.cr)]).filter(([a, b]) => a && b),
  );
  svg.setAttribute('width', graph.scrollWidth);
  svg.setAttribute('height', graph.scrollHeight);
  setHtml(svg, html`${marker()}${paths.map(([a, b]) => path(graph, a, b))}`);
  if (lit) light(root, rows, lit);
}

// Hover and focus light a CR; leaving it clears. `rows` is read when the event fires.
export function bindLight(root, rowsNow) {
  const on = (_event, node) => light(root, rowsNow(), node.dataset.id);
  const off = (event, node) => {
    if (!node.contains(event.relatedTarget)) light(root, rowsNow(), null);
  };
  const stops = [
    delegate(root, 'mouseover', '.node', on),
    delegate(root, 'mouseout', '.node', off),
    delegate(root, 'focusin', '.node', on),
    delegate(root, 'focusout', '.node', off),
  ];
  return () => {
    for (const stop of stops) stop();
    lit = null;
  };
}
