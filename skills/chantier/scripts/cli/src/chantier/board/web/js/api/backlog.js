// The board's writes, one function per route of the server (the backlog only: the inbox, P1 to P4
// and 3-ready). A refusal of the CLI's own code comes back as a `BoardWriteError` carrying its
// message, its status and the board's whole answer (a write of several items may have written
// some). The page never guesses: after a write it reads the record again.
import { get, route, send } from '../core/api.js';

export class BoardWriteError extends Error {
  constructor(message, status, data = null) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function write(method, project, path, body) {
  const { ok, status, data } = await send(method, route(project, path), body);
  if (ok && data?.ok) return data;
  throw new BoardWriteError(data?.error ?? `the board answered ${status}`, status, data);
}

const post = (project, path, body) => write('POST', project, path, body);

// File an idea in the inbox; `slug` only when the title's slug is taken.
export const newIdea = (project, text, slug = null) =>
  post(project, 'backlog/new', slug ? { text, slug } : { text });

// Move items, or a whole group, to `inbox`, `P1`..`P4` or `3-ready`.
export const moveItems = (project, items, to) => post(project, 'backlog/move', { items, to });

export const moveGroup = (project, group, to) => post(project, 'backlog/move', { group, to });

export const addLabel = (project, items, label) =>
  post(project, 'backlog/labels', { items, add: [label] });

// Put items in one group: they all go to the first item's column.
export const groupItems = (project, items, name) => post(project, 'backlog/group', { items, name });

export const ungroup = (project, name) => post(project, 'backlog/ungroup', { name });

// Replace a Markdown file of an item; `base` is the SHA-256 the editor loaded.
export const saveFile = (project, { item, path, text, base }) =>
  write('PUT', project, 'backlog/file', { item, path, text, base_sha256: base });

export const declareReady = (project) => post(project, 'backlog/next-batch', {});

export const rescan = (project) => post(project, 'journal/rescan', {});

// The entries the board wrote since the last rescan: { entries, count, now }.
export const readJournal = async (project) => (await get(route(project, 'journal'))).data;
