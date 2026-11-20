// The "pushed N s ago" line ages on the client between two live refreshes: every 5 s, only while
// the writer is synced and its panel is closed. The clock moves the server's last instant on.
import { snapshot, update } from '../core/store.js';

const EVERY_MS = 5000;

const ticking = (state) =>
  Boolean(state.now) &&
  state.board?.surface === true &&
  state.board.writer?.state === 'synced' &&
  !state.writer.open;

export function tickWriter() {
  setInterval(() => {
    const state = snapshot();
    if (ticking(state)) update({ now: new Date(Date.parse(state.now) + EVERY_MS).toISOString() });
  }, EVERY_MS);
}
