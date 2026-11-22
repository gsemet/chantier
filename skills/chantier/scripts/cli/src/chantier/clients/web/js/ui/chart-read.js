// Reading a chart's points (ui/chart.js): hover, keyboard focus and a tap light a column and write
// its text in the chart's readout line. One tab stop per chart; Left, Right, Home and End walk the
// columns. Bound once on a view's root by delegation; it writes only the readout's text.
import { delegate } from '../core/dom.js';

const COL = '.chart-col';

const readout = (col) => col.closest('.chart').querySelector('.chart-read');

// With nothing pointed the readout shows its hint; the focused or hovered column wins.
function settle(chart) {
  const out = chart.querySelector('.chart-read');
  const col = chart.querySelector(`${COL}:focus`) ?? chart.querySelector(`${COL}:hover`);
  out.textContent = col ? col.getAttribute('aria-label') : out.dataset.hint;
}

// The focused column is the chart's one tab stop.
function stop(col) {
  for (const other of col.parentElement.children) other.tabIndex = other === col ? 0 : -1;
}

function walk(event, col) {
  const cols = [...col.parentElement.children];
  const at = cols.indexOf(col);
  const to = { ArrowLeft: at - 1, ArrowRight: at + 1, Home: 0, End: cols.length - 1 }[event.key];
  if (to === undefined) return;
  event.preventDefault();
  cols[Math.min(Math.max(to, 0), cols.length - 1)].focus();
}

export function bindCharts(root) {
  const show = (_, col) => {
    readout(col).textContent = col.getAttribute('aria-label');
  };
  const rest = (_, col) => settle(col.closest('.chart'));
  const offs = [
    delegate(root, 'mouseover', COL, show),
    delegate(root, 'mouseout', COL, rest),
    delegate(root, 'focusin', COL, (event, col) => {
      stop(col);
      show(event, col);
    }),
    delegate(root, 'focusout', COL, rest),
    delegate(root, 'click', COL, (_, col) => col.focus()),
    delegate(root, 'keydown', COL, walk),
  ];
  return () => {
    for (const off of offs) off();
  };
}
