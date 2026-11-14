// The drawn icon set (the prototype's `IC`): one SVG each, stroked in the text colour.
import { raw } from './dom.js';

const draw = (paths) =>
  raw(`<svg class="svgi" viewBox="0 0 24 24" aria-hidden="true">${paths}</svg>`);

const PATHS = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
  triage:
    '<path d="M3 13h5l1.5 3h5l1.5-3h5"/><path d="M5.5 5h13L21 13v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-6z"/>',
  kanban: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/>',
  batch:
    '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="7" r="2"/>' +
    '<path d="M6 7v10"/><path d="M18 9a7 7 0 0 1-7 7H8"/>',
  costs:
    '<circle cx="12" cy="12" r="9"/><path d="M15 9.5c-.5-1-1.6-1.5-3-1.5-1.7 0-3 .8-3 2s1.3 1.7 3 2 3 ' +
    '.9 3 2.1-1.3 1.9-3 1.9c-1.5 0-2.6-.6-3.1-1.6M12 6v2M12 16v2"/>',
  file: '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5"/>',
  folder: '<path d="M3 7a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>',
  expand: '<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/>',
  ext:
    '<path d="M14 4h6v6M20 4 10 14"/>' +
    '<path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  dep: '<path d="M6 4v8a4 4 0 0 0 4 4h8"/><path d="m15 13 3 3-3 3"/>',
  img: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="m21 16-5-5-9 9"/>',
  blank: '<rect x="5" y="3" width="14" height="18" rx="1"/>',
  chev: '<path d="m7 10 5 5 5-5"/>',
};

export const icon = (name) => draw(PATHS[name] ?? '');

export const ICON_NAMES = Object.keys(PATHS);
