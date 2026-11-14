// The CR's file panel. The contract the views use: `openPanel(state, target)` opens the folder of
// a target (see model/targets.js) and `closePanel()` closes it. The panel is a head, the folder's
// tree and the file view. The page draws it from the store (`panel`, `panelTree`, `panelFile`), so
// a live refresh redraws it in place and it stays on its file.
import { $, delegate, html } from '../core/dom.js';
import { snapshot, update } from '../core/store.js';
import { bindEditor, confirmLeave, syncEditor } from '../edit/markdown-editor.js';
import { targetFor } from '../model/targets.js';
import { t } from '../model/words.js';
import { fileView } from './file-view.js';
import { head } from './head.js';
import { loadFile, loadTree } from './load.js';
import { treeMarkup } from './tree.js';

let openerKey = null; // the `data-key` of the element that opened the panel: it gets the focus back
let shownKey = null; // the key of the panel the focus was last moved for

export function openPanel(state, target) {
  openerKey = document.activeElement?.dataset?.key ?? null;
  update({
    panel: { ...target, project: state.project },
    panelTree: null,
    panelFile: null,
    editing: null,
  });
}

export const closePanel = () =>
  update({ panel: null, panelTree: null, panelFile: null, editing: null });

// The target as the data now says it (a live refresh moves a CR's round or cost); as it was opened
// when the record no longer holds it.
const current = (state) => ({ ...state.panel, ...targetFor(state, state.panel.key) });

// What the panel holds for the state: nothing while it is closed.
export function panelMarkup(state) {
  if (!state.panel) return '';
  const target = current(state);
  const { panelTree: tree, panelFile: file } = state;
  const list = tree?.list ?? null;
  const open = file ? `doc:${file.path}` : 'doc';
  return html`${head(target, state.data?.batch, list?.length ?? target.files ?? 0)}<div class="pbody"><nav class="tree" data-scroll="tree" aria-label="${t('panel.tree')}">${treeMarkup(list, file?.path, tree?.failed)}</nav><div class="doc" data-scroll="${open}" tabindex="0" role="region" aria-label="${t('panel.doc')}">${fileView(target, list, file, state.editing)}</div></div>`;
}

// Read what the open panel needs and does not have: its listing, again when the folder's file
// count moved. Called after every draw; a read already asked is not asked twice.
export function syncPanel(state) {
  if (!state.panel) return;
  if (state.panel.project !== state.project) {
    closePanel();
    return;
  }
  const target = current(state);
  const loaded = state.panelTree;
  const same = loaded?.folder === target.folder;
  if (!loaded || !same || (loaded.list && loaded.count !== target.files)) {
    loadTree(target, same);
  }
}

// The focus goes into the panel when it opens and back to what opened it when it closes.
export function afterPanel(root, state) {
  syncEditor(root, state);
  const key = state.panel?.key ?? null;
  if (key === shownKey) return;
  shownKey = key;
  const target = key
    ? $('[data-close]', root)
    : openerKey && $(`[data-key="${CSS.escape(openerKey)}"]`);
  target?.focus({ preventScroll: true });
}

// A click on a file of the tree opens it (after asking, when an edit would be lost); the editor's
// own buttons are bound here too.
export function bindPanel(root) {
  const offs = [
    bindEditor(root),
    delegate(root, 'click', '[data-file]', async (_, button) => {
      if (!(await confirmLeave())) return;
      const { panel, panelTree: tree } = snapshot();
      const entry = tree?.list?.find((f) => f.path === button.dataset.file);
      if (panel && entry) loadFile(panel.key, entry);
    }),
  ];
  return () => {
    for (const off of offs) off();
  };
}
