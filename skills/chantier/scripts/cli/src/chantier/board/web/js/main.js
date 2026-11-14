// The page's start: the language, the first read of the board, the shell drawn from the store, and
// the few events of the frame (a view, a project, the menu, the language, Escape).
import { board } from './core/api.js';
import { $, delegate } from './core/dom.js';
import { paint } from './core/paint.js';
import { start } from './core/refresh.js';
import { ALL, configure, go, listen, resolve } from './core/router.js';
import { snapshot, subscribe, update } from './core/store.js';
import { confirmLeave } from './edit/markdown-editor.js';
import { openNew } from './edit/new-idea.js';
import { nextLanguage, pick, setLanguage, t } from './model/words.js';
import { afterPanel, bindPanel, closePanel, panelMarkup, syncPanel } from './panel/panel.js';
import { bottomBar } from './ui/bottombar.js';
import { notice, stats, title } from './ui/header.js';
import { show } from './ui/host.js';
import { menu, trigger } from './ui/picker.js';
import { heard, languageButton, navigation, projectSide } from './ui/sidebar.js';
import { ids, overviewIds } from './views/registry.js';

const RETRY_MS = 5000;

function drawFrame(state) {
  paint($('#project-side'), projectSide(state));
  paint($('#views-label'), t('nav.views'));
  paint($('#side-nav'), navigation(state));
  paint($('#heard'), heard(state));
  paint($('#lang'), languageButton());
  paint($('#project-phone'), [trigger(state, 'pbtn'), menu(state)]);
  paint($('#title'), title(state));
  paint($('#stats'), stats(state));
  paint($('#bottom-nav'), bottomBar(state));
  paint($('#new'), t('new.button'));
  $('#new').hidden = state.project === ALL || !state.data;
}

function drawNotice(state) {
  const text = notice(state);
  const element = $('#notice');
  paint(element, text);
  element.hidden = !text;
}

function draw(state) {
  drawFrame(state);
  drawNotice(state);
  show($('#view'), state);
  const panel = $('#panel');
  paint(panel, panelMarkup(state));
  panel.classList.toggle('open', Boolean(state.panel));
  panel.inert = !state.panel;
  afterPanel(panel, state);
  syncPanel(state);
}

// A move away from an open editor asks first when the text would be lost.
const guarded = (action) => async (event, el) => {
  if (await confirmLeave()) action(event, el);
};

function listenToFrame() {
  const body = document.body;
  delegate(
    body,
    'click',
    '[data-view]',
    guarded((_, el) => {
      update({ menu: false });
      go({ view: el.dataset.view });
    }),
  );
  delegate(
    body,
    'click',
    '[data-go]',
    guarded((_, el) => go({ view: el.dataset.go })),
  );
  delegate(
    body,
    'click',
    '[data-project]',
    guarded((_, el) => {
      update({ menu: false });
      go({ project: el.dataset.project });
    }),
  );
  delegate(
    body,
    'click',
    '[data-close]',
    guarded(() => closePanel()),
  );
  delegate(body, 'click', '[data-new]', () => openNew());
  bindPanel($('#panel'));
  delegate(body, 'keydown', '[tabindex][data-go], [tabindex][data-project]', (event, el) => {
    if (event.key === 'Enter') el.click();
  });
  delegate(body, 'click', '[data-menu]', () => update({ menu: !snapshot().menu }));
  delegate(body, 'click', '[data-lang]', () => {
    setLanguage(nextLanguage());
    draw(snapshot());
  });
  document.addEventListener('click', (event) => {
    if (snapshot().menu && !event.target.closest('.menu, [data-menu]')) update({ menu: false });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !$('dialog[open]')) closeInnermost();
  });
}

// Escape closes the innermost thing first: the menu, the journal, the selection, then the panel.
function closeInnermost() {
  const { menu: open, panel, journalOpen, selection } = snapshot();
  if (open) update({ menu: false });
  else if (journalOpen) update({ journalOpen: false });
  else if (selection.length) update({ selection: [] });
  else if (panel) confirmLeave().then((ok) => ok && closePanel());
}

// Read the board until the server answers; the refresh takes over once a project is shown.
async function boot() {
  try {
    const got = await board();
    update({ board: got.data, now: got.now, heard: Date.now(), fails: 0, denied: false });
    go(resolve(got.data.projects), { replace: true });
    listen();
    start();
  } catch (error) {
    update({ fails: snapshot().fails + 1, denied: error.status === 401 });
    setTimeout(boot, RETRY_MS);
  }
}

setLanguage(pick(new URLSearchParams(location.search).get('lang')));
configure(ids(), overviewIds());
listenToFrame();
subscribe(draw);
draw(snapshot());
boot();
