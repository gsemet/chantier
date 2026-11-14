// The batch graph: the CRs in levels, grouped by state, with an arrow from a CR to the one that
// waits for it. The arrows are an SVG layer measured from the nodes and redrawn after every paint
// and on a resize. A hover (or a focus) lights a CR, what it waits for and what waits for it.
import { $, $$, delegate, html, setHtml } from '../core/dom.js';
import { slug, title, usd } from '../core/format.js';
import {
  groupByState,
  levels,
  related,
  roundText,
  STATE_ORDER,
  vstate,
} from '../model/semantics.js';
import { crKey } from '../model/targets.js';
import { t } from '../model/words.js';
import { icon } from '../ui/icons.js';
import { opener } from '../ui/open.js';
import { dot, stateColor } from '../ui/parts.js';

const node = (c, batch) =>
  html`<div class="node st-${vstate(c)}" data-id="${c.cr}" ${opener(crKey(c), 'node-')}><div class="row-tags"><span class="tag cr">${c.cr}</span><span class="lbl">${slug(c.folder)}</span></div><div class="nt">${title(c.title)}</div><div class="nm"><span>r${roundText(c, batch)}</span>${c.after?.length ? html`<span>${icon('dep')} ${c.after.length}</span>` : ''}${c.pr ? html`<span>PR</span>` : ''}<span class="r">${usd(c.cost_usd)}</span></div></div>`;

const group = (g, batch) =>
  html`<div class="grp"><div class="gh">${dot(stateColor(g.state))}${t(`state.${g.state}`)} · ${g.rows.length}</div>${g.rows.map((c) => node(c, batch))}</div>`;

const level = (rows, i, batch) => {
  const head = i === 0 ? t('batch.no_dep') : t('batch.level', { i, j: i - 1 });
  return html`<div class="lvl"><div class="lvlh">${head}</div>${groupByState(rows).map((g) => group(g, batch))}</div>`;
};

const legend = () =>
  html`<div class="legend">${STATE_ORDER.map((s) => html`<span class="k">${dot(stateColor(s))}${t(`state.${s}`)}</span>`)}<span class="k">${t('batch.arrow')}</span></div>`;

export const graphBlock = (batch) =>
  html`${legend()}<div class="graph" data-key="graph"><svg class="edges" aria-hidden="true"></svg>${levels(batch.crs).map((rows, i) => level(rows, i, batch))}</div><p class="note">${t('batch.hover')}</p>`;

// One arrow, from the right edge of a CR to the left edge of the one that waits for it.
function path(graph, from, to) {
  const g = graph.getBoundingClientRect();
  const a = from.getBoundingClientRect();
  const b = to.getBoundingClientRect();
  const x1 = a.right - g.left;
  const y1 = a.top + a.height / 2 - g.top;
  const x2 = b.left - g.left;
  const y2 = b.top + b.height / 2 - g.top;
  const mid = (x1 + x2) / 2;
  const d = `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2 - 6},${y2}`;
  return html`<path data-from="${from.dataset.id}" data-to="${to.dataset.id}" d="${d}" marker-end="url(#ar)"></path>`;
}

const marker = () =>
  html`<defs><marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="head" d="M0,0 L10,5 L0,10 z"></path></marker></defs>`;

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
