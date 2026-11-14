// HTML5 drag and drop on Triage (a PC; a touch browser fires none, the selection bar is its way).
// A post-it dropped on a column or a row moves there, on another post-it makes or joins a group,
// on a group's frame joins it; a group dragged by its handle moves whole. The drop target is
// lit while the drag is over it.
import { $$, delegate } from '../core/dom.js';
import { dropOnPostit, joinGroup, moveWhole } from './groups.js';
import { moveTo } from './move.js';

let dragging = null; // { slug } for a post-it, { group } for a group handle

const clearOver = (root) => {
  for (const el of $$('.over', root)) el.classList.remove('over');
};

function start(event, source) {
  const slug = source.dataset.slug;
  const group = source.dataset.gdrag;
  dragging = slug ? { slug } : { group };
  source.classList.add('drag');
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', slug ?? group);
}

// The nearest thing a drag can land on: a post-it, a group's frame, a column or a row.
// A dragged group lands on a column or a row only, wherever the pointer is inside it.
const targetOf = (event) =>
  dragging?.group
    ? event.target.closest('[data-col]')
    : (event.target.closest('.pi') ??
      event.target.closest('.grpf') ??
      event.target.closest('[data-col]'));

function light(root, event) {
  if (!dragging) return null;
  const target = targetOf(event);
  const own = target?.classList.contains('pi') && target.dataset.slug === dragging.slug;
  if (!target || own) return null;
  event.preventDefault();
  clearOver(root);
  if (!target.classList.contains('pi')) target.classList.add('over');
  return target;
}

function drop(root, event) {
  const target = light(root, event);
  clearOver(root);
  const moved = dragging;
  dragging = null;
  if (!target || !moved) return;
  event.preventDefault();
  if (moved.group) moveWhole(moved.group, target.dataset.col);
  else if (target.classList.contains('pi')) dropOnPostit(moved.slug, target.dataset.slug);
  else if (target.classList.contains('grpf')) joinGroup(moved.slug, target.dataset.gid);
  else moveTo([moved.slug], target.dataset.col);
}

// A post-it's own drop on a column removes it from its group (the server does that for a lone
// post-it); nothing here knows it.
export function bindDrag(root) {
  const offs = [
    delegate(root, 'dragstart', '.pi, [data-gdrag]', start),
    delegate(root, 'dragend', '.pi, [data-gdrag]', (_, el) => {
      el.classList.remove('drag');
      dragging = null;
      clearOver(root);
    }),
  ];
  const over = (event) => light(root, event);
  const leave = (event) => {
    if (!root.contains(event.relatedTarget)) clearOver(root);
  };
  const dropped = (event) => drop(root, event);
  root.addEventListener('dragover', over);
  root.addEventListener('dragleave', leave);
  root.addEventListener('drop', dropped);
  return () => {
    for (const off of offs) off();
    root.removeEventListener('dragover', over);
    root.removeEventListener('dragleave', leave);
    root.removeEventListener('drop', dropped);
  };
}
