// Home, the backlog block: the pipeline from the inbox to 3-ready, and the last merged CRs.
import { html, vars } from '../core/dom.js';
import { percent } from '../core/format.js';
import { knows } from '../core/router.js';
import { tally } from '../model/grill.js';
import { t } from '../model/words.js';
import { dot } from '../ui/parts.js';

const ROWS = ['inbox', 'P1', 'P2', 'P3', 'P4', '3-ready'];
const LAST_MERGED = 4;

const COLORS = {
  spec: 'var(--green)',
  grill: 'var(--amber)',
  raw: 'var(--queued-bar)',
  auto: 'var(--violet)',
};

const WORDS = { spec: 'pipe.specified', grill: 'pipe.grill', raw: 'pipe.raw', auto: 'pipe.auto' };

const label = (bucket) => (bucket === 'inbox' ? t('priority.inbox') : bucket);

const seg = (n, color, whole) =>
  n ? html`<i data-vars="${vars({ '--w': `${percent(n, whole)}%`, '--c': color })}"></i>` : '';

function pipeRow(bucket, items, whole) {
  const c = tally(items);
  const parts = ['spec', 'grill', 'raw', 'auto'].map((k) => seg(c[k], COLORS[k], whole));
  return html`<div class="pipe-row"><span>${label(bucket)}</span><div class="bar">${parts}</div><span class="n">${items.length}</span></div>`;
}

const mergedRow = (m) =>
  html`<div class="x"><b>${m.cr}</b><span class="ell">${m.title}</span><span class="r">${(m.when ?? '').slice(5, 10)}</span></div>`;

export function backlogBlock(state) {
  const backlog = state.data.backlog ?? {};
  const whole = Math.max(1, ...ROWS.map((b) => (backlog[b] ?? []).length));
  const legend = Object.keys(WORDS).map((k) => html`<span>${dot(COLORS[k])}${t(WORDS[k])}</span>`);
  const sort = knows('triage')
    ? html`<button class="more" type="button" data-go="triage">${t('home.sort')}</button>`
    : '';
  const merged = (state.data.merged ?? []).slice(0, LAST_MERGED);
  return html`<section class="block side"><h2>${t('home.pipeline')}${sort}</h2><div class="pipe">${ROWS.map((b) => pipeRow(b, backlog[b] ?? [], whole))}</div><div class="legend">${legend}</div><h3>${t('home.last_merged')} <span class="sub">${t('home.total', { n: state.data.merged_total ?? 0 })}</span></h3><div class="list">${merged.map(mergedRow)}</div></section>`;
}
