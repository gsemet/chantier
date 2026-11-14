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

// A route of a project, relative to the page: `route('p', 'backlog/move')`.
export const route = (id, path) => `${base(id)}/${path}`;
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

// A text file: its text, whether the server cut it, and the SHA-256 of its bytes (an editor sends
// it back; the server leaves it out of a cut file).
export async function fileText(id, path) {
  const res = await fetch(`${base(id)}/file?${withPath(path)}`, OPTIONS);
  if (!res.ok) throw new AskError(res.status);
  return {
    text: await res.text(),
    cut: res.headers.get('X-Chantier-Cut') === '1',
    sha256: res.headers.get('X-Chantier-Sha256'),
  };
}

// Where a file is served from: an image's `src`, or a download link's `href`.
export const fileUrl = (id, path) => `${base(id)}/file?${withPath(path)}`;

// POST a JSON body to a route that may refuse (409) or fail (502): the answer comes back with its
// status and its JSON, never thrown.
export async function post(path, body = {}) {
  const res = await fetch(path, {
    ...OPTIONS,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

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

// A write: method is POST or PUT, body an object sent as JSON. It never throws on a refusal:
// the answer is { ok, status, data }, data the board's JSON (or null). Only a failure of the
// network throws. api/backlog.js turns a refusal into a BoardWriteError.
export async function send(method, path, body = {}) {
  const res = await fetch(path, {
    ...OPTIONS,
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  return { ok: res.ok, status: res.status, data };
}
