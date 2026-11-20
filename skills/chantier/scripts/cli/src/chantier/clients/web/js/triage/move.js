// Moving post-its: to a column or a row of Triage. A post-it already in the target column writes
// nothing (there is no rank inside a row).
import { moveItems } from '../api/backlog.js';
import { snapshot } from '../core/store.js';
import { columnOf } from '../model/triage.js';
import { run } from './actions.js';

// Move the slugs that are not in `to` already; null when none is left to move.
export function moveTo(slugs, to) {
  const { project, data } = snapshot();
  const here = slugs.filter((s) => columnOf(data?.backlog, s) !== to);
  return here.length ? run(here, () => moveItems(project, here, to)) : null;
}
