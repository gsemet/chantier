// The key notice's two events: "Open" (or Enter) goes to the page's own address with the field's
// text as `k`, and the server's exchange reads a key or a whole link, sets the cookie and sends the
// page back with no `k`. The text is read at the click and goes nowhere else: no store field, no web
// storage, no script-written cookie.
import { $, delegate } from '../core/dom.js';

function open(root) {
  const text = $('[data-key-field]', root).value.trim();
  if (!text) return;
  const address = new URL(location.href);
  address.searchParams.set('k', text);
  location.assign(address.href);
}

export function bindKeyNotice(root) {
  delegate(root, 'click', '[data-key-open]', () => open(root));
  delegate(root, 'keydown', '[data-key-field]', (event) => {
    if (event.key === 'Enter') open(root);
  });
}
