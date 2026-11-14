// A native `<dialog>` the page asks one thing in: a title, a note, some fields (a line, a text
// area, a line with choices) and two buttons. It never uses `window.prompt`. The keyboard focus
// goes into it and comes back to what opened it. `showDialog` answers with the values typed, or
// null when the user cancelled.
//   submit(values) may be given: it runs on the confirm button and may answer { error, reveal }
//   to keep the dialog open with a message (and show the fields named in `reveal`).
import { $, $$, html, setHtml } from '../core/dom.js';
import { t } from '../model/words.js';

let counter = 0;

function control(field, id) {
  const common = html`id="${id}" name="${field.name}" autocomplete="off" spellcheck="false"`;
  if (field.kind === 'area') {
    return html`<textarea ${common} rows="${field.rows ?? 6}">${field.value ?? ''}</textarea>`;
  }
  const list = field.choices?.length ? html` list="${id}-list"` : '';
  const choices = (field.choices ?? []).map((c) => html`<option value="${c}"></option>`);
  const datalist = list ? html`<datalist id="${id}-list">${choices}</datalist>` : '';
  return html`<input type="text" ${common} value="${field.value ?? ''}"${list} />${datalist}`;
}

function fieldMarkup(field, id) {
  const hint = field.hint ? html`<small>${field.hint}</small>` : '';
  const hidden = field.hidden ? html` hidden` : '';
  return html`<label class="field" data-field="${field.name}"${hidden} for="${id}-${field.name}"><span>${field.label}</span>${control(field, `${id}-${field.name}`)}${hint}</label>`;
}

function markup(spec, id) {
  const note = spec.note ? html`<p class="note">${spec.note}</p>` : '';
  const fields = (spec.fields ?? []).map((f) => fieldMarkup(f, id));
  return html`<h2 id="${id}-title">${spec.title}</h2>${note}${fields}<p class="dlg-err" role="alert" hidden></p><div class="dlg-row"><button type="button" class="btn" data-do="cancel">${spec.cancel ?? t('dialog.cancel')}</button><button type="button" class="btn pri" data-do="ok">${spec.confirm ?? t('dialog.ok')}</button></div>`;
}

const valuesOf = (dialog) =>
  Object.fromEntries($$('input, textarea', dialog).map((el) => [el.name, el.value]));

function reveal(dialog, names = []) {
  for (const name of names) {
    const label = $(`[data-field="${CSS.escape(name)}"]`, dialog);
    if (label) label.hidden = false;
  }
}

async function confirmed(dialog, spec) {
  const values = valuesOf(dialog);
  const message = $('.dlg-err', dialog);
  const button = $('[data-do="ok"]', dialog);
  message.hidden = true;
  button.disabled = true;
  const answer = (await spec.submit?.(values)) ?? null;
  button.disabled = false;
  if (!answer?.error) return values;
  message.textContent = answer.error;
  message.hidden = false;
  reveal(dialog, answer.reveal);
  $('input:not([hidden]), textarea', dialog)?.focus();
  return null;
}

// Ask. The promise settles once, when the dialog is closed.
export function showDialog(spec) {
  const opener = document.activeElement;
  const id = `dlg-${++counter}`;
  const dialog = document.createElement('dialog');
  dialog.className = 'dlg';
  dialog.setAttribute('aria-labelledby', `${id}-title`);
  setHtml(dialog, markup(spec, id));
  document.body.append(dialog);
  return new Promise((resolve) => {
    let result = null;
    const finish = (values) => {
      result = values;
      dialog.close();
    };
    dialog.addEventListener('close', () => {
      dialog.remove();
      if (opener?.isConnected) opener.focus({ preventScroll: true });
      resolve(result);
    });
    dialog.addEventListener('click', async (event) => {
      const action = event.target.closest('[data-do]')?.dataset.do;
      if (action === 'cancel') finish(null);
      if (action === 'ok') {
        const values = await confirmed(dialog, spec);
        if (values) finish(values);
      }
    });
    dialog.addEventListener('keydown', (event) => {
      const enter = event.key === 'Enter' && (event.target.tagName !== 'TEXTAREA' || event.ctrlKey);
      if (enter || (event.key === 'Enter' && event.metaKey)) {
        event.preventDefault();
        $('[data-do="ok"]', dialog).click();
      }
    });
    dialog.showModal();
    $('input:not([hidden]), textarea', dialog)?.focus();
    document.activeElement?.select?.();
  });
}

// A question with two answers: true when confirmed.
export async function confirmDialog({ title, note, confirm, cancel }) {
  return (await showDialog({ title, note, confirm, cancel })) !== null;
}
