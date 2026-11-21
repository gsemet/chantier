// The folded rows of Triage's Backlog column: P1 to P4 each fold on a click on their head. The choice
// is the device's preference `triageFolded` (the rows, comma-separated, in LANES order), the same
// for every project; a value that cannot be read reads as open. Nothing is written but the store's
// preference and the selection (the post-its drawn in a row being folded leave it).
import { delegate } from '../core/dom.js';
import { pref, setPref, snapshot, update } from '../core/store.js';
import { columnOf, LANES } from '../model/triage.js';

// The folded rows in a stored text: only the names of the rows, once each, in LANES order.
export const readFolded = (text) => {
  const names = String(text ?? '').split(',');
  return LANES.filter((row) => names.includes(row));
};

// The rows folded now: the store's field, else the device's preference.
export const foldedOf = (state) => state.triageFolded ?? readFolded(pref('triageFolded'));

// Fold the row, or open it if it is folded; a fold leaves the selection of what it hides.
export function toggleFold(row) {
  const state = snapshot();
  if (!LANES.includes(row)) return;
  const now = foldedOf(state);
  const folding = !now.includes(row);
  const triageFolded = LANES.filter((r) => (r === row ? folding : now.includes(r)));
  setPref('triageFolded', triageFolded.join(','));
  const selection = folding
    ? state.selection.filter((slug) => columnOf(state.data?.backlog, slug) !== row)
    : state.selection;
  update({ triageFolded, selection });
}

// One delegated click on a lane's head; the chevron button inside it has no handler of its own.
export const bindFold = (root) =>
  delegate(root, 'click', '[data-fold]', (_, head) => toggleFold(head.dataset.fold));
