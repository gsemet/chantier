// The HTTP binding's link: one op as a POST to `api/v1/call/<op>`, and the long-poll `api/v1/poll`
// that stands for the subscriptions when the socket cannot open. Only `transport.js` uses it.
const RETRY_MS = 5000;
const OPTIONS = { cache: 'no-store', credentials: 'same-origin' };
const HEADERS = { 'Content-Type': 'application/json' };

const post = (path, body, signal) =>
  fetch(path, { ...OPTIONS, method: 'POST', headers: HEADERS, body: JSON.stringify(body), signal });

// One op: `{ ok, status, data, error, now }`, a refusal included. Only the network throws.
export async function httpCall(op, args) {
  const res = await post(`api/v1/call/${op}`, args);
  const body = await res.json().catch(() => ({}));
  const error = res.ok ? null : (body.error ?? `the board answered ${res.status}`);
  return { ok: res.ok, status: res.status, data: body.data ?? null, error, now: body.now };
}

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Poll for `subs` (a Map of id to { topic, args, rev }): one request at a time, at once again after
// each answer, after 5 s after a failure. `hooks`: `deliver(sub, event)`, `touch(now)`,
// `miss(denied)`. It returns `{ kick }` (the subscriptions changed).
export function startPoll(subs, hooks) {
  let abort = null;
  let wake = null;
  const wanted = () =>
    [...subs.entries()].map(([key, s]) => ({ key, topic: s.topic, args: s.args, rev: s.rev }));

  async function round() {
    const list = wanted();
    if (!list.length) return new Promise((resolve) => (wake = resolve));
    abort = new AbortController();
    const res = await post('api/v1/poll', { subs: list }, abort.signal);
    const body = await res.json().catch(() => ({}));
    if (!res.ok)
      throw Object.assign(new Error(`the board answered ${res.status}`), { status: res.status });
    hooks.touch(body.now);
    for (const event of body.events ?? []) {
      const sub = subs.get(event.key);
      if (sub) hooks.deliver(sub, event);
    }
    return null;
  }

  async function loop() {
    for (;;) {
      try {
        await round();
      } catch (error) {
        if (error.name === 'AbortError') continue;
        hooks.miss(error.status === 401);
        await pause(RETRY_MS);
      }
    }
  }
  loop();
  return {
    kick() {
      wake?.();
      wake = null;
      abort?.abort();
    },
  };
}
