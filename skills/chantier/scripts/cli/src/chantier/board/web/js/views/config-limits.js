// The Configuration view's Limits tab: the two numbers a project sets, each an input that holds what
// the planning surface's project file sets (empty: inherited), the value in effect with its layer,
// and a control that takes the key back to the inherited value. Its changes are judged, saved and
// refused like the Models tab's.

import { html } from '../core/dom.js';
import { t } from '../model/words.js';
import { empty } from '../ui/parts.js';

export const LIMITS = [
  { key: 'specifying.parallel', id: 'parallel', min: 1 },
  { key: 'batch.slots', id: 'slots', min: 0 },
];

// What the surface project's own file holds for a key; a held reset counts as nothing.
export const mineOf = (limit) => {
  const held = limit.layers['surface project'];
  return held === 'reset' ? null : held;
};

function effective(limit) {
  if (limit.effective == null) return t('config.limits.unset');
  return t('config.in_layer', { value: limit.effective, layer: limit.layer });
}

function row(spec, limit, writable) {
  const value = mineOf(limit) ?? '';
  const off = writable ? '' : 'disabled';
  const over = limit.overridden_by
    ? html`<div class="over">${t('config.limits.overridden', { path: limit.overridden_by })}</div>`
    : '';
  const inherit =
    mineOf(limit) == null
      ? ''
      : html`<button class="btn" type="button" data-inherit="${spec.key}" ${off}>${t('config.limits.inherit')}</button>`;
  return html`<div class="lrow" data-limit-row="${spec.key}"><div>${t(`config.limits.${spec.id}`)}<small>${t(`config.limits.${spec.id}.text`)}</small></div><div><input type="number" min="${spec.min}" step="1" data-limit="${spec.key}" value="${value}" placeholder="${t('config.inherited')}" ${off} />${inherit}<div class="eff">${t('config.effective')} ${effective(limit)}</div>${over}</div></div>`;
}

export function limitsTab(view) {
  if (!view.limits) return empty(t('config.limits.unreadable'));
  const rows = LIMITS.map((spec) => row(spec, view.limits[spec.key], view.writable));
  return html`<section class="limits">${rows}</section>`;
}

// The change a control asks for: a whole number, or null for the inherited value.
export const limitChange = (key, text) => ({
  key,
  value: text.trim() === '' ? null : Number(text),
});
