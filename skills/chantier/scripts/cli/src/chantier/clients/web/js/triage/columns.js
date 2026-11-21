// The columns of Triage: the Inbox, the Backlog column with its rows P1 to P4, and the last column
// with its two halves (running batch over next batch, 3-ready with its foot), all built by ui/column.js. A group is a dashed frame with its handle, its count and "undo", before the loose post-its.
// Pure: markup from the record and a context (see postit.js), nothing bound here.
import { html } from '../core/dom.js';
import {
  DOTS,
  groupsIn,
  LANES,
  openBatch,
  pendingCrs,
  READY,
  RUNNING,
  readyCounts,
  runningItems,
  shownIn,
  stateCounts,
} from '../model/triage.js';
import { t } from '../model/words.js';
import { card } from '../ui/card.js';
import { column as column_, lane } from '../ui/column.js';
import { priorityChip } from '../ui/parts.js';
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

// What a column or a lane holds: the groups, the loose post-its and the drop zone.
// `more` is markup that follows the post-its (the running batch's pending cards).
function body(column, items, ctx, more = []) {
  const { groups, loose } = groupsIn(items);
  const empty = !items.length && !more.length;
  const drop = empty ? t(LANES.includes(column) ? 'triage.empty_row' : 'triage.drop') : '';
  return html`${groups.map((g) => frame(g, ctx))}${loose.map((i) => postit(i, ctx))}${more}<div class="dropzone">${drop}</div>`;
}

// The foot of 3-ready: the counts and the button.
function readyFoot(ctx) {
  const ready = ctx.ready;
  const { auto, specified } = readyCounts(ready);
  const done = ctx.indicator.kind === 'declared';
  const summary = ready.length
    ? html`<small>${t('triage.ready_counts', { specified, auto })}</small>`
    : '';
  const label = done ? t('triage.declared') : t('triage.declare');
  return html`<div class="rfoot">${summary}<button type="button" class="btn pri" data-ready="next"${ready.length && !done ? '' : ' disabled'}>${label}</button></div>`;
}

// The Inbox, one column.
export function column(backlog, key, base) {
  const ctx = { ...base, column: key };
  const items = shownIn(backlog, key, ctx.filter);
  return column_({
    drop: key,
    label: name(key),
    name: name(key),
    color: DOTS[key],
    count: items.length,
    states: counts(items),
    sub: t('triage.inbox_sub'),
    body: body(key, items, ctx),
  });
}

// A CR of the open batch waiting for a slot: a plain card, neither draggable nor selectable.
function pending(c) {
  return card({
    attrs: html`data-key="pend-${c.cr}" aria-label="${c.cr}, ${c.title ?? ''}"`,
    top: html`<span class="tag cr">${c.cr}</span><span class="lbl">${c.folder ?? ''}</span>`,
    title: c.title ?? '',
    meta: html`<span>${t('triage.state_queued')}</span>`,
  });
}

// The last column's top half: the CRs marked for the open batch, then the batch's pending CRs;
// greyed, with no card, when no batch is open. It is a drop target all the same.
function runningHalf(backlog, base) {
  const ctx = { ...base, column: RUNNING };
  const batch = openBatch(ctx.batch);
  const marked = batch ? runningItems(backlog, ctx.filter) : [];
  const waiting = batch ? pendingCrs(batch) : [];
  return lane({
    drop: RUNNING,
    label: t('triage.lane_running'),
    name: t('triage.lane_running'),
    count: marked.length + waiting.length,
    states: counts(marked),
    sub: batch
      ? t('triage.running_lane', { batch: batch.id, state: batch.state })
      : t('triage.no_running'),
    body: body(RUNNING, marked, ctx, waiting.map(pending)),
    idle: !batch,
  });
}

// The last column's bottom half: 3-ready, "Next batch", with its counts and its foot.
function nextHalf(backlog, base) {
  const ctx = { ...base, column: READY };
  const items = shownIn(backlog, READY, ctx.filter);
  return lane({
    drop: READY,
    label: t('triage.lane_next'),
    name: t('triage.lane_next'),
    count: items.length,
    states: counts(items),
    sub: t('kanban.ready_sub'),
    body: body(READY, items, ctx),
    foot: readyFoot(ctx),
  });
}

// The last column: one column, two named halves, running batch over next batch, always drawn.
export function last(backlog, ctx) {
  return column_({
    key: 'tri-last',
    label: `${t('triage.lane_running')} / ${t('triage.lane_next')}`,
    body: html`${runningHalf(backlog, ctx)}${nextHalf(backlog, ctx)}`,
  });
}

// A lane of the Backlog column: its priority chip, its counts, its post-its.
function laneOf(backlog, key, base) {
  const ctx = { ...base, column: key };
  const items = shownIn(backlog, key, ctx.filter);
  return lane({
    drop: key,
    label: key,
    chip: priorityChip(key),
    count: items.length,
    states: counts(items),
    body: body(key, items, ctx),
    empty: !items.length,
  });
}

// The central "Backlog" column: one column, the rows P1 to P4 in its body, up is more urgent.
export function lanes(backlog, ctx) {
  return column_({
    label: t('triage.backlog'),
    name: t('triage.backlog'),
    color: DOTS.backlog,
    hint: t('triage.urgent'),
    sub: t('triage.backlog_sub'),
    body: html`${LANES.map((k) => laneOf(backlog, k, ctx))}`,
  });
}
