// The CR's file panel. The contract the views use: `openPanel(state, target)` opens the folder of
// a target (see model/targets.js) and `closePanel()` closes it. Round 3 draws the panel in full
// (head, tree, file view); until then it shows the target's head only.
import { html } from '../core/dom.js';
import { update } from '../core/store.js';
import { t } from '../model/words.js';
import { icon } from '../ui/icons.js';

export const openPanel = (_state, target) => update({ panel: target });

export const closePanel = () => update({ panel: null });

// What the panel holds for the state: nothing while it is closed.
export function panelMarkup(state) {
  const target = state.panel;
  if (!target) return '';
  return html`<div class="bar"><button class="btn" type="button" data-close aria-label="${t('panel.close')}">${icon('close')}</button><h2>${target.title}</h2></div><div class="body"><code>${target.folder ?? ''}</code> · ${t('panel.files', { n: target.files ?? 0 })}</div>`;
}
