// The folder's listing as a tree: its own files first, then one heading per first-level
// sub-folder with its files under it. A deeper file sits under its first-level heading, named by
// the rest of its path.
import { html } from '../core/dom.js';
import { size } from '../core/format.js';
import { t } from '../model/words.js';
import { icon } from '../ui/icons.js';
import { iconOf } from './files.js';

// The server lists paths from the planning folder; an entry also knows its path from the open
// folder (`rel`), its first-level folder (`dir`, empty for an own file) and its shown `name`.
export function entries(folder, files) {
  const prefix = folder ? `${folder}/` : '';
  return files.map((f) => {
    const rel = f.path.startsWith(prefix) ? f.path.slice(prefix.length) : f.path;
    const at = rel.indexOf('/');
    return {
      path: f.path,
      size: f.size,
      kind: f.kind,
      rel,
      dir: at < 0 ? '' : rel.slice(0, at),
      name: at < 0 ? rel : rel.slice(at + 1),
    };
  });
}

// The own files, then the sub-folders by name.
export function groups(list) {
  const dirs = new Map();
  for (const file of list.filter((f) => f.dir)) {
    dirs.set(file.dir, [...(dirs.get(file.dir) ?? []), file]);
  }
  const names = [...dirs.keys()].sort();
  return {
    own: list.filter((f) => !f.dir),
    dirs: names.map((name) => ({ name, files: dirs.get(name) })),
  };
}

const button = (file, open) =>
  html`<button type="button" class="${file.dir ? 'ind' : ''}${file.path === open ? ' on' : ''}" data-file="${file.path}" data-key="file-${file.path}"${file.path === open ? html` aria-current="true"` : ''}><span class="ic">${icon(iconOf(file))}</span><span class="nm">${file.name}</span><span class="sz">${size(file.size)}</span></button>`;

const section = (dir, open) =>
  html`<div class="dir">${dir.name}/ · ${dir.files.length}</div>${dir.files.map((f) => button(f, open))}`;

// The tree's markup: while the listing is loading `list` is null.
export function treeMarkup(list, open, failed) {
  if (failed) return html`<div class="empty">${t('panel.error')}</div>`;
  if (!list) return html`<div class="empty">${t('stats.loading')}</div>`;
  if (!list.length) return html`<div class="empty">${t('panel.empty')}</div>`;
  const { own, dirs } = groups(list);
  return html`${own.map((f) => button(f, open))}${dirs.map((d) => section(d, open))}`;
}
