// How the page writes a value: money, sizes, ages, local times, PR numbers, slugs, titles.
// Ages are counted against the server's instant (the `now` of its answers), never the device's.
import { t } from '../model/words.js';

const MINUTE = 60;
const HOUR = 3600;
const DAY = 86400;
const KILO = 1024;

// "$12.40", or a dash when there is no figure.
export const usd = (n) => (n == null ? '—' : `$${Number(n).toFixed(2)}`);

// "812 B", "4.2 KB", "35 KB".
export function size(bytes) {
  if (bytes < KILO) return `${bytes} B`;
  const kb = bytes / KILO;
  if (kb < 10) return `${kb.toFixed(1)} KB`;
  if (kb < KILO) return `${Math.round(kb)} KB`;
  return `${(kb / KILO).toFixed(1)} MB`;
}

// "12 s", "5 min", "3 h", "2 d": the time between two ISO instants.
export function span(fromIso, toIso) {
  const seconds = Math.max(0, Math.round((Date.parse(toIso) - Date.parse(fromIso)) / 1000));
  if (seconds < MINUTE) return t('time.s', { n: seconds });
  if (seconds < HOUR) return t('time.min', { n: Math.round(seconds / MINUTE) });
  if (seconds < DAY) return t('time.h', { n: Math.round(seconds / HOUR) });
  return t('time.d', { n: Math.round(seconds / DAY) });
}

// How long ago an instant of the record was, as the server sees it; empty when unknown.
export const age = (iso, nowIso) => (iso && nowIso ? span(iso, nowIso) : '');

// A wait measured on the device (the foot's "Data: N min ago"): from device milliseconds.
export const waited = (sinceMs, nowMs = Date.now()) =>
  span(new Date(sinceMs).toISOString(), new Date(nowMs).toISOString());

// The local time of an instant, "14:05".
export function hhmm(iso) {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return '';
  return at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}

// "#41" from a PR's address, else empty.
export const prNumber = (url) => (url ? `#${String(url).split('/').pop()}` : '');

// "visualization-backend" from a folder "…/2-actives/225-visualization-backend".
export const slug = (folder) => (folder ?? '').split('/').pop().replace(/^\d+-/, '');

// A title without the "Change Specification: " or "Intent: " prefix the files carry.
export const title = (text) => String(text ?? '').replace(/^(Change Specification|Intent):\s*/, '');

// A share of a whole as a percentage in [0, 100]; zero when the whole is zero.
export const percent = (part, whole) =>
  whole > 0 ? Math.min(100, Math.max(0, (part / whole) * 100)) : 0;

// A link only for an http(s) address; anything else is no link and gives null.
export const safeUrl = (url) => (/^https?:\/\//i.test(url ?? '') ? url : null);

// A project's colour is one of the palette's marks, picked from its name.
export const markOf = (id) => [...id].reduce((sum, c) => sum + c.codePointAt(0), 0) % 6;
