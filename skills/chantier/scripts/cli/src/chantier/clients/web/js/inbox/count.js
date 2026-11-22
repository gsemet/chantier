// The number the navigation, the bottom bar and the tab's title show: the entries of the scope
// shown that no hide covers now; nothing at zero, and nothing before the board has arrived.
import { entriesOf, split } from '../model/inbox.js';

export function inboxCount(state) {
  if (!state.board) return null;
  const { shown } = split(entriesOf(state.board, state.project), state.inboxMarks, Date.now());
  return shown.length || null;
}
