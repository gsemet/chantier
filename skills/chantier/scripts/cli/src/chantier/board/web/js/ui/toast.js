// The toast: one message at the bottom of the page. A success ("Written: ...") goes by itself
// after 2.6 s; a refusal shows the CLI's message on a red tint and stays until it is closed or
// another toast replaces it. A success is announced as a status, a refusal as an alert (each toast
// is a new element, so a screen reader announces it).
import { t } from '../model/words.js';

const SUCCESS_MS = 2600;
let timer = null;

function hide() {
  clearTimeout(timer);
  document.getElementById('toast')?.remove();
}

function closer() {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'toast-x';
  button.textContent = '×';
  button.setAttribute('aria-label', t('toast.close'));
  button.addEventListener('click', hide);
  return button;
}

// Show `message`; `error` makes it a refusal that stays.
export function toast(message, { error = false } = {}) {
  hide();
  const box = document.createElement('div');
  const text = document.createElement('span');
  text.textContent = message;
  box.id = 'toast';
  box.className = `toast${error ? ' err' : ''}`;
  box.setAttribute('role', error ? 'alert' : 'status');
  box.append(text, ...(error ? [closer()] : []));
  document.body.append(box);
  if (!error) timer = setTimeout(hide, SUCCESS_MS);
}

// "Written: <words>": the success of a write.
export const written = (words) => toast(t('toast.written', { text: words }));
