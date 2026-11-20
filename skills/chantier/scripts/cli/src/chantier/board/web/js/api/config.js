// The Configuration page's two ops. Unlike the backlog's writes, a refusal of a dry run (400)
// or of a stale file (409) is an answer the page shows, so it comes back as { ok, status, data }.
import { post, read } from '../core/api.js';

// The configuration of a project: { hosts, timing, limits, others, files, problems, writable, file, sha256, batch }.
export const readConfig = async (project) => (await read('config.get', { project })).data;

// Change the `agent` or `model` of roles, or one of the two limits, in the planning surface's
// project file. `changes` is a list of { host, role, key, value } or, for a limit, { key, value }
// (a null value goes back to the inherited one), `base` the
// SHA-256 the page was drawn from, `dry` true to judge without writing.
export const changeConfig = (project, changes, base, dry) =>
  post('config.put', { project, changes, base_sha256: base, dry_run: dry });
