// Every request the page makes. The key is in the cookie: nothing here sends or reads it.

export class AskError extends Error {
  constructor(status) {
    super(`the board answered ${status}`);
    this.status = status;
  }
}

// GET a JSON route. With the last ETag, a 304 comes back as `{ changed: false }`.
export async function get(path, etag = null) {
  const headers = etag ? { 'If-None-Match': etag } : {};
  const res = await fetch(path, { headers, cache: 'no-store', credentials: 'same-origin' });
  const now = res.headers.get('X-Chantier-Now');
  if (res.status === 304) return { changed: false, etag, now };
  if (!res.ok) throw new AskError(res.status);
  return { changed: true, etag: res.headers.get('ETag'), now, data: await res.json() };
}

export const board = () => get('/api/board');

export const projectState = (id, etag) =>
  get(`/api/projects/${encodeURIComponent(id)}/state`, etag);
