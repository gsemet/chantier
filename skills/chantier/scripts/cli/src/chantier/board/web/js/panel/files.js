// How the panel treats a file of a folder: how it is shown, which file opens first, which icon it
// has. Pure: no DOM and no fetch. The size rule below is the panel's only one.

// The size rule. The server sends a text file cut at 1,000,000 bytes (header `X-Chantier-Cut`)
// and an image only up to 5,000,000. A text file above the first limit (the prototype's `data.js`
// is 1.5 MB) is listed by its size and never fetched as text: the page would draw a megabyte of
// a file nobody reads, and it would be cut. An image above the second limit is not an image for
// the server either, so it is listed as any other file.
export const TEXT_LIMIT = 1_000_000;
export const IMAGE_LIMIT = 5_000_000;

const FIRST = ['03-change-spec.md', '01-intent.md', 'STATUS.md'];

// The kinds fetched as text when a file is opened.
export const FETCHED = new Set(['markdown', 'json', 'text']);

const extOf = (path) => (/\.[^./]+$/.exec(path)?.[0] ?? '').toLowerCase();

// How a file of the listing is shown: markdown, json, text, image, large or other.
export function viewKind(file) {
  if (file.kind === 'image') return file.size <= IMAGE_LIMIT ? 'image' : 'other';
  if (file.kind !== 'text') return 'other';
  if (file.size > TEXT_LIMIT) return 'large';
  const ext = extOf(file.path);
  if (ext === '.md') return 'markdown';
  return ext === '.json' ? 'json' : 'text';
}

// The file opened first: the specification, else the intent, else STATUS.md, else the first
// Markdown file, else the first file.
export function firstFile(list) {
  const named = FIRST.map((name) => list.find((f) => f.rel === name)).find(Boolean);
  return named ?? list.find((f) => extOf(f.rel) === '.md') ?? list[0] ?? null;
}

// The icon of a file in the tree: text, image, other.
export function iconOf(file) {
  const kind = viewKind(file);
  if (kind === 'image') return 'img';
  return FETCHED.has(kind) ? 'file' : 'blank';
}
