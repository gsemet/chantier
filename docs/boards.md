# Boards

The CR board in Claude Code, a read-only pane over the planning folder, and the web board ([its own page](web-board.md)), served by `chantier board` on this machine, or to any device on the local network when you open it.

## The CR board (Claude Code)

### What it is

A Claude Code mod (early access): a read-only pane over the planning folder's `STATUS.json` (in a surface,
the projects whose seat or current batch, as its Foreman or Chief of Staff, names this session, else
every project under a line saying no seat names it). It shows the live batches, the backlog (and `3-ready`), and the
merged and trashed CRs. Nothing of it on Copilot, and the pane is not shown in a Remote Control view
([anthropics/claude-code#99217](https://github.com/anthropics/claude-code/issues/99217)). It writes
nothing and runs no process but `git rev-parse`, to find the main checkout from a worktree.

### How to open it

`/chantier-board` shows or hides it. Loading the `chantier` or `chief-of-staff` skill opens it too
(not `griller`).

### How to read it

At the top, a header line: `5 live · 0 waiting for you · checked 3s ago, every 15 s`: when the pane last checked, and its period. Under it, each batch has a
line (its id, its cost against its budget, a gauge, and how old that cost is: `12 min old`), its unread asks, its slots and its shape (`Slots 3/3, 0
free · parallel`). Then "Waiting for you" and "In progress", with the columns CR, Subject, State, Step, PR and Cost. The Step is what a working CR's Driver is doing (`coder r2`, `gate scenario`, `CI`), or "waits for the user" on a blocked one; the web board also marks the next CR to start.
The state says the state, the step and the round: `working Round 1/3`, `working CI 2/3`,
`🟢 ready to merge Notify 1/3`, `🟤 PR in draft, waits for …`, `🟣 ready locally Notify 1/3`, `queued`. Then Backlog, Merged (n of m) and Trashed (n of m). Press a CR for its
sheet and its documents. The pane checks every 15 seconds while open and reads a file again only when it changed. A **Refresh** button at the top of the pane (in every view) checks at once: it reads the files again, even unchanged ones, and looks for the planning folders again (a project added to a surface, a `.agents/changes/` created after opening), and for the projects that name this session again (a seat taken after opening; the 15 s check looks too), keeping the page shown and the folds. It does not refresh the batch's cost or record: that moves when the steering session refreshes the status.

### A batch in pictures

A batch just opened: three CRs working in round 1/3, two queued, no PR yet, no cost.

![The board, a batch just opened](board-mod-batch.png)

Three CRs in CI, with PRs #1 to #3 and their costs: $0.57 of $20.

![The board, three CRs in CI with their PRs](board-mod-batch-prs-light.png)

"3 waiting for you": two CRs ready to merge, and one unread ask.

![The board, three things waiting for you](board-mod-waiting-light.png)

"Merged (2 of 2)" open.

![The board, the merged CRs](board-mod-merged-light.png)

The batch done: 0 live, $9.22 of $20, and "Merged (5 of 5)" with each CR's PR and cost.

![The board, the batch done](board-mod-batch-done.png)

### Two facts the pictures raise

They are not bugs.

- The header's "waiting for you" counts the unread asks as well as the table's rows: in the
  merged picture, "1 waiting for you" sits beside "Nothing waits for you".
- The batch's cost is priced when the steering session refreshes the status, not live: $0.57 over
  three pictures while the CRs moved on, then $9.22 once the batch was done.

### The guard of a worker's and a CR Driver's writes

The same mod starts an agent whose prompt holds a `writes:` line in its first folder (a worker's:
its worktree; a CR Driver's: its worktree, or the project's root before the worktree exists) and refuses its Write, Edit or NotebookEdit outside the
folders named. It judges the agent's Bash or PowerShell writes the same way when it can see them (a
redirection, `Set-Content`, `sed -i`, `rm`...); what it cannot see, such as an interpreter's inline
code, is covered by the cards, and the steering session reports what changed in the main checkout.

## The web board

The web board is a small web server, `chantier board`, for any device. Every view, how to start it, keep it on the machine and stop it are in [the web board](web-board.md); its API, which the page and any other client use, is in [the server's API](server-api.md).

## The live terminal view

`chantier live` watches one to four running boards in the terminal, read-only: the second client
of [the server's API](server-api.md), beside the web page. It never starts a board, writes nothing
and messages no agent. Its keys only change what its own screen shows.

What it shows, redrawn once a second:

- the header: the folder served, the board's version, the transport (`ws` or `http`), the link's
  state (`live`, or `reconnecting since HH:MM:SS`), the server's time, and four counts: working,
  ready (to review), held (blocked), done (merged);
- on the left (from 100 columns): each project watched with its batch and its backlog, and one
  line per unit an agent holds (`Driver <cr> <phase>`, `Stack driver`);
- in the centre, the flow: the record's events and the journal's lines of every project
  watched, newest at the bottom; it keeps the last 2000 lines of each board, merged by time;
- on the right, the tasks: the working CRs with their round and their lease's time left (from the
  server's clock, so a machine with a wrong clock shows the right time), then the CRs to review
  with their age, then the blocked ones with their reason.

With several boards the boards are labelled `a` to `d`, in the order of their `--url`: the header
has one line per board (`<label>  <address>  <folder>  v<version>  <transport> <link state>`), the
counts are summed, a project is named `<label>/<project>` and a task's CR reads `<label> <CR>`.

How to start it:

- `chantier live`: the board recorded as running for this surface or project, on the loopback
  address. With none: `live: no board runs for this surface: start one with chantier board, or
  pass --url <link>` (exit 4).
- `chantier live --url <link>`: a board on another machine, from the link it printed (with its
  `?k=` key); the environment's proxies apply. `--url` is repeatable: one to four boards, one key
  and one connection each. A fifth, or the same board twice, is refused at start (two spellings of
  one host, `localhost` and `127.0.0.1`, are not detected). The recorded board joins others only
  by its own link.
- `--only <project>` (repeatable) watches those projects only; without it, every project, the
  first 15 of each board. `--transport auto|ws|http`: the WebSocket first, else the HTTP
  long-poll, or one only. Both apply to every board. A lost link is tried again every 5 s while
  the other boards go on; a refused key on any board exits 4 with the server's sentence and that
  board's address (never its key).
- `--once` prints the screen once as plain text and exits, once every board has answered: for a
  script, a test or a bug report. It reads no key. Without it, a stdout that is not a terminal is
  refused. `q` or Ctrl-C leaves the screen.

Keys:

| Key | Effect |
|---|---|
| Up / Down | the Flow one line older / newer |
| PgUp / PgDn | the Flow one page older / newer |
| Home | the oldest kept line of the merged Flow |
| End | back to the live end (follows again) |
| `/` | type a filter: characters add, Backspace removes, Enter applies (empty clears), Esc cancels |
| `?` | show the keys over the screen; any key closes them |
| Esc | clear the filter; leave the help |
| `q`, Ctrl-C | quit, exit 0 |

- Only the Flow scrolls. Scrolled back, it does not move when lines arrive and its title reads
  `Flow  paused, <n> new`, until End, or Down or PgDn reaching the newest line, follows live again.
- The filter is one text, matched without case against a Flow line's board label, project, CR,
  who and text, and a task's board label, project, CR, title and phase. It narrows the Flow and
  the Tasks, not the left column nor the counts, and the footer says `filter: <text>`. It is
  local: nothing more is asked of the server (`--only` watches fewer projects).
- With no keyboard (the input is not a terminal), there are no keys and the footer reads
  `Ctrl-C to quit`; the screen runs as before.
- The terminal is given back on every way out (`q`, Ctrl-C, a refused key, an error, SIGTERM on
  POSIX) but a killed process (SIGKILL, a closed terminal window), which cannot.

One `--once` capture, on a board over a small scratch project, a running batch whose first CR is
taken (its lease live) and the second not yet (120 columns):

```text
chantier live  /tmp/live-demo/demo/.agents/changes  v0.14.0  ws  live  23:54:56 U…
working 1  ready 0  held 0  done 0
┌─ Projects ───────────────┐┌─ Flow ───────────────────────────────────────┐┌─ Tasks ──────────────────────────────────┐
│ demo  batch-01 running … ││ 23:54:48 chief-of-… add CR-101               ││ CR-101    Export the report as CSV       │
│   inbox 0 backlog 0 rea… ││ 23:54:48 chief-of-… add CR-102               ││           lease 09:55  round 0/3         │
│                          ││ 23:54:48 chief-of-… open                     ││                                          │
│ Agents                   ││ 23:54:52 foreman    take CR-101              ││                                          │
│ Driver CR-101            ││                                              ││                                          │
└──────────────────────────┘└──────────────────────────────────────────────┘└──────────────────────────────────────────┘
Ctrl-C to quit
```
