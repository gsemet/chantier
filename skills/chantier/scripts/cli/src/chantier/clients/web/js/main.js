// The page's start: the language, the first read of the board, the shell drawn from the store, and
// the few events of the frame (a view, a project, the menu, the language, Escape).
import { board } from './core/api.js';
import { $, delegate } from './core/dom.js';
import { paint } from './core/paint.js';
import { start } from './core/refresh.js';
import { ALL, closeTopic, configure, go, listen, resolve } from './core/router.js';
import { snapshot, subscribe, update } from './core/store.js';
import { confirmLeave } from './edit/markdown-editor.js';
import { openNew } from './edit/new-idea.js';
import { inboxCount } from './inbox/count.js';
import { watchInbox } from './inbox/watch.js';
import { nextLanguage, pick, setLanguage, t } from './model/words.js';
import { afterPanel, bindPanel, closePanel, panelMarkup, syncPanel } from './panel/panel.js';
import { navigator } from './ui/batch-nav.js';
import { bottomBar } from './ui/bottombar.js';
import { bindScroll, crumbs, notice, stats, title } from './ui/header.js';
import { show } from './ui/host.js';
import { bindKeyNotice } from './ui/key-notice.js';
import { menu, trigger } from './ui/picker.js';
import { heard, languageButton, navigation, projectSide } from './ui/sidebar.js';
import { dot, pill } from './ui/writer.js';
import { bindWriter } from './ui/writer-events.js';
import { batchMode } from './views/batch-head.js';
import { topicIds } from './views/help-topics.js';
import { ids, overviewIds } from './views/registry.js';

const RETRY_MS = 5000;

function drawFrame(state) {
  paint($('#project-side'), projectSide(state));
  paint($('#views-label'), t('nav.views'));
  paint($('#crumbs'), crumbs(state));
  paint($('#side-nav'), navigation(state));
  paint($('#writer-side'), pill(state));
  paint($('#sync-label'), t('nav.sync'));
  $('#sync-label').hidden = !$('#writer-side').firstElementChild;
  paint($('#writer-phone'), dot(state));
  paint($('#heard'), heard(state));
  paint($('#lang'), languageButton());
  paint($('#project-phone'), [trigger(state, 'pbtn'), menu(state)]);
  paint($('#title'), title(state));
  paint($('#stats'), stats(state));
  paintNav(state);
  paintMode(state);
  paint($('#bottom-nav'), bottomBar(state));
  paint($('#new'), t('new.button'));
  $('#new').hidden = state.project === ALL || !state.data;
  paintTitle(state);
}

// The tab's title: "(3) chantier board" while something needs the user.
function paintTitle(state) {
  const n = inboxCount(state);
  const text = n ? `(${n}) chantier board` : 'chantier board';
  if (document.title !== text) document.title = text;
}

// The batch navigator, hidden where the page has none.
function paintNav(state) {
  const nav = $('#batch-nav');
  const markup = navigator(state);
  nav.setAttribute('aria-label', t('batchnav.label'));
  paint(nav, markup);
  nav.hidden = !markup;
}

// The Batch page's mode and legend, in the title row, hidden where the page has none.
function paintMode(state) {
  const slot = $('#batch-mode');
  const markup = batchMode(state);
  paint(slot, markup);
  slot.hidden = !markup;
}

function drawNotice(state) {
  const text = notice(state);
  const element = $('#notice');
  paint(element, text);
  element.hidden = !text;
}

let shownKey = null;

function draw(state) {
  const key = `${state.project}|${state.view}`;
  if (key !== shownKey) $('.main').scrollTop = 0;
  shownKey = key;
  drawFrame(state);
  drawNotice(state);
  show($('#view'), state);
  const panel = $('#panel');
  paint(panel, panelMarkup(state));
  panel.classList.toggle('open', Boolean(state.panel));
  panel.inert = !state.panel;
  $('#backdrop').classList.toggle('open', Boolean(state.panel));
  afterPanel(panel, state);
  syncPanel(state);
}

// A move away from an open editor asks first when the text would be lost.
const guarded = (action) => async (event, el) => {
  if (await confirmLeave()) action(event, el);
};

const goOnClick = (body, selector, place) =>
  delegate(
    body,
    'click',
    selector,
    guarded((_, el) => go(place(el))),
  );

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
      const toAll = el.dataset.project === ALL && !overviewIds().includes(snapshot().view);
      go(toAll ? { project: ALL, view: overviewIds()[0] } : { project: el.dataset.project });
    }),
  );
  goOnClick(body, '[data-batch-go]', (el) => ({ batch: el.dataset.batchGo || null }));
  goOnClick(body, '[data-tab]', (el) => ({ tab: el.dataset.tab }));
  delegate(
    body,
    'click',
    '[data-close]',
    guarded(() => closePanel()),
  );
  // a click on the dimmed page closes the panel, as Escape does: an unsaved edit asks first
  $('#backdrop').addEventListener('click', () => {
    confirmLeave().then((ok) => ok && closePanel());
  });
  delegate(body, 'click', '[data-new]', () => openNew());
  bindPanel($('#panel'));
  bindWriter(body);
  bindKeyNotice(body);
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
  const { menu: open, panel, journalOpen, selection, helpTopic } = snapshot();
  if (open) update({ menu: false });
  else if (journalOpen) update({ journalOpen: false });
  else if (selection.length) update({ selection: [] });
  else if (panel) confirmLeave().then((ok) => ok && closePanel());
  else if (helpTopic) closeTopic();
}

// Read the board (`board.get`) until the server answers; the refresh takes over once a project is
// shown.
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
configure(ids(), overviewIds(), topicIds());
listenToFrame();
bindScroll($('.main'), $('#head'));
subscribe(draw);
watchInbox();
draw(snapshot());
boot();
