// What chantier's words mean, in one place. Pure: no DOM, no fetch. Every view reads the meanings
// here and nowhere else (02-answers, "Semantics fixed"). A `batch` is the record's batch, its
// `crs` the rows of the batch; a `c` is one row.
import { t } from './words.js';

const CLOSED = ['merged', 'cancelled'];
export const STATE_ORDER = [
  'blocked',
  'working',
  'ready',
  'draft',
  'local',
  'waits',
  'queued',
  'merged',
];
export const HEARTBEAT_LATE_MIN = 15;
const MINUTE_MS = 60000;

export const isOpen = (c) => Boolean(c) && !CLOSED.includes(c.state);
export const isFix = (c) => c.kind === 'fix';
export const isRelease = (c) => c.kind === 'release';
export const crsOf = (batch) => batch?.crs ?? [];
export const byState = (batch, state) => crsOf(batch).filter((c) => c.state === state);

// A handed-back CR shows by the word the record derived: `ready` (ready to merge), `draft` (PR in
// draft; also a record with no word) or `local` (ready locally). A queued CR held by its
// dependencies shows as "waits"; any other keeps its own state.
const READY_STATE = { 'ready to merge': 'ready', 'PR in draft': 'draft', 'ready locally': 'local' };
const READY_WORDS = ['ready', 'draft', 'local'];
export function vstate(c) {
  if (c.state === 'ready') return READY_STATE[c.readiness] ?? 'draft';
  return c.state === 'queued' && c.waits?.length ? 'waits' : c.state;
}

export const defaultBranch = (batch) => batch?.default_branch || 'main';

// A CR's own round limit, else the batch's `max_rounds`, else none: never a fixed "/3".
export const roundLimit = (c, batch) => c.round_limit || batch?.max_rounds || null;

export function roundText(c, batch) {
  const limit = roundLimit(c, batch);
  return limit ? `${c.round}/${limit}` : String(c.round);
}

// The time a CR counts as merged: `merged_at` when the record has it, else `updated`.
export const mergedAt = (c) => c.merged_at || c.updated || null;

// The stack or the series, bottom first: the open CRs but a fix, by order, the release on top.
export function chain(batch) {
  const rank = (c) => Number(isRelease(c));
  return crsOf(batch)
    .filter((c) => isOpen(c) && !isFix(c))
    .sort((a, b) => rank(a) - rank(b) || (a.order ?? 0) - (b.order ?? 0));
}

// A CR's open dependencies: the CRs of its fter that are not merged or cancelled.
export const openAfter = (c, batch) => {
  const rows = crsOf(batch);
  return (c.after ?? []).map((id) => rows.find((x) => x.cr === id)).filter(isOpen);
};

const lastOpenDependency = (c, batch) => openAfter(c, batch).at(-1) ?? null;

// Where a CR's PR sits: `{ on, text }`, the branch or CR it is based on and the words for it.
export function baseOf(c, batch) {
  const def = defaultBranch(batch);
  if (isFix(c)) return { on: def, text: t('base.fix', { branch: def }) };
  const list = chain(batch);
  const place = list.findIndex((x) => x.cr === c.cr);
  const under = place > 0 ? list[place - 1].cr : null;
  if (batch.mode === 'stack' && c.stacked) {
    return under
      ? { on: under, text: t('base.on', { branch: under }) }
      : { on: def, text: t('base.bottom', { branch: def }) };
  }
  if (batch.mode === 'series' && under) return { on: under, text: t('base.series', { cr: under }) };
  const dep = lastOpenDependency(c, batch);
  const base = dep
    ? { on: dep.cr, text: t('base.dependency', { cr: dep.cr }) }
    : { on: def, text: t('base.on', { branch: def }) };
  if (batch.mode === 'stack') base.text += t('base.not_stacked');
  return base;
}

// To review: ready to merge, the word the record derives (the PR is out of draft on the forge and
// everything under it is ready to merge too).
export const toReview = (c) => vstate(c) === 'ready';

// The open CRs with a PR, in the order their PRs are merged. A stack or a series: the chain, a
// fix apart. A parallel batch: the order the CRs were handed back, the release last.
export function mergeOrder(batch) {
  const open = crsOf(batch).filter((c) => c.pr && isOpen(c));
  const rank = (c) => Number(isRelease(c));
  if (batch.mode === 'parallel') {
    const when = (c) => c.handed_back_at || c.updated || '';
    return open.sort((a, b) => rank(a) - rank(b) || when(a).localeCompare(when(b)));
  }
  const apart = (c) => Number(isFix(c));
  return open.sort(
    (a, b) => apart(a) - apart(b) || rank(a) - rank(b) || (a.order ?? 0) - (b.order ?? 0),
  );
}

