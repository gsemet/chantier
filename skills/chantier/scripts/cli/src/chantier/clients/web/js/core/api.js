// Every request the page makes, each over `call` of `transport.js` (the one module that opens a
// socket or names an address). The key is in the cookie: nothing here sends or reads it. A read
// throws an `AskError` on a refusal; a write comes back as `{ ok, status, data }`, never thrown.
import { AskError, call, fileUrl } from './transport.js';

export { AskError, fileUrl };

// A read: the op's `data`, its clock, or a thrown `AskError`.
export async function read(op, args = {}) {
  const answer = await call(op, args);
  if (!answer.ok) throw new AskError(answer.status);
  return { data: answer.data, now: answer.now };
}

export const board = () => read('board.get');

// The project's state; with the last `rev`, an unchanged record comes back as `{ changed: false }`.
export async function projectState(project, rev = null) {
  const got = await read('project.state', { project, ...(rev ? { rev } : {}) });
  if (got.data.changed === false) return { changed: false, rev, now: got.now };
  return { changed: true, rev: got.data.rev, now: got.now, data: got.data };
}

export const costs = (project) => read('costs.get', { project });

// The PRs of a batch read on the forge (read-only; the server keeps a read for 10 s per batch);
// with no `batch`, the batch in 4-batch/, else the newest closed one.
export const prs = (project, batch) => read('prs.get', { project, ...(batch ? { batch } : {}) });

// The Dashboard's figures over the project's closed batches (`range`: '10', '20' or 'all').
export const dashboard = (project, range) => read('dashboard.get', { project, range });

export const tree = (project, path) => read('project.tree', { project, path });

// A text file: its text, whether the server cut it, and the SHA-256 of its bytes (an editor sends
// it back; the server leaves it out of a cut file).
export async function fileText(project, path) {
  const { data } = await read('project.file', { project, path });
  return { text: data.text, cut: data.cut, sha256: data.sha256 };
}

// An op that may refuse (409) or fail (502), a write above all: the answer comes back with its status and its JSON,
// the refusal's text in `data.error` when the op gave none. Only a failure of the
// network throws.
export async function post(op, args = {}) {
  const answer = await call(op, args);
  const data = answer.data ?? (answer.error ? { error: answer.error } : null);
  return { ok: answer.ok, status: answer.status, data };
}

// Ask the server to read the transcripts again. It answers at once; the figure arrives with
// the `costs` topic.
export async function recompute(project) {
  return (await read('costs.recompute', { project })).data;
}
