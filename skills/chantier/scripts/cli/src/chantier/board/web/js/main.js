// The page's start: the language, the first read of the board, the shell drawn from the store, and
// the few events of the frame (a view, a project, the menu, the language, Escape).
import { board } from './core/api.js';
import { $, delegate } from './core/dom.js';
import { paint } from './core/paint.js';
import { start } from './core/refresh.js';
import { configure, go, listen, resolve } from './core/router.js';
import { snapshot, subscribe, update } from './core/store.js';
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

function listenToFrame() {
  const body = document.body;
  delegate(body, 'click', '[data-view]', (_, el) => {
    update({ menu: false });
    go({ view: el.dataset.view });
  });
  delegate(body, 'click', '[data-go]', (_, el) => go({ view: el.dataset.go }));
  delegate(body, 'click', '[data-project]', (_, el) => {
    update({ menu: false });
    go({ project: el.dataset.project });
  });
  delegate(body, 'click', '[data-close]', () => closePanel());
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
    if (event.key !== 'Escape') return;
    const { menu: open, panel } = snapshot();
    if (open) update({ menu: false });
    else if (panel) closePanel();
  });
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
