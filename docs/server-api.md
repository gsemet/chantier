# The server's API, protocol 1

`chantier board` serves one published API, and a folder of static files (by default the web
board). The web board is one client of it; a script, an editor
or a phone app is another. The API has two bindings of the same protocol: a **WebSocket**
(`/api/v1/ws`), and **HTTP** (`POST /api/v1/call/<op>`, `POST /api/v1/poll`), for a network where
a WebSocket does not pass, behind a proxy for instance. HTTP is not a fallback of the server: it
is the same ops and the same topics, with a long-poll in place of the push.

The schema of record is [`protocol.json`](../skills/chantier/scripts/cli/src/chantier/board/api/protocol.json),
the JSON Schema of every frame and of every op's and topic's arguments. `just protocol-schema`
rebuilds it from the code's models, and a test refuses a file that is not that output. This page
says what the schema cannot: the rules and the `data` of each answer.

## The key

The server's key is in the link the Chief of Staff gives you (`?k=<key>`). The API takes it from:

- a header, `X-Chantier-Board-Key: <key>`: from any origin, for any client;
- the cookie the web page keeps, **only from the server's own origin** (no `Origin`, or the
  server's own, and `Sec-Fetch-Site` absent or `same-origin`): the cookie of a page served by
  another site is refused, so such a page cannot ride on your browser's cookie;
- for a WebSocket, the `key` field of the first frame, `hello`.

No key, a wrong one, or a cookie from another origin: HTTP 401, and on a WebSocket the error
`key` and the close code 4401. A body is `application/json` (415 otherwise).

Every answer allows any origin (`Access-Control-Allow-Origin: *`), never credentials, and
`OPTIONS` passes before the key check, so a page served elsewhere can call the API with the key in
a header. Behind a proxy that sets `X-Forwarded-Host`, the server's own origin is that host.

`GET /api/board` stays outside the protocol, as the probe a client finds a board with: it
answers `board`, `version`, `pid`, `served`, `surface` and `protocols` (the list of protocol
numbers the server speaks, `[1]` today).

## The frames

Every frame is a JSON object with a `t`. All times (`now`) are ISO 8601 UTC.

From the client:

| `t` | Fields | Meaning |
| --- | --- | --- |
| `hello` | `protocol` (1), `client` (a name, 100 characters at most), `key` (when no header or cookie carried it) | The first frame, within 5 s. Unknown fields are ignored, so a newer client may say more. |
| `call` | `id`, `op`, `args` | Run an op. `id` is yours (64 characters at most), unique among your open calls. |
| `sub` | `id`, `topic`, `args` | Watch a topic. The first event comes at once. |
| `unsub` | `id` | Stop watching what `sub` `id` asked. |

From the server:

| `t` | Fields | Meaning |
| --- | --- | --- |
| `welcome` | `protocol`, `server` (`version`, `pid`, `served`, `surface`), `ops`, `topics`, `now` | The answer to a good `hello`. |
| `result` | `id`, `ok`, `status`, `data`, `error`, `now` | The answer to a `call` (and to a refused `sub`). `status` is the HTTP status the op's HTTP binding would give; `error` is a sentence when `ok` is false. |
| `event` | `sub`, `topic`, `rev`, `data`, `now` | A watched value, when it changed (and once at first). |
| `tick` | `now` | Every 5 s, so a client sees a stalled link. |
| `error` | `code`, `error` | A fault of the connection; the server then closes it. Codes: `protocol`, `key`, `busy`, `frame` (a missed `hello` only closes, 4408). |

