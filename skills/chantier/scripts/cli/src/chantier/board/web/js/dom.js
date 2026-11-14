// The one `html` tagged template that escapes, and the one place that sets innerHTML.

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

// The only innerHTML of the page. A plain string is escaped, never taken as markup.
export function setHtml(element, markup) {
  element.innerHTML = markup instanceof Markup ? markup.text : esc(markup);
}

export const $ = (selector, root = document) => root.querySelector(selector);

export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
