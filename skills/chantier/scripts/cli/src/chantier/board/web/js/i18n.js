// The words: one file per language under i18n/, registered here. Add a language by adding a file.
import en from './i18n/en.js';
import fr from './i18n/fr.js';

const LANGUAGES = { en, fr };
const STORE_KEY = 'chantier.lang';
let current = 'en';

export const codes = () => Object.keys(LANGUAGES);

export const language = () => current;

// The language asked: ?lang=, the one chosen last, then the browser's, else English.
export function pick(search = location.search) {
  const asked = new URLSearchParams(search).get('lang') ?? localStorage.getItem(STORE_KEY);
  const browser = (navigator.language ?? '').slice(0, 2);
  return [asked, browser].find((code) => code in LANGUAGES) ?? 'en';
}

export function setLanguage(code) {
  if (!(code in LANGUAGES)) return;
  current = code;
  localStorage.setItem(STORE_KEY, code);
  document.documentElement.lang = code;
}

// The next language after the current one, in the order of the registry.
export function nextLanguage() {
  const all = codes();
  return all[(all.indexOf(current) + 1) % all.length];
}

export function t(key, params = {}) {
  const text = LANGUAGES[current][key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, name) => params[name] ?? '');
}

export const wordOf = (code, key) => LANGUAGES[code][key] ?? key;
