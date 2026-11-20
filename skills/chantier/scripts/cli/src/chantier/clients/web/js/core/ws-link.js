// The WebSocket binding's link: open the socket to `api/v1/ws` (relative to the page), say hello
// and wait for the welcome. Only `transport.js` uses it; it keeps no state of its own.
export const PROTOCOL = 1;
const HELLO_WAIT_MS = 5000;
const CLIENT = 'chantier-web';

// The socket's address: the page's own, `ws:` for an `http:` page and `wss:` for `https:`.
export function address() {
  const url = new URL('api/v1/ws', document.baseURI);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.href;
}

// Resolves `{ ws, now }` once the server's welcome came; rejects with the close event when the
// socket closed before it (or after the wait of 5 s). Later frames go to `onFrame`, the close to
// `onClose`.
export function openSocket(onFrame, onClose) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(address());
    let welcomed = false;
    const timer = setTimeout(() => ws.close(), HELLO_WAIT_MS);
    ws.onopen = () => ws.send(JSON.stringify({ t: 'hello', protocol: PROTOCOL, client: CLIENT }));
    ws.onmessage = (event) => {
      const frame = JSON.parse(event.data);
      if (welcomed) return onFrame(frame);
      if (frame.t !== 'welcome') return undefined;
      welcomed = true;
      clearTimeout(timer);
      return resolve({ ws, now: frame.now });
    };
    ws.onclose = (event) => {
      clearTimeout(timer);
      (welcomed ? onClose : reject)(event);
    };
  });
}
