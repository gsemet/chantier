// The board's writes, one function per op of the server (the backlog only: the inbox, P1 to P4,
// 3-ready and the running batch's mark). A refusal of the CLI's own code comes back as a `BoardWriteError` carrying its
// message, its status and the board's whole answer (a write of several items may have written
// some). The page never guesses: after a write it reads the record again.
import { post, read } from '../core/api.js';

export class BoardWriteError extends Error {
  constructor(message, status, data = null) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function write(op, project, body) {
  const { ok, status, data } = await post(op, { project, ...body });
  if (ok && data?.ok) return data;
  throw new BoardWriteError(data?.error ?? `the board answered ${status}`, status, data);
}

// File an idea in the inbox; `title` is the optional short title written above the text, `slug`
// only when the title's slug is taken.
export const newIdea = (project, text, slug = null, title = null) =>
  write('backlog.new', project, { text, ...(slug ? { slug } : {}), ...(title ? { title } : {}) });

// Move items, or a whole group, to `inbox`, `P1`..`P4`, `3-ready` or `running-batch` (the mark for
// the open batch; with no batch open the server moves them to `3-ready`).
export const moveItems = (project, items, to) => write('backlog.move', project, { items, to });

export const moveGroup = (project, group, to) => write('backlog.move', project, { group, to });

export const addLabel = (project, items, label) =>
  write('backlog.labels', project, { items, add: [label] });

// Put items in one group: they all go to the first item's column.
export const groupItems = (project, items, name) =>
  write('backlog.group', project, { items, name });

export const ungroup = (project, name) => write('backlog.ungroup', project, { name });

// Replace a Markdown file of an item; `base` is the SHA-256 the editor loaded.
export const saveFile = (project, { item, path, text, base }) =>
  write('backlog.file', project, { item, path, text, base_sha256: base });

export const declareReady = (project) => write('backlog.next_batch', project, {});

export const rescan = (project) => write('journal.rescan', project, {});

// The entries the board wrote since the last rescan: { entries, count, now }.
export const readJournal = async (project) => (await read('journal.get', { project })).data;
