// The autosync panel's events: open and close it, and run the user's actions (start, stop, approve).
// The board's server runs the surface's own tool; this only asks, and shows the answer.
import { post } from '../core/api.js';
import { delegate } from '../core/dom.js';
import { snapshot, update } from '../core/store.js';
import { t } from '../model/words.js';
import { tickAutosync } from './autosync-tick.js';

const ROUTES = { start: 'api/autosync/start', stop: 'api/autosync/stop' };
const APPROVE = 'api/autosync/approve';

const setUi = (patch) => update({ autosync: { ...snapshot().autosync, ...patch } });

// The words for a refusal (409) or a failure (502): a known code is translated, else the server's line.
function failure({ data }) {
  if (data.code === 'blocked' || data.code === 'stale') return t(`autosync.err.${data.code}`);
  if (data.code === 'failed') return data.error;
  const state = t(`autosync.state.${data.code}`);
  return data.code ? t('autosync.err.state', { state }) : (data.error ?? '');
}

const withGroup = (data) =>
  data.autosync ? { board: { ...snapshot().board, autosync: data.autosync } } : {};

async function run(path, body) {
  setUi({ busy: true, error: '' });
  try {
    const answer = await post(path, body);
    update({
      ...withGroup(answer.data),
      autosync: { ...snapshot().autosync, busy: false, error: answer.ok ? '' : failure(answer) },
    });
  } catch {
    setUi({ busy: false, error: t('autosync.err.network') });
  }
}

export function bindAutosync(body) {
  delegate(body, 'click', '[data-autosync="toggle"]', () =>
    setUi({ open: !snapshot().autosync.open, error: '' }),
  );
  delegate(body, 'click', '[data-autosync-act]', (_, el) =>
    run(ROUTES[el.dataset.autosyncAct], {}),
  );
  delegate(body, 'click', '[data-autosync-approve]', (_, el) =>
    run(APPROVE, { incident: el.dataset.autosyncApprove }),
  );
  // in the capture phase: a click that redraws the panel must be judged on the element it hit
  document.addEventListener(
    'click',
    (event) => {
      if (snapshot().autosync.open && !event.target.closest('.aswrap')) setUi({ open: false });
    },
    true,
  );
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && snapshot().autosync.open) setUi({ open: false });
  });
  tickAutosync();
}