A frame of a kind the server does not know, or with a field it does not know (but `hello`'s),
is an `error` and the close 4400.

Close codes: 1001 the server stops, 1009 a frame over 4 MiB, 1013 the server is busy (a 65th
welcomed socket), 4400 bad frame, 4401 key, 4408 no `hello` within 5 s, 4426 protocol (a `hello`
whose `protocol` is not 1). A 17th socket still waiting for `hello` gets no close code: the upgrade
itself is refused, HTTP 503 `too many clients`. The server pings every 20 s.

## The ops

An op takes `args` (an object) and answers a `result`. Over HTTP, `POST /api/v1/call/<op>` takes
the same object as its body and answers `{ok, status, data, error?, now}` with `status` as the
HTTP status. An unknown op is 404, bad arguments 400, an unreadable project 500. The `project`
of an argument is the project's id, as `board.get` lists it. An argument not in the table is
refused (400).

| Op | Arguments | Data |
| --- | --- | --- |
| `board.get` | none | `board`, `version`, `surface`, `pid`, `served`, `served_origin`, `local_url`, `seats`, `projects`, `writer`, `protocols`, `now` |
| `project.state` | `project`, `rev`? | the project's state, with `rev` and `now`; with `rev` equal to the current one, `{"changed": false, "rev": ...}`. Each CR row of `batch.crs` has `lease`, and the batch `stack_lease`: `null` when the unit never had a lease, else `{n, renewed, expires, ended, holds, gate}`, facts only (`holds`: the running `lease hold`s of this lease; `gate`: `"gate running"`, `"gate queued"` or `null`); a client compares `expires` with `now` itself |
| `project.tree` | `project`, `path`? | `{path, files, now}`: the files and folders of the planning folder at `path` |
| `project.file` | `project`, `path` | a text file as `{text, cut, sha256}` (`cut` is true when the text was shortened); a binary file is 415 (read it over HTTP, below) |
| `costs.get` | `project` | `recorded`, `live`, `now` |
| `costs.recompute` | `project` | `202`: the recorded costs are being recomputed |
| `prs.get` | `project`, `batch`? | the batch's PRs as the forge says they are now (`all_done`, `closed`, the rows, `now`) |
| `seats.register` | `session`, `project`? | the seat of a session is recorded for the board |
| `backlog.new` | `project`, `text`, `slug`?, `title`? | the item filed in the inbox |
| `backlog.move` | `project`, `to`, `items`?, `group`? | the items moved to `to` (the inbox, a priority, `3-ready`) |
| `backlog.labels` | `project`, `items`, `add` | labels added to the items |
| `backlog.group` | `project`, `items`, `name` | the items put in a group |
| `backlog.ungroup` | `project`, `name` | the group dissolved |
| `backlog.file` | `project`, `item`, `path`, `text`, `base_sha256` | an item's Markdown file written; 409 when `base_sha256` is not the file's |
| `backlog.next_batch` | `project` | `next-batch.json` written from `3-ready` |
| `journal.get` | `project` | the board's journal, as `rescan` reads it |
| `journal.rescan` | `project` | the board's journal emptied |
| `config.get` | `project` | the configuration page's data: each role's agent, model and escalation, per host, the two limits, and the file's `sha256` |
| `config.put` | `project`, `changes`, `base_sha256`?, `dry_run`? | the configuration saved (or only checked, with `dry_run`); 409 when `base_sha256` is stale |
| `writer.sync` | none | the writer's state after one sync round |

The writes are the ones the web board always had, through the same role-free commands, and they
refuse what those refuse. Each backlog write appends its `board@1` line, and each `config.put`
its `config@1` lines, to the project's `forge-journal.jsonl`, as before.

Example, over HTTP:

```sh
curl -s -X POST http://127.0.0.1:8765/api/v1/call/costs.get \
  -H "X-Chantier-Board-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"project": "chantier"}'
```

```json
{"ok": true, "status": 200, "data": {"recorded": {}, "live": {}, "now": "2026-11-20T10:00:00Z"}, "now": "2026-11-20T10:00:00Z"}
```

A file of a project, binary or not, is also `GET /api/v1/projects/<project>/file?path=<path>`,
served with its own type (an image, for the web page's `<img>`).

## The topics

A topic is a value the server watches and pushes when it changes. Each event carries `rev`, a
token of the value: equal revs, equal values. The server looks every 2 s, and only at what a
client watches.

| Topic | Arguments | `data` of an event |
| --- | --- | --- |
| `board` | none | what `board.get` gives |
| `project` | `project` | what `project.state` gives |
| `costs` | `project` | what `costs.get` gives |
| `prs` | `project`, `batch`? | what `prs.get` gives; the forge is read at most once every 10 s per project and batch |
| `journal` | `project` | what `journal.get` gives |
| `events` | `project`, `after`? | `{"lines": [...]}`: the new lines of the project's `forge-journal.jsonl`, 200 at most, each with its `seq`, and `text`, its type's sentence, when the type is published and its payload accepted (no `text` otherwise); that `text` replaces, in the answer only, a payload's own `text` key (`board@1`, `issue@1`, `sync-*@1`), which the sentence quotes and the journal file keeps; with no `after`, the lines after the last one at the time of `sub` |

A `sub` for an unknown topic is a `result` with 404, for bad arguments 400, for an unknown
project 404, and the 33rd subscription of a connection 429.

Example, over a WebSocket (`>` is sent, `<` is received):

```text
> {"t": "hello", "protocol": 1, "client": "my-script", "key": "<key>"}
< {"t": "welcome", "protocol": 1, "server": {...}, "ops": [...], "topics": [...], "now": "..."}
> {"t": "sub", "id": "s1", "topic": "project", "args": {"project": "chantier"}}
< {"t": "event", "sub": "s1", "topic": "project", "rev": "9f2c...", "data": {...}, "now": "..."}
> {"t": "call", "id": "c1", "op": "backlog.move", "args": {"project": "chantier", "to": "P2", "items": ["an-idea"]}}
< {"t": "result", "id": "c1", "ok": true, "status": 200, "data": {...}, "error": null, "now": "..."}
```

## The long-poll

`POST /api/v1/poll` is the push for a client with no WebSocket. The body lists at most 32 subs:

```json
{"subs": [{"key": "p", "topic": "project", "args": {"project": "chantier"}, "rev": "9f2c..."}]}
```

`key` is yours, to tell the events apart; `rev` is the last one you saw (null for none). The
server answers at once with an event for each sub whose value is not at `rev`, and otherwise
holds the request for 20 s (under a proxy's usual idle limit) for a change, then answers
`{"events": [{"key", "topic", "rev", "data", "now"}...], "now": ...}`, with no event after a quiet
hold. Poll again with the revs you were given. Past 16 long-polls held at once, the server
answers 429 at once.

## Limits

| What | Limit | Beyond |
| --- | --- | --- |
| A frame, or an HTTP body | 4 MiB | close 1009 (HTTP 413) |
| Subscriptions of a connection, subs of a poll | 32 | 429 |
| Long-polls held at once | 16 | 429 |
| WebSockets past `welcome` | 64 | close 1013 |
| WebSockets before `hello` | 16 | HTTP 503 at the upgrade |
| Time to say `hello` | 5 s | close 4408 |

## Behind a proxy

Pass the upgrade (`Upgrade` and `Connection` headers, HTTP/1.1) for the WebSocket, and set
`X-Forwarded-Host` to the host the browser used, so the server's own origin is the page's. The
long-poll holds 20 s: keep the proxy's read timeout above that (nginx's `proxy_read_timeout`
defaults to 60 s). For a client that cannot upgrade, use the HTTP binding; nothing else changes.
The server speaks plain HTTP: put TLS on the proxy, and keep the key out of logs.

## Serving another UI

`chantier board` serves a folder of static files at `/`: the shipped web client by default, your
own with `--ui <folder>`, none with `--ui none`. The shipped client's folder
(`skills/chantier/scripts/cli/src/chantier/clients/web/`) is the example of such a folder.

- `chantier board --ui <folder>` serves that folder's files, `index.html` for `/`, behind the same
  key: the link's `?k=` sets the cookie, and the page then calls the API from the same origin
  (the cookie counts there, as the key section says). The folder must hold an `index.html`, or the
  command refuses to start (the usage exit, 1).
- The server sends only files of the folder, by the types it knows: `.html`, `.js`, `.css`,
  `.svg`, `.json`, `.ico`, `.png`, `.woff2`; any other answers 404 (a type is added only when a
  real UI needs it). Each answer carries `Cache-Control: no-cache` and an `ETag`. An HTML page
  carries the server's Content Security Policy (`default-src 'none'; script-src 'self'; style-src
  'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; ...`): no inline script or
  style, nothing loaded from another origin, the API on the same origin only.
- Its addresses must be relative to stay working behind a proxy with a path prefix (the proxy
  rules below hold for any served folder).
- `--ui none`: the API only; `/` answers 404 with the line `this server serves no UI: see
  docs/server-api.md`. A UI served elsewhere (another origin) or a native app uses the key in a
  header or in the WebSocket's first message, as the key section says; it needs no `--ui`.
- A board already running keeps what it was started with: `--ui` on a second `chantier board`
  prints `--ui not applied: a board already serves this surface; stop it to change what it
  serves`, and nothing else changes.

## A terminal client

`chantier live` is the API's second client: a read-only terminal view of a running board (the
counts, the projects and Drivers, the flow of events, the tasks with their lease time left). It
sends `hello`, `sub`, `unsub` and the poll, and nothing else, over the WebSocket first and the
HTTP long-poll when the WebSocket does not open. Its package,
[`clients/tui/`](../skills/chantier/scripts/cli/src/chantier/clients/tui/), is the example of a
client in Python: it imports nothing of chantier but itself, the version and the error type, so
everything it shows comes through this API. See [boards.md](boards.md#the-live-terminal-view).

## Versions

The protocol is numbered; this page is protocol 1. A change that only adds (an op, a topic, a
field of a `data`, an optional argument) stays protocol 1: a client ignores the fields it does
not know. A removal or a change of meaning is protocol 2. A `hello` with another protocol number is the error `protocol` and the
close 4426, and `/api/board`'s `protocols` lists what the server speaks.
