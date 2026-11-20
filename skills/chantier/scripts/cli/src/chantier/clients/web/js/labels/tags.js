// The labels of an item as small tags. A label's colour is its place in the project's sorted list
// of labels (model/triage.js), one of six tokens. Shared by Triage's post-its and Kanban's cards.
import { html, vars } from '../core/dom.js';
import { labelColor } from '../model/triage.js';

// The colour of a label: a token, set as a custom property by `data-vars`.
export const colorVars = (all, label) => vars({ '--lc': `var(--label-${labelColor(all, label)})` });

export const labelTag = (all, label) =>
  html`<span class="lab" data-vars="${colorVars(all, label)}">${label}</span>`;

// The row of an item's tags, or nothing when it has none.
export const labelTags = (item, all) =>
  item.labels?.length
    ? html`<div class="labs">${item.labels.map((l) => labelTag(all, l))}</div>`
    : '';
