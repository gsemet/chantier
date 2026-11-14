// Draw markup into an element so that a refresh is not felt: nothing is redrawn when the markup is
// the one already there, and a redraw keeps the scroll positions and the keyboard focus.
import { $, $$, applyVars, setHtml, textOf } from './dom.js';

const SEEN = new WeakMap();
const FOCUSABLE = 'a[href],button,input,select,textarea,[tabindex]';

// A focused element is found again by its `data-key`, else by its place among the focusables.
function focusOf(root) {
  const active = document.activeElement;
  if (!active || active === root || !root.contains(active)) return null;
  return { key: active.dataset.key ?? null, index: $$(FOCUSABLE, root).indexOf(active) };
}

// A scrolled element is named by its `data-scroll`; the root itself by the empty name.
const scrollsOf = (root) =>
  [root, ...$$('[data-scroll]', root)].map((el) => ({
    name: el === root ? '' : el.dataset.scroll,
    top: el.scrollTop,
    left: el.scrollLeft,
  }));

function restore(root, focus, scrolls) {
  for (const { name, top, left } of scrolls) {
    const el = name ? $(`[data-scroll="${CSS.escape(name)}"]`, root) : root;
    if (el) Object.assign(el, { scrollTop: top, scrollLeft: left });
  }
  if (!focus) return;
  const byKey = focus.key && $(`[data-key="${CSS.escape(focus.key)}"]`, root);
  const target = byKey || $$(FOCUSABLE, root)[focus.index];
  if (target) target.focus({ preventScroll: true });
}

// Draw `markup` into `element` unless it is what the element already holds.
export function paint(element, markup) {
  const text = textOf(markup);
  if (SEEN.get(element) === text) return false;
  const focus = focusOf(element);
  const scrolls = scrollsOf(element);
  SEEN.set(element, text);
  setHtml(element, markup);
  applyVars(element);
  restore(element, focus, scrolls);
  return true;
}

// Forget what an element holds: its next paint draws from nothing (a new view or project).
export function forget(element) {
  SEEN.delete(element);
}
