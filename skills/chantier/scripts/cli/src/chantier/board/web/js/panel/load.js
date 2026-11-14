// What the panel reads, and when: the folder's listing when the panel opens (and again when the
// folder's file count changes), and a file's text only when that file is opened. A late answer
// for a panel or a file that is no longer the open one is dropped.
import { fileText, tree } from '../core/api.js';
import { snapshot, update } from '../core/store.js';
import { FETCHED, firstFile, viewKind } from './files.js';
import { entries } from './tree.js';

const stillOpen = (key) => snapshot().panel?.key === key;

// Open a file of the listing: set it as the open one and, for a text kind, read it.
export async function loadFile(key, entry) {
  if (!entry) return;
  const project = snapshot().panel.project;
  const kind = viewKind(entry);
  const base = { path: entry.path, kind, text: null, cut: false, failed: false };
  const fetched = FETCHED.has(kind);
  update({ panelFile: { ...base, loading: fetched } });
  if (!fetched) return;
  try {
    const got = await fileText(project, entry.path);
    if (!stillOpen(key) || snapshot().panelFile?.path !== entry.path) return;
    update({ panelFile: { ...base, loading: false, text: got.text, cut: got.cut } });
  } catch {
    if (stillOpen(key) && snapshot().panelFile?.path === entry.path) {
      update({ panelFile: { ...base, loading: false, failed: true } });
    }
  }
}

// Read the folder's listing. The first time, the first file is opened as well.
export async function loadTree(target, keepFile = false) {
  const { key, folder, project } = target;
  const mark = { folder, count: target.files };
  update({
    panelTree: { ...mark, list: null, failed: false },
    ...(keepFile ? {} : { panelFile: null }),
  });
  try {
    const got = await tree(project, folder);
    if (!stillOpen(key)) return;
    const list = entries(folder, got.data.files);
    update({ panelTree: { ...mark, list, failed: false } });
    if (!snapshot().panelFile) await loadFile(key, firstFile(list));
  } catch {
    if (stillOpen(key)) update({ panelTree: { ...mark, list: null, failed: true } });
  }
}
