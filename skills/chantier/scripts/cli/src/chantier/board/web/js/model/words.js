// Every word the page shows: one file per language under i18n/, registered here. To add a
// language, add its file with the same keys and one line below.
import { pref, setPref } from '../core/store.js';
import en from '../i18n/en.js';
import fr from '../i18n/fr.js';

const LANGUAGES = { en, fr };
const KEY = 'lang';
let current = 'en';

export const codes = () => Object.keys(LANGUAGES);

export const language = () => current;

// The language asked: ?lang=, the one chosen last, then the browser's, else English.
export function pick(asked = null, browser = navigator.language ?? '') {
  return [asked, pref(KEY), browser.slice(0, 2)].find((code) => code in LANGUAGES) ?? 'en';
}

export function setLanguage(code) {
  if (!(code in LANGUAGES)) return;
  current = code;
  setPref(KEY, code);
  document.documentElement.lang = code;
}

// The next language after the current one, in the order of the registry.
export function nextLanguage() {
  const all = codes();
  return all[(all.indexOf(current) + 1) % all.length];
}

// A word, with its `{name}` holes filled. An unknown key shows as itself.
export function t(key, params = {}) {
  const text = LANGUAGES[current][key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, name) => params[name] ?? '');
}

// A word of another language (the language button names the language it switches to).
export const wordOf = (code, key) => LANGUAGES[code][key] ?? key;
