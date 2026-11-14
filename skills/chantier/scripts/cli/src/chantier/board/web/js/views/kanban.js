// The kanban view. Its title is the header's h1 (the frame reads `title`); the body is empty here.
import { html, setHtml } from '../dom.js';
import { t } from '../i18n.js';

export const title = 'nav.kanban';

// The body, drawn from the page's state (store.js) into the view area.
export function render(_state, root) {
  setHtml(root, html`<section class="empty" data-view="kanban">${t('view.empty')}</section>`);
}
