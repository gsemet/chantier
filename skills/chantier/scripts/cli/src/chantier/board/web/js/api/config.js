// The Configuration page's two routes. Unlike the backlog's writes, a refusal of a dry run (400)
// or of a stale file (409) is an answer the page shows, so it comes back as { ok, status, data }.
import { get, route, send } from '../core/api.js';

// The configuration of a project: { hosts, others, files, problems, writable, file, sha256, batch }.
export const readConfig = async (project) => (await get(route(project, 'config'))).data;

// Change the `agent` or `model` of roles in the planning surface's project file. `changes` is a
// list of { host, role, key, value } (a null value goes back to the inherited one), `base` the
// SHA-256 the page was drawn from, `dry` true to judge without writing.
export const changeConfig = (project, changes, base, dry) =>
  send('PUT', route(project, 'config'), { changes, base_sha256: base, dry_run: dry });
