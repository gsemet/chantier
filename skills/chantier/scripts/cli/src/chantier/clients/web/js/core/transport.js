// The page's one door to the server: `call` an op, `subscribe` to a topic, `fileUrl`. It opens
// the WebSocket (`ws-link.js`) and, when that cannot open, falls to the HTTP binding (`http-link.js`)
// for the rest of the page's life; `?transport=http` forces it. It tells the store what it hears
// (`now`, `minute`, `heard`, `fails`, `denied`, `mode`, `upgraded`). Nothing else in the page
// opens a socket or names an `api/` address.

import { httpCall, startPoll } from './http-link.js';
import { snapshot, update } from './store.js';
import { openSocket } from './ws-link.js';

export class AskError extends Error {
  constructor(status) {
    super(`the board answered ${status}`);
    this.status = status;
  }
}

const MINUTE_MS = 60000;
const BACKOFF_MS = [1000, 2000, 4000, 8000, 16000, 30000];
const DENIED = 4401; // the server refused the key
const UPGRADED = 4426; // the server speaks another protocol: reload the page

const subs = new Map(); // id -> { topic, args, onEvent, onFail, rev, sent }
const pending = new Map(); // id of a call over the socket -> { resolve, reject }
let socket = null;
let poll = null;
let started = null;
let wasLive = false;
let counter = 0;

const minuteOf = (iso) => Math.floor(Date.parse(iso) / MINUTE_MS) || 0;

// A frame came: the clock, and "heard just now".
function touch(now) {
  const at = now ?? snapshot().now;
  update({ now: at, minute: minuteOf(at), heard: Date.now(), fails: 0, denied: false });
}

const miss = (denied = false) => update({ fails: snapshot().fails + 1, denied });

function deliver(sub, event) {
  sub.rev = event.rev;
  sub.onEvent(event.data, event.rev);
}

function onFrame(frame) {
  if (frame.t === 'result') {
    pending.get(frame.id)?.resolve(frame);
    pending.delete(frame.id);
    return;
  }
  touch(frame.now);
  const sub = frame.t === 'event' ? subs.get(frame.sub) : null;
  if (sub) deliver(sub, frame);
}

function ask(frame) {
  return new Promise((resolve, reject) => {
    pending.set(frame.id, { resolve, reject });
    socket.send(JSON.stringify(frame));
  });
}

function attach(id, sub) {
  sub.sent = true;
  ask({ t: 'sub', id, topic: sub.topic, args: sub.args })
    .then((result) => result.ok || sub.onFail?.(result.error))
    .catch(() => {});
}

function dropped(event) {
  socket = null;
  for (const sub of subs.values()) sub.sent = false;
  for (const { reject } of pending.values()) reject(new Error('the socket closed'));
  pending.clear();
  if (!refused(event.code)) later(0);
}

// A close that no retry mends: the key, or the protocol.
function refused(code) {
  if (code === DENIED) update({ denied: true });
  else if (code === UPGRADED) update({ upgraded: true });
  return code === DENIED || code === UPGRADED;
}

function later(step) {
  const wait = BACKOFF_MS[Math.min(step, BACKOFF_MS.length - 1)];
  setTimeout(() => dial(step + 1), wait);
}

function http() {
  update({ mode: 'http' });
  poll = startPoll(subs, { deliver, touch, miss });
}

async function dial(step) {
  let opened;
  try {
    opened = await openSocket(onFrame, dropped);
  } catch (event) {
    if (refused(event?.code)) return;
    if (!wasLive) return http(); // never welcomed: HTTP for the rest of the page's life
    miss(); // a reconnect that failed
    return later(step);
  }
  socket = opened.ws;
  wasLive = true;
  touch(opened.now);
  for (const [id, sub] of subs) attach(id, sub);
}

const forcedHttp = () => new URLSearchParams(location.search).get('transport') === 'http';

// Open the connection; every `call` and `subscribe` waits for the first attempt to settle.
export function connect() {
  started ??= forcedHttp() ? Promise.resolve(http()) : dial(0);
  return started;
}

// One op. Resolves `{ ok, status, data, error, now }` even for a refusal; only a failure of the
// network, or a socket closed under the call, rejects.
export async function call(op, args = {}) {
  await connect();
  if (!socket) {
    const answer = await httpCall(op, args);
    if (answer.status === 401) update({ denied: true });
    return answer;
  }
  counter += 1;
  return ask({ t: 'call', id: `c${counter}`, op, args });
}

// Watch a topic: `onEvent(data, rev)` gets its whole value at once and at each change; `onFail(error)`
// the refusal of the subscription. It returns the function that stops watching.
export function subscribe(topic, args, onEvent, onFail = null) {
  counter += 1;
  const id = `s${counter}`;
  const sub = { topic, args, onEvent, onFail, rev: null, sent: false };
  subs.set(id, sub);
  connect().then(() => {
    if (!subs.has(id) || sub.sent) return;
    if (socket) attach(id, sub);
    else poll?.kick();
  });
  return () => {
    if (!subs.delete(id)) return;
    if (socket && sub.sent) socket.send(JSON.stringify({ t: 'unsub', id }));
    else poll?.kick();
  };
}

// Where a file is served from: an image's `src`, or a download link's `href`.
export const fileUrl = (project, path) =>
  `api/v1/projects/${encodeURIComponent(project)}/file?path=${encodeURIComponent(path)}`;
