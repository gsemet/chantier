// The page's start: the language, the frame, the board's projects, then the live refresh.
import { AskError, board } from './api.js';
import { mount } from './frame.js';
import { pick, setLanguage } from './i18n.js';
import { start } from './poll.js';
import { go, listen, resolve } from './router.js';
import { update } from './store.js';

async function boot() {
  setLanguage(pick());
  mount();
  try {
    const got = await board();
    update({ board: got.data, now: got.data.now });
    listen();
    start();
    go(resolve(got.data.projects), { replace: true });
  } catch (error) {
    update({ denied: error instanceof AskError && error.status === 401, fails: 2 });
  }
}

boot();
