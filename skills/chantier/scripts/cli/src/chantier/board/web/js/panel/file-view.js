// The file view: a line with the file's path and size, then the file by its kind. Markdown is
// rendered, JSON pretty-printed, an image drawn from the server, other text put in a `pre`. Any
// other file is listed with its size and a download link. Every text is escaped by `html`; an SVG
// or an HTML file is never a document of the page (the server sends the first as a download and
// the second as plain text), and the page builds no `data:` or `blob:` address.
import { fileUrl } from '../core/api.js';
import { html } from '../core/dom.js';
import { size } from '../core/format.js';
import { t } from '../model/words.js';
import { renderMarkdown } from './markdown.js';

// JSON, indented; text that does not parse stays as it is.
function pretty(text) {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

const note = (text) => html`<p class="info">${text}</p>`;

const download = (project, file) =>
  html`<a class="btn" href="${fileUrl(project, file.path)}" download>${t('panel.download')}</a>`;

// The body of an opened file, by how it is shown.
function bodyOf(project, entry, file) {
  const shown = size(entry.size);
  if (file.failed) return note(t('panel.error'));
  switch (file.kind) {
    case 'image':
      return html`<img src="${fileUrl(project, entry.path)}" alt="${entry.rel}" />`;
    case 'large':
      return note(t('panel.large', { name: entry.rel, size: shown }));
    case 'other':
      return html`${note(t('panel.other', { name: entry.rel, size: shown }))}${download(project, entry)}`;
    default:
      break;
  }
  if (file.loading || file.text == null) return note(t('stats.loading'));
  if (file.kind === 'markdown') return renderMarkdown(file.text);
  const text = file.kind === 'json' ? pretty(file.text) : file.text;
  return html`<pre><code>${text}</code></pre>`;
}

// The view of the open file, or nothing to show while no file is chosen.
export function fileView(project, folder, list, file) {
  const entry = list?.find((f) => f.path === file?.path);
  if (!entry) return html`<div class="info">${list ? '' : t('stats.loading')}</div>`;
  const cut = file.cut ? ` ${t('panel.cut')}` : '';
  return html`<div class="info">${folder}/${entry.rel} · ${size(entry.size)}${cut}</div>${bodyOf(project, entry, file)}`;
}
