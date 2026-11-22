// The board's Griller, one function per op of the server and the topic's feed. A refusal comes back
// as a `GrillerError` carrying the server's one line and its status. The client id marks the turns
// this page sends (`from`): it is made once per tab and kept in `sessionStorage`, so a reload keeps it.
import { post, read } from '../core/api.js';
import { subscribe } from '../core/transport.js';

export class GrillerError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

const ID_KEY = 'chantier.client';
const ID_LENGTH = 24;

// This page's id; a browser that keeps nothing gets one for the page's life.
let memory = null;
export function clientId() {
  try {
    let id = sessionStorage.getItem(ID_KEY);
    if (!id) {
      id = crypto.randomUUID().replaceAll('-', '').slice(0, ID_LENGTH);
      sessionStorage.setItem(ID_KEY, id);
    }
    return id;
  } catch {
    memory ??= crypto.randomUUID().replaceAll('-', '').slice(0, ID_LENGTH);
    return memory;
  }
}

async function act(op, args) {
  const { ok, status, data } = await post(op, args);
  if (ok) return data;
  throw new GrillerError(data?.error ?? `the board answered ${status}`, status);
}

// The item's Griller as the server says it now (the topic gives the same value).
export const getGriller = async (project, item) =>
  (await read('griller.get', { project, item })).data;

export const sendMessage = (project, item, text) =>
  act('griller.send', { project, item, text, from: clientId() });

export const stopTurn = (project, item) => act('griller.stop', { project, item });

export const endConversation = (project, item) => act('griller.end', { project, item });

// Watch the `griller` topic of one item; returns the function that stops watching.
export const watchGriller = (project, item, onEvent, onFail) =>
  subscribe('griller', { project, item }, onEvent, onFail);
