// The Markdown editor of the file panel, for the Markdown files of a backlog item (not STATUS.md).
// "Edit" puts a text area in place of the rendered text; "Save" (or Ctrl/Cmd+S) sends the text with
// the SHA-256 the file had when it was loaded, so a file changed meanwhile is refused, not
// overwritten. The text area is built once and kept: a redraw of the panel (a live refresh) puts
// it back in its place, with what was typed and the caret.
import { BoardWriteError, saveFile } from '../api/backlog.js';
import { $, delegate, html, setHtml } from '../core/dom.js';
import { snapshot, update } from '../core/store.js';
import { loadJournal } from '../journal/journal.js';
import { t } from '../model/words.js';
import { loadFile } from '../panel/load.js';
import { confirmDialog } from '../ui/dialog.js';
import { toast, written } from '../ui/toast.js';

let box = null; // the editor's element, kept between redraws of the panel
let wantsFocus = false;

const field = () => $('textarea', box);

const unix = (text) => (text ?? '').replace(/\r\n?/g, '\n');

// Whether the typed text differs from what was loaded.
export const dirty = () => {
  const editing = snapshot().editing;
  return Boolean(editing && box && field().value !== unix(editing.original));
};

// A Markdown file of a backlog item, other than STATUS.md, read whole.
export function canEdit(target, file) {
  return (
    target?.kind === 'item' &&
    file?.kind === 'markdown' &&
    file.rel !== 'STATUS.md' &&
    file.text != null &&
    !file.cut &&
    Boolean(file.sha256)
  );
}

export const isEditing = (state, file) => state.editing?.path === file?.path;

export const editButton = () =>
  html`<button type="button" class="btn small" data-edit="start" data-key="edit-start">${t('edit.edit')}</button>`;

// The empty place the editor is put in.
export const editorPlace = () => html`<div class="editor" data-editor></div>`;

function build(editing) {
  box = document.createElement('div');
  box.className = 'editbox';
  setHtml(
    box,
    html`<div class="ebar"><button type="button" class="btn pri" data-edit="save">${t('edit.save')}</button><button type="button" class="btn" data-edit="cancel">${t('edit.cancel')}</button><span class="ehint">${t('edit.hint')}</span><span class="emsg" role="alert" hidden></span></div><textarea class="etext" spellcheck="false" aria-label="${t('edit.area')}"></textarea>`,
  );
  field().value = unix(editing.original);
  box.addEventListener('focusin', () => {
    wantsFocus = true;
  });
  box.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault();
      save();
    }
  });
}

function show(message) {
  const line = $('.emsg', box);
  line.textContent = message ?? '';
  line.hidden = !message;
}

// Called after every draw of the panel: put the editor in its place, or let it go.
export function syncEditor(root, state) {
  const place = $('[data-editor]', root);
  if (!state.editing || !place) {
    box = null;
    return;
  }
  if (!box) build(state.editing);
  $('[data-edit="save"]', box).disabled = state.editing.saving;
  show(state.editing.error);
  if (box.parentNode === place) return;
  place.append(box);
  if (wantsFocus) field().focus({ preventScroll: true });
}

export function startEdit() {
  const { panelFile: file } = snapshot();
  if (!file || file.text == null) return;
  box = null;
  wantsFocus = true;
  update({
    editing: {
      path: file.path,
      original: file.text,
      base: file.sha256,
      saving: false,
      error: null,
    },
  });
}

async function save() {
  const state = snapshot();
  const { editing, panel } = state;
  if (!editing || editing.saving) return;
  update({ editing: { ...editing, saving: true, error: null } });
  const file = state.panelFile;
  try {
    const answer = await saveFile(panel.project, {
      item: panel.row.item,
      path: file.rel,
      text: field().value,
      base: editing.base,
    });
    written(answer.journal.map((e) => e.text).join('; '));
    update({ editing: null });
    const entry = snapshot().panelTree?.list?.find((f) => f.path === file.path);
    await loadFile(panel.key, entry);
    loadJournal();
  } catch (error) {
    const message = error instanceof BoardWriteError ? error.message : t('toast.network');
    update({ editing: { ...snapshot().editing, saving: false, error: message } });
    toast(message, { error: true });
  }
}

// Leave the editor: true when there is nothing to lose or the user agreed to lose it.
export async function confirmLeave() {
  if (!snapshot().editing) return true;
  if (dirty()) {
    const ok = await confirmDialog({
      title: t('edit.leave_title'),
      note: t('edit.leave'),
      confirm: t('edit.discard'),
    });
    if (!ok) return false;
  }
  update({ editing: null });
  return true;
}

export function bindEditor(root) {
  const offs = [
    delegate(root, 'click', '[data-edit]', async (_, button) => {
      const what = button.dataset.edit;
      if (what === 'start') startEdit();
      if (what === 'save') save();
      if (what === 'cancel') await confirmLeave();
    }),
  ];
  const leaving = (event) => {
    if (dirty()) event.preventDefault();
  };
  const away = (event) => {
    wantsFocus = Boolean(box?.contains(event.target));
  };
  window.addEventListener('beforeunload', leaving);
  document.addEventListener('pointerdown', away);
  return () => {
    for (const off of offs) off();
    window.removeEventListener('beforeunload', leaving);
    document.removeEventListener('pointerdown', away);
  };
}
