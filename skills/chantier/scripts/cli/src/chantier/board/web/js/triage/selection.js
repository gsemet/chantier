// The selection and its bottom bar. A click or a tap on a post-it (not on its "open" button), or
// Space or Enter on a focused one, toggles it. The bar sends the selection to a column, groups it,
// labels it or opens it. It is how a phone moves things, since touch fires no HTML5 drag.
import { addLabel } from '../api/backlog.js';
import { delegate, html } from '../core/dom.js';
import { snapshot, update } from '../core/store.js';
import { targetFor } from '../model/targets.js';
import { COLUMNS, findItem, labelsOf, passes } from '../model/triage.js';
import { t } from '../model/words.js';
import { openPanel } from '../panel/panel.js';
import { showDialog } from '../ui/dialog.js';
import { clearSelection, run } from './actions.js';
import { createGroup } from './groups.js';
import { moveTo } from './move.js';

const name = (column) => (column === 'inbox' ? t('priority.inbox') : column);

export function selectionBar(selected) {
  if (!selected.length) return '';
  const sends = COLUMNS.map(
    (c) => html`<button type="button" data-to="${c}">→ ${name(c)}</button>`,
  );
  const group =
    selected.length > 1
      ? html`<button type="button" data-act="group">${t('sel.group')}</button>`
      : '';
  const open =
    selected.length === 1
      ? html`<button type="button" data-act="open">${t('sel.open')}</button>`
      : '';
  return html`<div class="selbar" role="toolbar" aria-label="${t('sel.bar')}"><span class="n">${t('sel.count', { n: selected.length })}</span>${sends}${group}<button type="button" data-act="label">${t('sel.label')}</button>${open}<button type="button" data-act="clear" aria-label="${t('sel.clear')}">✕</button></div>`;
}

function toggle(slug) {
  const now = snapshot().selection;
  update({ selection: now.includes(slug) ? now.filter((s) => s !== slug) : [...now, slug] });
}

async function label(slugs) {
  const { data, project } = snapshot();
  const asked = await showDialog({
    title: t('label.title'),
    note: t('label.note'),
    confirm: t('label.confirm'),
    fields: [
      { name: 'label', label: t('label.name'), value: '', choices: labelsOf(data?.backlog) },
    ],
  });
  const word = asked?.label.trim().toLowerCase();
  if (!word) return;
  const done = await run(slugs, () => addLabel(project, slugs, word));
  if (done) clearSelection();
}

function act(action, slugs) {
  const state = snapshot();
  if (action === 'clear') clearSelection();
  if (action === 'group') createGroup(slugs);
  if (action === 'label') label(slugs);
  if (action === 'open') {
    const target = targetFor(state, `i:${slugs[0]}`);
    if (target) openPanel(state, target);
  }
}

// The selection as the record now holds it: a slug that left the backlog drops out.
export const selectedNow = (state) =>
  state.selection.filter((s) => {
    const item = findItem(state.data?.backlog, s);
    return item && passes(item, state.labelFilter);
  });

export function bindSelection(root) {
  const offs = [
    delegate(root, 'click', '.pi', (event, pi) => {
      if (!event.target.closest('[data-open]')) toggle(pi.dataset.slug);
    }),
    delegate(root, 'keydown', '.pi', (event, pi) => {
      const key = event.key === 'Enter' || event.key === ' ';
      if (!key || event.target !== pi) return;
      event.preventDefault();
      toggle(pi.dataset.slug);
    }),
    delegate(root, 'click', '[data-to]', async (_, b) => {
      const slugs = selectedNow(snapshot());
      if (await moveTo(slugs, b.dataset.to)) clearSelection(slugs);
    }),
    delegate(root, 'click', '[data-act]', (_, b) => act(b.dataset.act, selectedNow(snapshot()))),
  ];
  return () => {
    for (const off of offs) off();
  };
}