// The two PR lists, each in the order the page reads it (a stack reads from its top PR).
export function prLists(batch) {
  const all = mergeOrder(batch);
  const read = (list) => (batch.mode === 'stack' ? [...list].reverse() : list);
  return {
    review: read(all.filter((c) => toReview(c))),
    drafts: read(all.filter((c) => !toReview(c))),
  };
}

// A PR's place: its number in the stack ("top" on the highest), or its place in the merge order.
export function placeOf(c, batch, index) {
  if (batch.mode === 'stack' && !isFix(c)) {
    const list = chain(batch);
    const k = list.findIndex((x) => x.cr === c.cr);
    return k < 0 ? null : { n: k + 1, top: k === list.length - 1, kind: 'stack' };
  }
  return { n: index + 1, top: false, kind: 'order' };
}

// Why a PR is not to review yet.
export const draftWhy = (c) => (vstate(c) === 'draft' ? t('pr.draft') : t(`state.${vstate(c)}`));

// The CRs in levels: a CR is one level above the highest of its dependencies in the batch; a
// cycle counts as level 0.
export function levels(rows) {
  const found = new Map(rows.map((c) => [c.cr, c]));
  const level = new Map();
  const walking = new Set();
  const of = (id) => {
    if (level.has(id)) return level.get(id);
    if (walking.has(id)) return 0;
    walking.add(id);
    const deps = (found.get(id)?.after ?? []).filter((d) => found.has(d));
    const value = deps.length ? 1 + Math.max(...deps.map(of)) : 0;
    level.set(id, value);
    return value;
  };
  const cols = [];
  for (const c of rows) {
    const at = of(c.cr);
    cols[at] = [...(cols[at] ?? []), c];
  }
  return cols;
}

// A level's CRs grouped by state, in the graph's order; empty groups left out.
export const groupByState = (rows) =>
  STATE_ORDER.map((state) => ({ state, rows: rows.filter((c) => vstate(c) === state) })).filter(
    (g) => g.rows.length,
  );

// A CR, its dependencies and its dependants: what a hover lights.
export function related(rows, id) {
  const ids = new Set([id]);
  for (const c of rows) {
    if (c.cr === id) for (const d of c.after ?? []) ids.add(d);
    if ((c.after ?? []).includes(id)) ids.add(c.cr);
  }
  return ids;
}

// The CRs and counts the Home and Batch figures need.
export function counts(batch) {
  const n = (state) =>
    crsOf(batch).filter((c) => (READY_WORDS.includes(state) ? vstate(c) : c.state) === state)
      .length;
  const review = crsOf(batch).filter((c) => toReview(c)).length;
  return {
    total: crsOf(batch).length,
    review,
    ...Object.fromEntries(STATE_ORDER.map((s) => [s, n(s)])),
    queued: crsOf(batch).filter((c) => c.state === 'queued').length,
  };
}

// "Waiting for you": every blocked CR plus the unread asks.
export const waitingForYou = (batch) =>
  byState(batch, 'blocked').length + (batch?.asks_unread ?? 0);

// The heartbeat: `stopped`, else the minutes since it, and whether that is late.
export function heartbeat(batch, nowIso) {
  if (batch.heartbeat_stopped) return { stopped: true, minutes: null, late: false };
  if (!batch.heartbeat || !nowIso) return { stopped: false, minutes: null, late: false };
  const minutes = Math.max(
    0,
    Math.round((Date.parse(nowIso) - Date.parse(batch.heartbeat)) / MINUTE_MS),
  );
  return { stopped: false, minutes, late: minutes > HEARTBEAT_LATE_MIN };
}

// Who steers: the Foreman, or the Chief of Staff when the batch is direct.
export const steeringWord = (batch) =>
  batch.steering === 'direct' ? t('steering.direct') : t('steering.foreman');

// The mode's words: its name and its sentence.
export const modeWords = (mode) => ({ name: t(`mode.${mode}`), text: t(`mode.${mode}.text`) });

// The hint over the PRs to review, by mode and by whether the whole stack is ready to merge.
export function reviewHint(batch) {
  if (batch.mode === 'stack') {
    const whole = chain(batch).length > 0 && chain(batch).every(toReview);
    return t(whole ? 'prs.hint_stack_ok' : 'prs.hint_stack_no');
  }
  if (batch.mode === 'series') return t('prs.hint_series', { branch: defaultBranch(batch) });
  return t('prs.hint_parallel');
}
