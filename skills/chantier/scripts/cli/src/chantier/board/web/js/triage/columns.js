// The columns of Triage: the Inbox, the Backlog column with its rows P1 to P4, and 3-ready with its
// foot. A group is a dashed frame with its handle, its count and "undo", before the loose post-its.
// Pure: markup from the record and a context (see postit.js), nothing bound here.
import { html, vars } from '../core/dom.js';
import {
  DOTS,
  groupsIn,
  LANES,
  READY,
  readyCounts,
  shownIn,
  stateCounts,
} from '../model/triage.js';
import { t } from '../model/words.js';
import { mark, postit } from './postit.js';

const name = (column) => (column === 'inbox' ? t('priority.inbox') : column);

const ORDER = ['spec', 'auto', 'grill', 'raw'];

function counts(items) {
  const n = stateCounts(items);
  const shown = ORDER.filter((s) => n[s]).map(
    (s) => html`<span class="sc">${mark(s)}${n[s]}</span>`,
  );
  return html`<span class="scs">${shown}</span>`;
}

function frame(group, ctx) {
  const n = group.members.length;
  const handle = html`<span class="gh" draggable="true" data-gdrag="${group.name}">⠿ ${group.name} · ${n}<button type="button" class="x" data-ungroup="${group.name}">${t('groups.undo')}</button></span>`;
  return html`<div class="grpf" data-gid="${group.name}">${handle}${group.members.map((i) => postit(i, ctx))}</div>`;
}

function body(column, items, ctx) {
  const { groups, loose } = groupsIn(items);
  const lane = LANES.includes(column);
  const drop = items.length ? '' : t(lane ? 'triage.empty_row' : 'triage.drop');
  return html`<div class="tbody">${groups.map((g) => frame(g, ctx))}${loose.map((i) => postit(i, ctx))}<div class="dropzone">${drop}</div></div>`;
}

// The foot of 3-ready: the counts, the button, and the running batch's line.
function readyFoot(ctx) {
  const ready = ctx.ready;
  const { auto, specified } = readyCounts(ready);
  const done = ctx.indicator.kind === 'declared';
  const batch = ctx.batch;
  const line =
    batch && batch.state !== 'closed'
      ? t('triage.running', { batch: batch.id, state: batch.state })
      : t('triage.idle');
  const summary = ready.length
    ? html`<small>${t('triage.ready_counts', { specified, auto })}</small>`
    : '';
  const label = done ? t('triage.declared') : t('triage.declare');
  return html`<div class="rfoot">${summary}<button type="button" class="btn pri" data-ready="next"${ready.length && !done ? '' : ' disabled'}>${label}</button><small>${line}</small></div>`;
}

export function column(backlog, key, ctx) {
  const items = shownIn(backlog, key, ctx.filter);
  const lane = LANES.includes(key);
  const classes = `tcol${key === READY ? ' rdy' : ''}${lane ? ' lane' : ''}${lane && !items.length ? ' empty' : ''}`;
  const head = html`<div class="colh"><span class="dot" data-vars="${vars({ '--c': DOTS[key] })}"></span><h2>${name(key)}</h2><span class="c">${items.length}</span>${counts(items)}</div>`;
  const foot = key === READY ? readyFoot(ctx) : '';
  return html`<section class="${classes}" data-col="${key}" aria-label="${name(key)}">${head}${body(key, items, ctx)}${foot}</section>`;
}

// The central "Backlog" column: the rows P1 to P4, up is more urgent.
export function lanes(backlog, ctx) {
  return html`<div class="lanes"><div class="lanesh">${t('triage.backlog')} <span>${t('triage.urgent')}</span></div>${LANES.map((k) => column(backlog, k, ctx))}</div>`;
}
