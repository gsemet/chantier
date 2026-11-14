// Every request the page makes: the only module that calls `fetch`. The key is in the cookie:
// nothing here sends or reads it. Every path is relative to the page, so the board's own address
// is kept on every request.

export class AskError extends Error {
  constructor(status) {
    super(`the board answered ${status}`);
    this.status = status;
  }
}

const base = (id) => `api/projects/${encodeURIComponent(id)}`;
const withPath = (path) => `path=${encodeURIComponent(path)}`;
const OPTIONS = { cache: 'no-store', credentials: 'same-origin' };

// GET a JSON route. With the last ETag, a 304 comes back as `{ changed: false }`.
export async function get(path, etag = null) {
  const headers = etag ? { 'If-None-Match': etag } : {};
  const res = await fetch(path, { ...OPTIONS, headers });
  const now = res.headers.get('X-Chantier-Now');
  if (res.status === 304) return { changed: false, etag, now };
  if (!res.ok) throw new AskError(res.status);
  return { changed: true, etag: res.headers.get('ETag'), now, data: await res.json() };
}

export const board = () => get('api/board');

export const projectState = (id, etag) => get(`${base(id)}/state`, etag);

export const costs = (id) => get(`${base(id)}/costs`);

export const tree = (id, path) => get(`${base(id)}/tree?${withPath(path)}`);

// A text file: its text, and whether the server cut it.
export async function fileText(id, path) {
  const res = await fetch(`${base(id)}/file?${withPath(path)}`, OPTIONS);
  if (!res.ok) throw new AskError(res.status);
  return { text: await res.text(), cut: res.headers.get('X-Chantier-Cut') === '1' };
}

// Where a file is served from: an image's `src`, or a download link's `href`.
export const fileUrl = (id, path) => `${base(id)}/file?${withPath(path)}`;

// Ask the server to read the transcripts again. It answers at once; the figure arrives with
// the next `costs` read.
export async function recompute(id) {
  const res = await fetch(`${base(id)}/costs/recompute`, {
    ...OPTIONS,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  });
  if (!res.ok) throw new AskError(res.status);
  return res.json();
}
