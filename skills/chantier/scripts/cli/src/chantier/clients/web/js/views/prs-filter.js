// The PRs view's two rows of chips: the state filter (all, open, draft, merged) and the sort (the
// batch's order, opened, last activity, CR number), one on at a time. Both apply in the browser on
// the rows the server answered; the choice is in the address (`st=`, `sort=`), which only the
// router writes: a click asks `go`, replacing the address so that back leaves the page.
import { delegate, html } from '../core/dom.js';
import { go, PRS_SORTS, PRS_STATES } from '../core/router.js';
import { t } from '../model/words.js';

// The rows the state filter keeps: `null` is "all", a closed PR shows under "all" only.
export const filtered = (rows, st) => (st ? rows.filter((r) => r.state === st) : rows);

const stamp = (row, key) => {
  const at = Date.parse(row[key] ?? '');
  return Number.isNaN(at) ? null : at;
};

const crNumber = (row) => Number(String(row.cr).match(/\d+/)?.[0] ?? 0);

// A row with no date goes last; the sort is stable, so ties keep the batch's order.
const newest = (key) => (a, b) => {
  const [x, y] = [stamp(a, key), stamp(b, key)];
  if (x === null || y === null) return (x === null) - (y === null);
  return y - x;
};

const SORTERS = {
  opened: newest('opened_at'),
  activity: newest('updated_at'),
  cr: (a, b) => crNumber(a) - crNumber(b),
};

// The rows in the sort's order: `null` is the batch's order, as the server gave it.
export const sorted = (rows, sort) => (SORTERS[sort] ? [...rows].sort(SORTERS[sort]) : rows);

const chip = (attr, value, current, word) =>
  html`<button type="button" class="lab lbtn${value === current ? ' on' : ''}" aria-pressed="${value === current}" ${attr}="${value}" data-key="${attr}-${value}">${t(word)}</button>`;

const group = (title, chips) =>
  html`<div class="lfil" role="group" aria-label="${t(title)}"><span class="lt">${t(title)}</span>${chips}</div>`;

export function chips(state) {
  const st = state.prsState ?? 'all';
  const sort = state.prsSort ?? 'batch';
  const states = ['all', ...PRS_STATES].map((v) => chip('data-pvf', v, st, `pv.f.${v}`));
  const sorts = ['batch', ...PRS_SORTS].map((v) => chip('data-pvs', v, sort, `pv.s.${v}`));
  return html`<div class="pvfilters">${group('pv.filter', states)}${group('pv.sort', sorts)}</div>`;
}

export function bindFilter(root) {
  const offState = delegate(root, 'click', '[data-pvf]', (_, el) =>
    go({ st: el.dataset.pvf === 'all' ? null : el.dataset.pvf }, { replace: true }),
  );
  const offSort = delegate(root, 'click', '[data-pvs]', (_, el) =>
    go({ sort: el.dataset.pvs === 'batch' ? null : el.dataset.pvs }, { replace: true }),
  );
  return () => {
    offState();
    offSort();
  };
}
