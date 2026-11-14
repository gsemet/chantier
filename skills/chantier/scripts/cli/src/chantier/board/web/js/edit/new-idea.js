// "New": file an idea in the inbox. A native dialog with a text area; the title and the slug come
// from the text, as the CLI's `file` makes them. When the CR folder already exists the dialog stays
// open with the CLI's message and shows a slug field to file again.
import { BoardWriteError, newIdea } from '../api/backlog.js';
import { reload } from '../core/refresh.js';
import { ALL } from '../core/router.js';
import { snapshot } from '../core/store.js';
import { loadJournal } from '../journal/journal.js';
import { t } from '../model/words.js';
import { showDialog } from '../ui/dialog.js';
import { written } from '../ui/toast.js';

const TAKEN = 'CR folder already exists';

const fields = () => [
  { name: 'text', kind: 'area', rows: 6, label: t('new.idea') },
  { name: 'slug', label: t('new.slug'), hint: t('new.slug_hint'), hidden: true },
];

// File the text; an error object keeps the dialog open.
async function file(project, values) {
  if (!values.text.trim()) return { error: t('new.empty') };
  try {
    const answer = await newIdea(project, values.text, values.slug.trim() || null);
    written(answer.journal.map((e) => e.text).join('; '));
    return null;
  } catch (error) {
    if (!(error instanceof BoardWriteError)) return { error: t('toast.network') };
    return { error: error.message, reveal: error.message.startsWith(TAKEN) ? ['slug'] : [] };
  }
}

export async function openNew() {
  const { project } = snapshot();
  if (!project || project === ALL) return;
  const filed = await showDialog({
    title: t('new.title'),
    confirm: t('new.file'),
    fields: fields(),
    submit: (values) => file(project, values),
  });
  if (!filed) return;
  await reload();
  await loadJournal();
}
