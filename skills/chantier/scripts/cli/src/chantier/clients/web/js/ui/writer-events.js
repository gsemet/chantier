// The writer panel's events: open and close it, and the one action, Sync now. The board's server
// runs the writer; this only asks it for a cycle, and shows the answer.
import { post } from '../core/api.js';
import { delegate } from '../core/dom.js';
import { snapshot, update } from '../core/store.js';
import { t } from '../model/words.js';
import { tickWriter } from './writer-tick.js';

const setUi = (patch) => update({ writer: { ...snapshot().writer, ...patch } });

// The words for a refusal (409): the server's line; a network failure has our own.
const failure = ({ data }) => data?.error ?? t('writer.err.network');

async function run() {
  setUi({ busy: true, error: '' });
  try {
    const answer = await post('writer.sync', {});
    const shown = answer.data?.writer;
    update({
      ...(shown ? { board: { ...snapshot().board, writer: shown } } : {}),
      writer: { ...snapshot().writer, busy: false, error: answer.ok ? '' : failure(answer) },
    });
  } catch {
    setUi({ busy: false, error: t('writer.err.network') });
  }
}

export function bindWriter(body) {
  delegate(body, 'click', '[data-writer="toggle"]', () =>
    setUi({ open: !snapshot().writer.open, error: '' }),
  );
  delegate(body, 'click', '[data-writer-sync]', () => run());
  // in the capture phase: a click that redraws the panel must be judged on the element it hit
  document.addEventListener(
    'click',
    (event) => {
      if (snapshot().writer.open && !event.target.closest('.aswrap')) setUi({ open: false });
    },
    true,
  );
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && snapshot().writer.open) setUi({ open: false });
  });
  tickWriter();
}
