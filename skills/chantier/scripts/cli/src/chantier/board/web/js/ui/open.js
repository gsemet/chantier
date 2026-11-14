// A card, a row or a node that carries `data-open="<key>"` opens its folder in the panel: with a
// click, or with Enter or Space once it has the keyboard focus. A view binds it once on its root.
import { delegate, html } from '../core/dom.js';
import { snapshot } from '../core/store.js';
import { targetFor } from '../model/targets.js';
import { openPanel } from '../panel/panel.js';

function open(event, element) {
  const state = snapshot();
  const target = targetFor(state, element.dataset.open);
  if (!target) return;
  event.preventDefault();
  event.stopPropagation();
  openPanel(state, target);
}

// Returns the function that removes both listeners.
export function bindOpen(root) {
  const offClick = delegate(root, 'click', '[data-open]', open);
  const offKey = delegate(root, 'keydown', '[data-open]', (event, element) => {
    if (event.key === 'Enter' || event.key === ' ') open(event, element);
  });
  return () => {
    offClick();
    offKey();
  };
}

// The attributes that make an element a keyboard button that opens `key`. `scope` tells apart two
// elements of a view that open the same key (the focus is found again by it after a redraw).
export const opener = (key, scope = '') =>
  html`data-open="${key}" data-key="${scope}open-${key}" tabindex="0" role="button"`;
