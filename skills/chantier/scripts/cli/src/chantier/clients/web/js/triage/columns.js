// The columns of Triage: the Inbox, the Backlog column with its rows P1 to P4, and 3-ready with its
// foot, all built by ui/column.js. A group is a dashed frame with its handle, its count and "undo", before the loose post-its.
// Pure: markup from the record and a context (see postit.js), nothing bound here.
import { html } from '../core/dom.js';
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
function body(column, items, ctx) {
  const { groups, loose } = groupsIn(items);
  const drop = items.length ? '' : t(LANES.includes(column) ? 'triage.empty_row' : 'triage.drop');
  return html`${groups.map((g) => frame(g, ctx))}${loose.map((i) => postit(i, ctx))}<div class="dropzone">${drop}</div>`;
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

// The Inbox and 3-ready, one column each (the latter with its foot).
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
    sub: t(key === READY ? 'kanban.ready_sub' : 'triage.inbox_sub'),
    body: body(key, items, ctx),
    foot: key === READY ? readyFoot(ctx) : '',
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
