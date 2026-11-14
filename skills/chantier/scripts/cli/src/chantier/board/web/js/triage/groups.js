// Groups: create, join, move whole, undo. A group is a name in each member's summary; the server
// moves the members to the first item's column, then names them. Each call goes through `run`.
import { groupItems, moveGroup, ungroup } from '../api/backlog.js';
import { snapshot } from '../core/store.js';
import { columnOf, findItem, groupNames, membersOf } from '../model/triage.js';
import { t } from '../model/words.js';
import { showDialog } from '../ui/dialog.js';
import { clearSelection, run } from './actions.js';

const project = () => snapshot().project;
const backlog = () => snapshot().data?.backlog;
const slugsOf = (name) => membersOf(backlog(), name).map((i) => i.item);

// Ask the name of a new group ("group N" by default) and put `slugs` in it, the first one's column.
export async function createGroup(slugs) {
  const asked = await showDialog({
    title: t('groups.title'),
    note: t('groups.note'),
    confirm: t('groups.confirm'),
    fields: [
      {
        name: 'name',
        label: t('groups.name'),
        value: t('groups.default', { n: groupNames(backlog()).size + 1 }),
      },
    ],
  });
  const name = asked?.name.trim();
  if (!name) return null;
  const done = await run(slugs, () => groupItems(project(), slugs, name));
  if (done) clearSelection(slugs);
  return done;
}

// Join the group `name`: the post-it follows its members' column (the server moves it).
export function joinGroup(slug, name) {
  const member = slugsOf(name).find((s) => s !== slug);
  const already = findItem(backlog(), slug)?.group === name;
  return member && !already ? run([slug], () => groupItems(project(), [member, slug], name)) : null;
}

export function moveWhole(name, to) {
  const [first] = slugsOf(name);
  if (!first || columnOf(backlog(), first) === to) return null;
  return run(slugsOf(name), () => moveGroup(project(), name, to));
}

export const undo = (name) => run(slugsOf(name), () => ungroup(project(), name));

// A post-it dropped on another: it joins the other's group, else both make a new one.
export function dropOnPostit(slug, onto) {
  const target = findItem(backlog(), onto);
  return target?.group ? joinGroup(slug, target.group) : createGroup([onto, slug]);
}
