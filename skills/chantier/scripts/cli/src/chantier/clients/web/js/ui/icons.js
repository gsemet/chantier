// The icon set: one outline per name, drawn in `currentColor`. An icon is trusted markup.
import { raw } from '../core/dom.js';

const PATHS = {
  inbox:
    '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5 5h14l2 8v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-6z"/>',
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
  overview:
    '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  kanban: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/>',
  batch:
    '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="7" r="2"/><path d="M6 7v10"/><path d="M18 9a7 7 0 0 1-7 7H8"/>',
  pr: '<circle cx="6" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><path d="M6 8v8"/><path d="M18 16V9a3 3 0 0 0-3-3h-3"/><path d="m14 3-2 3 2 3"/>',
  costs:
    '<circle cx="12" cy="12" r="9"/><path d="M15 9.5c-.5-1-1.6-1.5-3-1.5-1.7 0-3 .8-3 2s1.3 1.7 3 2 3 .9 3 2.1-1.3 1.9-3 1.9c-1.5 0-2.6-.6-3.1-1.6M12 6v2M12 16v2"/>',
  dashboard: '<path d="M4 20h16"/><path d="M7 20v-7M12 20V6M17 20v-10"/>',
  config:
    '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
  triage: '<path d="M4 4h16v11l-5 5H4z"/><path d="M15 20v-5h5"/><path d="M8 9h8M8 13h4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  file: '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5"/>',
  folder: '<path d="M3 7a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>',
  expand: '<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/>',
  ext: '<path d="M14 4h6v6M20 4 10 14"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  dep: '<path d="M6 4v8a4 4 0 0 0 4 4h8"/><path d="m15 13 3 3-3 3"/>',
  img: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="m21 16-5-5-9 9"/>',
  blank: '<rect x="5" y="3" width="14" height="18" rx="1"/>',
  chev: '<path d="m7 10 5 5 5-5"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  spark: '<path d="M12 3v5M12 16v5M3 12h5M16 12h5M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3"/>',
  lang: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
};

// One small outline per state, drawn in the state's colour (`stateIcon` in ui/parts.js).
const RING = '<circle cx="12" cy="12" r="9"/>';
const STATES = {
  working: '<path d="M21 12a9 9 0 1 1-3.2-6.9"/>',
  draft: '<circle cx="12" cy="12" r="9" stroke-dasharray="1.2 3.6"/>',
  ready: `${RING}<path d="m8 12.5 3 3 5-6"/>`,
  waits: `${RING}<path d="M12 7v5l3 2"/>`,
  merged:
    '<circle cx="7" cy="5" r="2"/><circle cx="7" cy="19" r="2"/><circle cx="17" cy="12" r="2"/><path d="M7 7v10M7 8c0 3 3 4 8 4"/>',
  blocked: `${RING}<path d="M5.6 18.4 18.4 5.6"/>`,
  queued: `${RING.replace('r="9"', 'r="3"')}`,
  local: `${RING}<circle cx="12" cy="12" r="2.5"/>`,
};

export const iconNames = () => Object.keys(PATHS);

// The icon `name`, or an empty one for a name the set does not know.
export const icon = (name) =>
  raw(
    `<svg class="svgi" viewBox="0 0 24 24" aria-hidden="true">${PATHS[name] ?? PATHS.blank}</svg>`,
  );

// The glyph of a state (a name the set does not know reads as queued).
export const stateGlyph = (state) =>
  raw(
    `<svg class="svgi" viewBox="0 0 24 24" aria-hidden="true">${STATES[state] ?? STATES.queued}</svg>`,
  );
