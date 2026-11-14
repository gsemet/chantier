// The board's journal: the button on Triage ("N writes since your last rescan"), its panel, and the
// reading of the entries. The server keeps the file; the page only reads it and says "rescan".

import { readJournal, rescan } from '../api/backlog.js';
import { delegate, html } from '../core/dom.js';
import { hhmm } from '../core/format.js';
import { snapshot, update } from '../core/store.js';
import { t, tn } from '../model/words.js';
import { toast } from '../ui/toast.js';

// The journal of the shown project, read again into the store.
export async function loadJournal() {
  const { project } = snapshot();
  if (!project) return;
  try {
    const got = await readJournal(project);
    if (snapshot().project === project) update({ journal: got });
  } catch {
    // the journal is a convenience: a failed read leaves the last one
  }
}

// How many writes since the last rescan: the full read if there is one, else the state's count.
export const countOf = (state) => state.journal?.count ?? state.data?.journal?.count ?? 0;

export function journalButton(state) {
  const n = countOf(state);
  return html`<button type="button" class="drafts${n ? ' has' : ''}" data-journal="toggle" data-key="journal-button" aria-expanded="${state.journalOpen}">${tn('journal.button', n)}</button>`;
}

const entryRow = (e) => html`<li><span class="when">${hhmm(e.t)}</span> ${e.text}</li>`;

// The panel, drawn only while it is open.
export function journalPanel(state) {
  if (!state.journalOpen) return '';
  const entries = (state.journal?.entries ?? []).filter((e) => e.kind !== 'rescan');
  const list = entries.length ? entries.map(entryRow) : html`<li>${t('journal.nothing')}</li>`;
  return html`<section class="dlist" role="dialog" aria-label="${t('journal.heading')}"><b>${t('journal.heading')}</b><ul data-scroll="journal">${list}</ul><div class="row"><button type="button" class="btn pri" data-journal="rescan" ${entries.length ? '' : 'disabled'}>${t('journal.rescan')}</button><button type="button" class="btn" data-journal="close" data-key="journal-close">${t('journal.close')}</button></div><p class="note">${t('journal.note')}</p></section>`;
}

async function said() {
  try {
    await rescan(snapshot().project);
    update({ journalOpen: false });
    await loadJournal();
    toast(t('journal.said'));
  } catch (error) {
    toast(error.message, { error: true });
  }
}

export function bindJournal(root) {
  return delegate(root, 'click', '[data-journal]', (_, button) => {
    const what = button.dataset.journal;
    if (what === 'toggle') update({ journalOpen: !snapshot().journalOpen });
    if (what === 'close') update({ journalOpen: false });
    if (what === 'rescan') said();
  });
}
