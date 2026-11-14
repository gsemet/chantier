// Ages are counted against the server's instant (the `now` of its answers), never the device's clock.

import { t } from './i18n.js';

const MINUTE = 60;
const HOUR = 3600;
const DAY = 86400;

// "12 s", "5 min", "3 h", "2 d": the time between two ISO instants.
export function span(fromIso, toIso) {
  const seconds = Math.max(0, Math.round((Date.parse(toIso) - Date.parse(fromIso)) / 1000));
  if (seconds < MINUTE) return t('time.s', { n: seconds });
  if (seconds < HOUR) return t('time.min', { n: Math.round(seconds / MINUTE) });
  if (seconds < DAY) return t('time.h', { n: Math.round(seconds / HOUR) });
  return t('time.d', { n: Math.round(seconds / DAY) });
}

// How long ago an instant of the record was, as the server sees it.
export const ago = (iso, nowIso) => (iso && nowIso ? span(iso, nowIso) : '');

// A wait measured on the device (the foot's "heard from the server"): seconds only.
export const waited = (sinceMs, nowMs = Date.now()) =>
  span(new Date(sinceMs).toISOString(), new Date(nowMs).toISOString());
