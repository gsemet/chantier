// The Configuration view: the roles of each host with their agent and model, editable in the
// planning surface's project file, and the rest of the configuration read-only. A change is judged
// by a dry run first (the server's answer shows the refusals), then written by Save.
//   render(state) returns the view's markup; mount(root, state) returns a cleanup.

import { changeConfig, readConfig } from '../api/config.js';
import { delegate, html } from '../core/dom.js';
import { paint } from '../core/paint.js';
import { snapshot } from '../core/store.js';
import { t } from '../model/words.js';
import { empty } from '../ui/parts.js';
import { tabAddress, tabOf, tabs, timingTab } from './config-timing.js';

const local = {
  project: null,
  view: null,
  pending: [],
  lines: [],
  saved: [],
  failed: false,
  tab: 'models',
};

const redraw = (root) => paint(root, render(snapshot()));

async function load(root, project) {
  local.project = project;
  try {
    local.view = await readConfig(project);
    local.failed = false;
  } catch {
    local.failed = true;
  }
  redraw(root);
}

const options = (host, row) => {
  const current = mine(row, 'model');
  const known = host.catalog.some((m) => m.id === current);
  const list = [...host.catalog.map((m) => ({ id: m.id, label: modelLabel(m) }))];
  if (current && !known) list.push({ id: current, label: current });
  return list;
};

const PLANS = {
  pro: 'Pro',
  pro_plus: 'Pro+',
  max: 'Max',
  business: 'Business',
  enterprise: 'Enterprise',
};

// The plans that include a model, from GitHub's table: plans is { pro: true, ... }, or null for
// a model the table does not list.
function plansOf(model) {
  if (!('plans' in model)) return '';
  if (!model.plans) return t('config.no_plans');
  return Object.entries(PLANS)
    .filter(([key]) => model.plans[key] !== false && model.plans[key] != null)
    .map(([key, name]) => (model.plans[key] === true ? name : `${name}: ${model.plans[key]}`))
    .join(', ');
}
function modelLabel(model) {
  const plans = plansOf(model);
  return `${model.id} (${model.name})${plans ? ` - ${plans}` : ''}`;
}

// What the planning surface's project file holds for a key; a held reset counts as nothing.
const mine = (row, key) => {
  const held = row[key].layers['surface project'];
  return held === 'reset' ? null : held;
};

const effective = (row, key) => {
  const value = row[key].effective;
  const text = (value && typeof value === 'object' ? value.id : value) ?? '-';
  const layer = row[key].layer;
  return layer ? t('config.in_layer', { value: text, layer }) : text;
};

// What the layers other than the project's own hold: the inherited value (the strongest weaker
// layer that sets one), greyed with its layer, and a reset wherever a layer holds one.
const WEAKER = ['defaults', 'surface'];
function inherited(row, key) {
  const layers = row[key].layers;
  const lines = [];
  const set = WEAKER.filter((l) => layers[l] && layers[l] !== 'reset').pop();
  if (set) lines.push(t('config.inherited_from', { value: layers[set], layer: set }));
  for (const [layer, held] of Object.entries(layers))
    if (held === 'reset') lines.push(t('config.reset', { layer }));
  return lines.map((l) => html`<div class="inh">${l}</div>`);
}

function modelCell(host, row, writable) {
  const value = mine(row, 'model') ?? '';
  const choices = options(host, row);
  const items = [
    html`<option value=""${value === '' ? ' selected' : ''}>${t('config.inherited')}</option>`,
    ...choices.map(
      (c) => html`<option value="${c.id}"${c.id === value ? ' selected' : ''}>${c.label}</option>`,
    ),
  ];
  return html`<select data-field data-key="model" ${writable ? '' : 'disabled'}>${items}</select>`;
}

function agentCell(row, writable) {
  const value = mine(row, 'agent') ?? '';
  return html`<input type="text" data-field data-key="agent" value="${value}" placeholder="${t('config.inherited')}" ${writable ? '' : 'disabled'} />`;
}

const startWord = (row) => (row.refusal ? row.refusal : t(`config.start_${row.start}`));

function roleRow(hostId, host, row, writable) {
  const over = row.overridden_by
    ? html`<div class="over">${t('config.overridden', { path: row.overridden_by })}</div>`
    : '';
  return html`<tr data-host="${hostId}" data-role="${row.role}"><td class="role">${row.role}</td><td>${agentCell(row, writable)}${inherited(row, 'agent')}<div class="eff">${t('config.effective')} ${effective(row, 'agent')}</div></td><td>${modelCell(host, row, writable)}${inherited(row, 'model')}<div class="eff">${t('config.effective')} ${effective(row, 'model')}</div>${over}</td><td class="start${row.refusal ? ' bad' : ''}">${startWord(row)}</td></tr>`;
}

function hostBlock(hostId, host, writable) {
  const rows = host.roles.map((r) => roleRow(hostId, host, r, writable));
  const note = t('config.cap', {
    answer: t(host.named_agent_model_at_start ? 'config.yes' : 'config.not_yet'),
  });
  const plans =
    hostId === 'copilot'
      ? html`<details class="catalog"><summary>${t('config.copilot_models')}</summary><ul>${host.catalog.map((m) => html`<li>${modelLabel(m)}</li>`)}</ul></details>`
      : '';
  return html`<section class="host"><h2>${host.name}</h2><div class="cap">${note}</div><div class="scroll"><table><thead><tr><th>${t('config.th_role')}</th><th>${t('config.th_agent')}</th><th>${t('config.th_model')}</th><th>${t('config.th_start')}</th></tr></thead><tbody>${rows}</tbody></table></div>${plans}</section>`;
}

