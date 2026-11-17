// A model's exact id read as { provider, name, version }, for the Costs card. Pure, no DOM.
// Four providers are known (Anthropic, OpenAI, Google, xAI); any other id, and "?", has no
// provider and shows as itself, never a guessed one.
import { t } from './words.js';

// "fast-mode" -> "Fast Mode", "sol" -> "Sol".
const words = (text) =>
  text
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

// claude-<family>-<major>[-|.<minor>][-YYYYMMDD][-(variant)]
const CLAUDE = /^claude-([a-z]+)-(\d+)(?:[-.](\d{1,2}))?(?:-\d{8})?(?:-\(([^)]+)\))?$/i;

function claude(id) {
  const m = CLAUDE.exec(id);
  if (!m) return null;
  const [, family, major, minor, variant] = m;
  const number = minor === undefined ? major : `${major}.${minor}`;
  const version = `${words(family.toLowerCase())} ${number}`;
  return {
    provider: 'anthropic',
    name: 'Claude',
    version: variant ? `${version} (${variant.replaceAll('-', ' ')})` : version,
  };
}

// <prefix>-<version>[-<variant>] for the three families that name a model the same way.
const FAMILIES = [
  ['gpt', 'openai', 'GPT'],
  ['gemini', 'google', 'Gemini'],
  ['grok', 'xai', 'Grok'],
];

function family(id) {
  for (const [prefix, provider, name] of FAMILIES) {
    const m = new RegExp(`^${prefix}-(\\d+(?:\\.\\d+)?)(?:-(.+))?$`, 'i').exec(id);
    if (m) return { provider, name, version: m[2] ? `${m[1]} ${words(m[2])}` : m[1] };
  }
  return null;
}

export function parseModel(id) {
  const text = String(id ?? '');
  if (text === '?' || text === '') {
    return { provider: null, name: t('costs.money_unknown_model'), version: '' };
  }
  return claude(text) ?? family(text) ?? { provider: null, name: text, version: '' };
}
