// "The next batch is ready": the marker the user writes. The server reads 3-ready itself and never
// trusts a list from the page; the button is off when 3-ready is empty or the marker matches it.
import { declareReady } from '../api/backlog.js';
import { delegate } from '../core/dom.js';
import { snapshot } from '../core/store.js';
import { run } from './actions.js';

export const declare = () => {
  const { project } = snapshot();
  return run([], () => declareReady(project));
};

export const bindReady = (root) => delegate(root, 'click', '[data-ready]', () => declare());
