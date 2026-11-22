// What the board's Griller shows: the notice before the first message, the turns, and the two
// sentences kept under the conversation. Pure markup from the topic's value; no storage, no
// transport. The typed text is plain text, the answer goes through the panel's Markdown renderer.
import { html } from '../core/dom.js';
import { t } from '../model/words.js';
import { renderMarkdown } from './markdown.js';

// The server's command, named once: the day it is renamed this is the one line to change.
export const BOARD_COMMAND = 'chantier board';

const shared = () => html`<p class="gnote">${t('griller.shared')}</p>`;
const warning = () => html`<p class="gnote">${t('griller.http', { command: BOARD_COMMAND })}</p>`;

// The files a turn wrote, as words; the cut turn says so.
function wroteLine(turn) {
  if (!turn.wrote?.length) return '';
  const key = turn.state === 'done' ? 'griller.wrote' : 'griller.wrote_cut';
  return html`<p class="info">${t(key, { files: turn.wrote.join(', ') })}</p>`;
}

const ENDS = { stopped: 'griller.stopped', 'timed-out': 'griller.cut', failed: 'griller.failed' };

// A turn's answer, or the one line that says how it ended.
function answerOf(turn) {
  if (turn.state === 'running') {
    return html`<p class="info" role="status">${t('griller.working')}</p>`;
  }
  if (turn.state === 'done') return renderMarkdown(turn.answer ?? '');
  return html`<p class="info">${turn.error ?? t(ENDS[turn.state] ?? 'griller.failed')}</p>`;
}

// One turn: the typed text, then the answer, each on its own fill.
export function turnMarkup(turn, me) {
  const other = turn.from === me ? '' : html`<span class="lbl">${t('griller.other')}</span>`;
  const grilled = turn.grilled
    ? html`<p class="info">${t('griller.grilled', { destination: turn.grilled })}</p>`
    : '';
  return html`<div class="gturn gsaid" data-turn="${turn.n}">${other}<p class="gtyped">${turn.user}</p></div><div class="gturn ganswer">${answerOf(turn)}${wroteLine(turn)}${grilled}</div>`;
}

// The notice of the first message: the CLI, the machine and the model the server names.
const notice = (g) =>
  html`<p class="gnote">${t('griller.notice', { cli: g.cli, machine: g.machine, model: g.model })}</p>`;

// The discussion for the topic's value `g` (null while it is read), as seen from client `me`.
export function discussion(g, me) {
  if (!g) return html`<p class="info">${t('griller.loading')}</p>`;
  if (!g.available) return html`<p class="info">${g.reason}</p>${shared()}${warning()}`;
  const turns = g.conversation?.turns ?? [];
  if (!turns.length) return html`${notice(g)}${shared()}${warning()}`;
  return html`${turns.map((turn) => turnMarkup(turn, me))}${shared()}${warning()}`;
}