function others(view) {
  if (!view.others.length) return '';
  const rows = view.others.map(
    (o) => html`<tr><td>${o.path}</td><td>${o.value}</td><td>${o.layer}</td></tr>`,
  );
  return html`<section class="others"><h2>${t('config.others')}</h2><table><tbody>${rows}</tbody></table></section>`;
}

function banner(view) {
  const lines = [];
  if (!view.writable) lines.push(html`<div class="note ro">${t('config.read_only')}</div>`);
  if (view.batch)
    lines.push(html`<div class="note">${t('config.next_batch', { batch: view.batch })}</div>`);
  for (const p of view.problems) lines.push(html`<div class="note bad">${p}</div>`);
  const files = view.files.map((f) => html`<li>${f.label}: ${f.path}</li>`);
  return html`${lines}<details class="files"><summary>${t('config.files')}</summary><ul>${files}</ul></details>`;
}

function actions() {
  const saved = local.saved.map((l) => html`<div class="note ok">${l}</div>`);
  const refused = local.lines.map((l) => html`<div class="note bad">${l}</div>`);
  const save = local.pending.length
    ? html`<div class="bar"><button class="btn pri" type="button" data-save>${t('config.save')}</button><button class="btn" type="button" data-cancel>${t('config.cancel')}</button></div>`
    : '';
  return html`${saved}${refused}${save}`;
}

export function render() {
  if (local.failed) return html`<div class="config">${empty(t('config.unreadable'))}</div>`;
  const view = local.view;
  if (!view) return html`<div class="config">${empty(t('stats.loading'))}</div>`;
  if (local.tab === 'timing')
    return html`<div class="config" data-key="config">${tabs(local.tab)}${banner(view)}${timingTab(view)}</div>`;
  const blocks = Object.entries(view.hosts).map(([id, host]) => hostBlock(id, host, view.writable));
  return html`<div class="config" data-key="config">${tabs(local.tab)}${banner(view)}${actions()}${blocks}${others(view)}</div>`;
}

// The answer of a refused write: the board's text, or its status when it said nothing.
const refusal = (res) => [res.data?.error ?? `the board answered ${res.status}`];

async function judge(root, change) {
  const base = local.view.sha256;
  const same = (c) => c.host === change.host && c.role === change.role && c.key === change.key;
  const next = [...local.pending.filter((c) => !same(c)), change];
  const res = await changeConfig(local.project, next, base, true);
  local.saved = [];
  if (res.ok && res.data?.ok) {
    local.view = { ...res.data.view, sha256: base };
    local.pending = next;
    local.lines = [];
  } else {
    local.lines = refusal(res);
    if (isStale(res)) {
      local.pending = [];
      local.view = await readConfig(local.project);
    }
  }
  redraw(root);
  if (!(res.ok && res.data?.ok)) showKept(root, change);
}

// A stale file is the server's marked refusal; any other refusal (problem lines) is not.
const isStale = (res) => !res.ok && res.status === 409 && res.data?.stale === true;

// After a refused edit the field shows the value the page still holds, not the refused one.
function showKept(root, change) {
  const row = local.view.hosts[change.host]?.roles.find((r) => r.role === change.role);
  const tr = [...root.querySelectorAll('tr[data-role]')].find(
    (r) => r.dataset.host === change.host && r.dataset.role === change.role,
  );
  const el = tr?.querySelector(`[data-key="${change.key}"]`);
  if (row && el) el.value = mine(row, change.key) ?? '';
}

async function save(root) {
  const res = await changeConfig(local.project, local.pending, local.view.sha256, false);
  const stale = isStale(res);
  const done = res.ok && res.data?.ok;
  if (done || stale) local.pending = [];
  local.lines = done ? [] : refusal(res);
  local.saved = done ? res.data.lines : [];
  if (done || stale) local.view = await readConfig(local.project);
  if (stale) local.saved = [];
  redraw(root);
}

function change(root, el) {
  const row = el.closest('tr');
  const value = el.value.trim();
  return judge(root, {
    host: row.dataset.host,
    role: row.dataset.role,
    key: el.dataset.key,
    value: value === '' ? null : value,
  });
}

export function mount(root, state) {
  local.pending = [];
  local.lines = [];
  local.saved = [];
  local.view = null;
  local.tab = tabOf(location.hash);
  load(root, state.project);
  const offs = [
    delegate(root, 'change', '[data-field]', (_, el) => change(root, el)),
    delegate(root, 'click', '[data-tab]', (_, el) => {
      local.tab = el.dataset.tab;
      history.replaceState(null, '', tabAddress(local.tab));
      redraw(root);
    }),
    delegate(root, 'click', '[data-save]', () => save(root)),
    delegate(root, 'click', '[data-cancel]', async () => {
      local.pending = [];
      local.lines = [];
      local.view = await readConfig(local.project);
      redraw(root);
    }),
  ];
  return () => {
    for (const off of offs) off();
  };
}
