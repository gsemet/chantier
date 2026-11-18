// Every word the page shows: one file per language under i18n/, registered here. To add a
// language, add its file with the same keys and one line below.
import { pref, setPref, snapshot } from '../core/store.js';
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

// The MR form of a key: `mr.<x>` for `pr.<x>`, `mr.<key>` for any other (see i18n/en-mr.js).
const mrKey = (key) => `mr.${key.startsWith('pr.') ? key.slice(3) : key}`;

// A word for a project of that forge, with its `{name}` holes filled: on GitLab the MR form when
// there is one, else the key's own. An unknown key shows as itself.
export function tf(forge, key, params = {}) {
  const words = LANGUAGES[current];
  const text = (forge === 'gitlab' ? words[mrKey(key)] : undefined) ?? words[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, name) => params[name] ?? '');
}

// A word for the project shown (its forge is `forge` in the state).
export const t = (key, params = {}) => tf(snapshot().data?.forge, key, params);

// A word with a count: `<key>.one` when the count is one ("1 file"), else `<key>` ("3 files").
export const tn = (key, n) => t(n === 1 ? `${key}.one` : key, { n });

// A word of another language (the language button names the language it switches to).
export const wordOf = (code, key) => LANGUAGES[code][key] ?? key;
