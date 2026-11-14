// The one `html` tagged template that escapes, the one place that sets innerHTML, and the small
// query and event helpers the views use.

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

class Markup {
  constructor(text) {
    this.text = text;
  }

  toString() {
    return this.text;
  }
}

export const raw = (text) => new Markup(text);

export const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ESCAPES[c]);

const part = (value) => {
  if (value instanceof Markup) return value.text;
  if (Array.isArray(value)) return value.map(part).join('');
  return esc(value);
};

// html`<b>${text}</b>`: every value is escaped unless it is Markup or a list of it.
export function html(strings, ...values) {
  const text = strings.reduce(
    (out, s, i) => out + s + (i < values.length ? part(values[i]) : ''),
    '',
  );
  return new Markup(text);
}

// The text of a markup, of a list of it, or of a plain string (escaped): what the page compares to
// skip a redraw.
export const textOf = part;

// The only innerHTML of the page. A plain string is escaped, never taken as markup.
export function setHtml(element, markup) {
  element.innerHTML = textOf(markup);
}

export const $ = (selector, root = document) => root.querySelector(selector);

export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

// One listener on `root` for a kind of event: `handler(event, target)` runs for a click inside
// the closest element matching `selector`. It returns the function that removes the listener.
export function delegate(root, type, selector, handler) {
  const listener = (event) => {
    const target = event.target.closest(selector);
    if (target && root.contains(target)) handler(event, target);
  };
  root.addEventListener(type, listener);
  return () => root.removeEventListener(type, listener);
}

// A value that sets a CSS custom property on an element: a computed width or colour reaches the
// stylesheet this way and never as a `style` attribute written in markup.
export function setVars(element, vars) {
  for (const [name, value] of Object.entries(vars)) element.style.setProperty(name, value);
}

// The attribute that carries custom properties in markup: `data-vars="${vars({ '--w': '40%' })}"`.
export const vars = (map) => JSON.stringify(map);

// Every `[data-vars]` element gets its custom properties: the markup says which, this sets them.
export function applyVars(root) {
  for (const element of $$('[data-vars]', root)) {
    setVars(element, JSON.parse(element.dataset.vars));
  }
}
