// The batch view. Round 1 ships the contract only: round 2 draws the view.
//   render(state) returns the view's markup (html); mount(root, state), if any, returns a cleanup;
//   after(root, state), if any, runs after each paint (measures, arrows).

import { t } from '../model/words.js';
import { empty } from '../ui/parts.js';

export const render = () => empty(t('nav.batch'));
