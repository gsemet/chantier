// Every write of Triage goes through `run`: the post-its it touches dim, the call is made, the
// toast says what was written (or the CLI's refusal), and the record is read again. The page never
// guesses: what it shows after a write is what the folder holds.
import { BoardWriteError } from '../api/backlog.js';
import { reload } from '../core/refresh.js';
import { snapshot, update } from '../core/store.js';
import { loadJournal } from '../journal/journal.js';
import { t } from '../model/words.js';
import { toast, written } from '../ui/toast.js';

const without = (list, slugs) => list.filter((s) => !slugs.includes(s));

function say(error) {
  const known = error instanceof BoardWriteError;
  toast(known ? error.message : t('toast.network'), { error: true });
}

// Run `call` for the post-its `slugs`; the answer, or null after a refusal.
export async function run(slugs, call) {
  update({ pending: [...snapshot().pending, ...slugs] });
  let answer = null;
  try {
    answer = await call();
    const words = (answer.journal ?? []).map((e) => e.text).join('; ');
    if (words) written(words);
  } catch (error) {
    say(error);
  }
  try {
    await reload();
    await loadJournal();
  } finally {
    update({ pending: without(snapshot().pending, slugs) });
  }
  return answer;
}

export const clearSelection = (slugs = null) =>
  update({ selection: slugs ? without(snapshot().selection, slugs) : [] });
