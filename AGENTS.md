# AGENTS.md

- Run `just check` before you hand back; it must pass on Linux, macOS and Windows.
- Before a CR's first push, its Driver runs `just check` in the worktree, at the rebased head it
  pushes; for a change under the CLI's `src/` (`skills/chantier/scripts/cli/src/`) or the eval kit
  (`evals/kit/`) it also runs `just eval-dry-run` there. A cards-only change does not owe it.
- The long gate is the pipeline's `just scenario (ubuntu-latest)` job, green at the PR's head: a
  change to the CLI, the cards or the scenario passes it before its PR; a change to the docs or the
  eval kit alone needs none. Windows coverage: before a PR is called ready to merge, it also
  passes the long gate `scenario` locally (`chantier gate <cr> scenario`) at its head. In a
  parallel or series batch each PR the long gate covers owes this run, since each lands alone on
  main (a docs-only or eval-kit-only PR owes none). In a stack batch only the CR on top of the
  stack owes it, a docs-only top included, and when a CR joins on top the run moves to it. No
  Windows run covers the merged result; that is left to the pipeline's ubuntu job.
- A change to `hooks/` or `types/` passes `just mod` before its PR; the agent runs it itself, and
  one that cannot stops and says so, with no workaround.
- `main` is protected: work on a branch, open a PR, merge by rebase when CI is green.
- The plugin must work with no setup (a runnable long gate needs its `long_gate.commands` entry in
  the code repository's root `chantier.yaml`): the user's `AGENTS.md`, and optional `chantier.yaml` (or
  `chantier.yml`) files, at the project's root and, with an external planning surface, at the
  surface's root and in the project's folder there, are the only configuration, above the plugin's
  shipped `config/chantier.defaults.yml`; the user's profiles (`chantier login`), below, only say where a project's commands run (with none, chantier runs on the shipped defaults; `uv` is the only tool to install, and the CLI needs no network once uv's cache holds its
  packages, except the server's read of a batch's PRs, the forge hub, the surface server's writer, whose fetch and push need it, the board's Griller run (the host CLI's calls to its model), and the forge calls of `ship`, `take`, `round`, `handoff` and `forge-stack`, made with the user's own `gh` or `glab` (below), and a command run through a profile (`chantier login`), which reaches the profile's server), and chantier writes only in the planning folder (`.agents/changes/`, or the project's folder of an
  external planning surface), as plain JSON and Markdown, and the project's `chantier.yaml` in an
  external planning surface's project folder, from the board's Configuration page, and a CR's
  cleaned archive in its PR when the project asks for it, and fast-forwards a clean main checkout
  after a merge it records, the surface server keeps its two keys, and the user's profiles (`chantier login`, `logout`), in one file outside any project, `chantier/profiles.json` in the user's config folder (`$CHANTIER_CONFIG_HOME`, else `%APPDATA%` on Windows, else `$XDG_CONFIG_HOME` or `~/.config`), mode 0600; a profile applies only to the projects it was logged in for, and to none served by another surface on this machine, the host CLI that the board's Griller runs keeps its own
  session files, as for any session of the user, and while it serves its PID, address
  and version, and the forge hub's PID, version and last reads, in the repository's git folder
  (`chantier/server.json`, with its write lock `chantier/server.json.lock`; the hub's lock is
  `chantier/hub.lock`), and the surface server's writer commits, rebases and pushes the planning
  surface's published paths (`projects/` and the root `chantier.yaml`, never the surface's other
  files), rebases and pushes with them the local commits of the surface's branch made by hand, and
  keeps `chantier/writer.lock` and `chantier/writer.wake` in the git folder,
  each watcher's lock too (`chantier/watch-<project>/<session>.lock`: one per project and session
  that ran a watcher, held while it runs, empty, never removed),
  and removes the merged CRs' worktrees and
  branches at a batch's end (below), and,
  on the user's yes, the Chief of Staff adds to `~/.claude/settings.json` the allow rules preflight's P10 named, and nothing else
  there.
- `agents/` (Claude Code) and `com.github.copilot/agents/` (Copilot) are hand-written, one file
  per role and host: change a role on both hosts together; their bodies must stay identical.
- A role's contract lives in `skills/chantier/references/` (the cards), never in an agent file
  or in the CLI: the parent that starts an agent names the card in its prompt. A card says what
  the role judges; the CLI (`rails.py`) says what it refuses; a user's project rules rank above
  both. The CLI knows no role; two named exceptions: the cost code knows the two specification
  agents by their agent type (`spec-writer`, `spec-critic`), to put them on the grill line, and the surface
  server knows the board's Griller (`board-griller`), to start it with its brief and read its
  `[griller→board]` line (below).
- The CLI's scope: the CR lifecycle, the batch's frame (limits, record, STATUS files), the means
  to synchronise, and a few tools (among them `validate`, a read-only check of a planning folder
  that a surface would otherwise keep in its own drifting script). The agents do the work, git and the forge included, but for the forge calls named below; a new
  CLI tool comes from measured token-costly behaviour, never from speculation. Named
  exceptions. The end of a batch's last CR (`order merged`, `handback released`, `cancel`,
  `order drop`) removes the batch's merged CRs' worktrees and branches whose Driver has ended
  (`git worktree remove`, `git branch -D`, from the main checkout or the project's clone, with no
  `--force`), then pauses the batch; it does nothing else in git. The surface server, `chantier serve`: the web board's server, for the user on this machine and the local
  network, behind two keys, a private one that reads and acts and a public one that reads only (either in its
  URL for the web client, in a header or a WebSocket's first message for any other client): the
  public key opens an allow-list of reads and subscriptions and acts on nothing; every other op, a
  write of the backlog or the configuration included, needs the private key (the user's answer
  remote-cli-Q9, 2026-11-22), through one published API over a WebSocket, and over HTTP as the same
  protocol for a network where a WebSocket does not pass, behind a proxy for instance (not a
  fallback): two surfaces' servers on one machine never clash: each keeps its key and record in its own git
  folder, and one that finds the default port held (by another chantier board or any program) takes the next free port above it
  and prints it (the user's answer remote-cli-Q17, 2026-11-22); it serves the record and the planning folder's files (it alone reads the planning
  files for the live clients, told of changes by the system's file notifications (inotify,
  FSEvents, ReadDirectoryChangesW), or, on a system where none works, by a check every 5 s (the
  user's own decision of 2026-11-21, not a fallback), and publishes 1 s after the last change),
  and the web client's files (another folder's with
  `--ui <folder>`, none with `--ui none`), one client among others, and it
  edits the backlog (the inbox, `2-backlog/P1`...`P4`, `3-ready`: files and folder moves) and
  each role's agent, model and escalation, per host, and the two limits (`specifying.parallel`,
  `batch.slots`), in the project's configuration file in the planning
  surface (`projects/<name>/chantier.yaml`), only through the CLI's role-free commands and its
  own reading, checking and writing of that file, and the board's Griller's
  writes in one CR's folder; it never edits a batch and never messages an
  agent (the board's Griller, below, is not one); it never edits a batch itself, but for the fifth exception below, a client's command; one named exception, a batch's PRs: while a client asks for them (one read, or a subscription),
  at most once every 10 s per project and batch, while a PR of that batch is not done, a
  subscription's first read included (within the same 10 s), it reads the forge, read-only, through the
  connector of its forge, with the user's own `gh` or `glab`, on its own (no agent asks it), and
  needs the network for that, and a second, from the same read: when its forge read finds a PR of
  the batch in `4-batch/` merged that the record does not hold, it appends one line to
  `forge-journal.jsonl` (planning folder, never published), which
  `status` prints for the Chief of Staff to record at its next `status`; the
  board itself records nothing and messages no agent, but its writer's commits of the planning
  surface's published paths (below) and its journal lines (`sync-*@1`, `arrived@1`), and the commands its `cli.run` runs for a client, which record what they record when run locally, and the board's Griller (the
  fourth exception, which passes the words a holder of the private key typed to a run the server started for
  the key's holder, and is not a message of the board to an agent); a third, from a configuration save (the web client's Configuration page, or any client's `config.put`): a save
  appends one `config@1` line to the same journal (`source: board`) for each key whose effective value it
  changes (the two limits, and each role's agent, model and escalation), which `status` and the
  watcher carry to the Chief of Staff; and each write it makes to the backlog also appends one
  `board@1` line to that project's `forge-journal.jsonl`, which the Chief of Staff's watcher reads;
  a drop of a `3-ready` CR on the running batch writes no file in the CR's folder and appends
  only its journal lines (its `board@1` line, action `running-batch`, which the Chief of Staff
  turns into `order add`);
  a fourth, the board's Griller: on the request of any client holding the private key (this machine,
  or the local network when `board.host: network`), and on an item of the inbox, the backlog
  (`2-backlog/P1`...`P4`) or `3-ready` only (never a CR of `4-batch/`, an archive or the trash), the
  server starts the headless CLI of the host it runs under (`claude -p`; `copilot -p` only once a
  trial has proved the same limits; on a host not proved or not told, the Grill action refuses with
  one line), as the plugin's own `board-griller` agent only (any other agent set for that role
  refuses the Grill action with one line naming the setting) with the project's model for that role
  on that host, one run per message typed in the board, each run resuming the conversation of the run
  before, one shared conversation per CR that every holder of the private key reads and any holder may stop
  or end, at most one run per planning surface (per project's planning folder in-project) at a time
  and at most 10 minutes per run, and no process between two runs; the first run's prompt is a fixed
  brief that names the Griller card, the CR's folder and the CLI, followed by the typed text, and each
  later run's prompt is the typed text alone, passed unchanged; the run loads none of the user's,
  project's or local host settings (allow rules, hooks, MCP servers), loads chantier explicitly, and
  works from an allow list alone, which the role's skills and tools never widen: it may read the
  project, the planning folder and the plugin's skill folder (read-only), write only in that CR's
  folder, and run only the four `chantier` commands that the Griller card's "Started from the board"
  names, `summary lint` and `summary set` on that CR's folder only: no other shell command, no
  network tool (no web fetch or search, no shell beyond those four commands; the host CLI's own
  calls to its model aside), no MCP tool, no subagent; a host whose flags cannot give all of these
  limits gets no run; it grills as that card says, messages no session and runs no git command of
  its own; while a run works on an item, the board's own writes on that item (its moves, the trash
  and the running batch included, its file edits, labels and groups) are refused, and when another
  session moves the item during a run, the server stops the run and removes, at the old path, only
  the files that appeared there after the move; this is not the board messaging an agent: the
  server sends a run nothing of its own
  but that fixed brief, only the words a holder of the private key typed, to a run it started for the key's
  holder, and it sends nothing to any session (no Chief of Staff, Foreman, Driver or Griller
  session) and records nothing in a batch; when a run has written in that CR's folder, the server
  appends one `board@1` line (action `grill`) to the project's `forge-journal.jsonl` through the one
  append function, which the Chief of Staff's watcher carries; the server keeps the conversation in
  its memory only (the host CLI keeps its own session files, as for any session of the user),
  refuses with one line while the surface's writer is not running or stopped, and no agent starts
  it; the board speaks plain HTTP, so on the network the key and every turn's text travel in clear,
  and `chantier serve --new-key` replaces both keys; built on the user's direction of 2026-11-17 and
  answers "Tout" (2026-11-21) and board-griller-Q4 B and Q20, with no measured cost; a fifth, a client's command: for a client logged in with `chantier login`, the `cli.run` op runs one chantier command (any but `serve`, `webui`, `watch`, `live`, `login`, `logout` and `gate`) as a child process of the server's own build, never forwarded again, in its planning folder on the server's machine (its worktrees, transcripts and paths), with the client's arguments and its batch, host and session variables, behind the private key, and returns its output, its exit code and its launch form; that command edits the batch and the planning folder exactly as when run locally, but prints no watcher line; built on the user's answers remote-cli-Q2, Q5, Q10, Q12 and Q15 (2026-11-22), with no measured cost; it takes its
  dependencies like the rest of the CLI and knows no role but the board's Griller. The same process is the
  forge hub while it runs (one per planning surface and machine, started by a session's watcher,
  detached, when none runs and the session holds the seat, on the user's one yes for the watcher
  and the board, or by the Chief of Staff on a host that cannot run the watcher, or by
  `chantier webui` when none runs (the user's typing it is the yes; that server has no seat and
  stops by itself 30 minutes after its last client); one a watcher or `webui`
  started stops by itself when its seat leaves or 30 minutes after its last subscribed client,
  after its writer's last cycle): it holds the OS file lock in the git folder
  (`chantier/hub.lock`). The hub reads the forge, read-only, with the user's
  own `gh` or `glab`, on its own (no agent asks it), and needs the network for that: at most once
  every 20 s while at least one client is subscribed to the server (a board page, a session's
  watcher, `chantier live`), and not otherwise, but for a board started with `--forge-always` by
  the Chief of Staff on a host that cannot run the watcher, which reads it every 20 s with or
  without a client (the user's answer of 2026-11-21), through the connector of its forge (GitHub with `gh`, GitLab with `glab`), one
  query per project of the surface for which the interest registry holds a PR or MR, and only
  those: today, the PRs of a project's batch that runs, or is paused with open PRs, while one of
  them is not held merged or cancelled, and the PRs or MRs that the open approval, pipeline and
  merge waits of that batch's CRs name, in the same query; it appends to that project's
  `forge-journal.jsonl` (planning folder, never published) one line per merge the record does not
  hold, per CI turning red on a PR ready to merge and per wait of that batch's CR that the forge
  shows met (`wait-cleared@1`), and nothing else; each session's watcher, run for the Chief of Staff's
  whole session, with or without a batch, subscribes to the surface server's `events` topic for
  its project (the hub's lines, the board's, the writer's and an outside poller's `issue@1`
  lines), never reads the journal file or the forge, and starts the server, detached, when none
  runs and its session holds the seat, and, 20 s after the last new event for it that wakes and no
  sooner than `events.wake_every` after its start or its last telling, tells the events it
  gathered, which wakes its session: in its streaming form (`watch --stream`, which the CLI prints
  on a host whose reference runs it so) it prints them and runs on, else it ends; it ends when the
  project's seat is another session's, and, while no batch of the project runs and none is paused
  with a PR the record holds neither merged nor cancelled, 2 h after the latest of its start, its
  last event for it that wakes and the last moment such a batch ran or was paused so (so a watcher
  an ended session left behind stops once the seat moves, or 2 h after its batch is done); the
  hub records nothing in a batch, runs no git and messages no agent (the server runs no git but its writer's and that of a command its `cli.run` runs, the batch's end cleanup); every journal line, the CLI commands' included in their own process, goes through the one append function; an outside poller (the user's own program, never
  started by chantier) writes into a project's journal only through `journal add`, only `issue@1`
  lines, and only for an issue a CR's `issue:` line names; each watcher holds a lock of
  its own in the git folder, `chantier/watch-<project>/<session>.lock` (one per project and session
  that ran a watcher, held while it runs, empty, never removed), which `status`, `open`, `take`,
  `order` and the switch to direct mode read to print the `watch: not running` line. Its measured cost to justify
  it: one round trip with the user per merge and per board session ("rescan").
  `lease`, an exception to the measured-cost rule and not a git one (with `take --reclaim` and
  `lease hold`), a Driver's, the stack driver's and a QA driver's short lease on their unit, renewed
  by their commands, built on the user's answer of 2026-11-20 ("tout": all five of Board's ideas);
  `lease hold` runs nothing: it keeps a lease live for a bounded time (45 minutes by default, 90 at
  most), and the hub writes nothing for leases. `interests`
  and `journal add`: `interests` lists, read-only, what the CRs wait for (the PRs or MRs of the
  batch that runs or is paused with open PRs, read by the forge hub, and the issues the CRs' `issue:` lines name, read by an outside
  poller only); `journal add` is the one entry by which an outside poller appends an `issue@1`
  line to a project's journal; built on the user's answer planning-server-Q24 (2026-11-20: issues
  polled from outside), with no measured cost.
  `login` and `logout`: `login` stores a server's address and key in a profile of the user's config folder for the projects named, after which every command for those projects but `serve`, `watch`, `webui`, `live`, `login` and `logout` runs on that server (`gate` is refused there), and `logout` removes it; built on the user's answers remote-cli-Q4, Q7, Q8 and Q17 (2026-11-22), with no measured cost.
  `webui`: prints the web board's link with its key, and starts the surface server, detached,
  when none runs (with an active profile, it prints the profile's link and starts nothing); built on the user's answers remote-cli-Q1, Q3 and Q14 (2026-11-22), with no
  measured cost.
  `wait`: a CR's typed
  waits (answer, approval, pipeline, merge), recorded, cleared and shown, the hub signalling a wait
  met; built on the user's answer of 2026-11-20 ("tout", planning-server-Q9), with no measured
  cost.
  `access`: read-only, it explains why a session may or may not write the planning folder, claim
  a CR or push its branch, and changes nothing; built on the user's answer of 2026-11-20 ("tout":
  all five of Vercel Board's ideas, planning-server-Q9), with no measured cost.
  `live`: a read-only terminal client of the surface server's published API, shipped in
  `clients/tui/`; it reads the server only (the recorded one, or the active profile's) (never the planning folder, the forge or git), writes
  nothing and messages no agent; built on the user's request of 2026-11-20, with no measured
  cost.
  The forge calls of the batch's commands, with the user's own `gh` or `glab`, and the network for
  them: `ship` reads the base branch and the draft state of the PR it records, once per call, and
  `take`, `round` and `handoff` read the base branch of a stacked CR's PR (a CR of a `stack`
  batch's chain with a PR recorded) for each such CR they print; a failed read prints
  `base ? (not read from <link>: …)` and blocks nothing; `forge-stack` (`create`, `show`,
  `rebuild`, `unstack`) reads the batch's PRs or MRs and the forge's stacks, and writes only
  stacks and bases: it creates a stack (GitHub), dissolves one and retargets a PR's base or an
  MR's target branch, and nothing else on the forge (no PR opened, closed, merged, approved or
  commented). Built on the record's drift from the forge in batch-17 and batch-18 (`ship`'s read,
  CR-270 `ship-reads-forge`) and on the stack batches (`forge-stack`, CR-234, CR-245, CR-313),
  named in this rule after the fact (`agents-md-names-cli-forge-reads`).
  The surface server's writer, a thread of the same process, one per planning surface and
  machine, held by an OS lock in the git folder (`chantier/writer.lock`): while the server runs, it
  commits, rebases and pushes the planning surface's published paths and the local commits of the
  surface's branch, within 5 minutes of a change, with the user's own git identity and hooks, and
  needs the network for its fetch and push; its git commands are the next bullet's, it records its
  state in the `writer` entry of `chantier/server.json` and appends `sync-*@1` lines to the
  journal, and one `arrived@1` line for each CR a pull brought into the inbox or the backlog
  (read from git's trees with the two reads the next bullet names), and it never edits a batch or messages an agent.
- The CLI has named git exceptions: the surface server's writer, which runs `git add`,
  `commit`, `fetch`, `merge --ff-only --autostash`, `rebase --autostash`, `rebase --abort`, `push` and, read-only, `merge-base` and `ls-tree` (to tell the
  arrivals) (never forced, never `--no-verify`), in the planning surface's checkout only, while the
  server runs, and the batch's end cleanup (above). The rest of the CLI keeps no git write.
- Never edit a version by hand: `just version X.Y.Z` or `just bump-version [minor|major]`.
- The CLI is one Python package declared in the root `pyproject.toml`, its dependencies listed
  there once and locked in `uv.lock`. One method runs it, `uvx --from <source> chantier`: as a
  plugin, from the plugin's own folder; in chantier's own checkout (a `.git` at the plugin root),
  when the session's project is chantier (the dev mode),
  `uv sync --locked --project` at the moments the cards name (a session's start, a batch's
  start, after a merge that changes `uv.lock`); it checks first, and a sync that chantier's own
  processes block names them and waits, never stopping or killing one but the session's own board
  and watcher on the user's yes (the cards), then `uv run --no-sync --project` runs the local
  code, live; chantier's own sessions never run `uvx --from <checkout>`; other projects run the
  plugin mode, `uvx --from <plugin root>`, even from chantier's checkout. Another project runs
  chantier from its checkout in plugin mode, a build uv caches by version: it changes at each
  version bump. The board server, its writer and the forge hub, started from another project's
  session, run that build and serve every project of the surface, chantier included, with no
  notice while the version is equal, until the next version bump or until stopped by hand and
  started again from a chantier session; but a chantier session in the dev mode is told, on
  `status`, the watcher's start line and `serve`, when the board runs another build than its
  checkout's, even at the same version string (`server.json` records each entry's `source`).
  A dependency ships wheels for Linux, macOS
  and Windows and replaces hand-written code. The CLI stays portable (POSIX and Windows, UTF-8
  everywhere).
- Tests (`tests/`) check the structure and the CLI's refusals on a prepared state, calling the CLI
  in-process: keep them few, parametrized and fast (`just test` at most 30 s above its 18.5 s of
  2026-11-14 on the user's Windows machine); the batch workflow belongs to `just scenario`.
- A session here runs chantier itself, read live from the main checkout: use it to debug it. An
  edit loads at the next session or with `/reload-plugins`, with no reinstall; a worktree's edit
  loads once merged into the main checkout.
- During an eval the main checkout does not change, neither its files nor its branch: any other
  work goes in a worktree. An eval's workspace is outside this repository: it does not read
  `.claude/settings.json` and gets the plugin from the user's own install.
- A change under `skills/chantier/scripts/cli/src/chantier/clients/web/` (the web client) reads its `DESIGN.md` first and
  keeps it true.
- A change to what the CR board pane draws (`hooks/register.tsx`'s pane, or the `STATUS.json`
  fields of `status.py` that the pane shows) carries, in its PR's Deliverables, one screenshot of
  the pane from a real Claude Code session running the PR's head, captioned with the head's SHA
  (seven characters). Until it is there, the PR's Known gaps names it ("no screenshot of the pane
  from a real session"), so the ready line quotes it; the Chief of Staff then asks the user for
  one. See [CONTRIBUTING.md](CONTRIBUTING.md).
- No fallback: no look-alike model, tool or agent and no workaround in the skill or the CLI; an
  agent judges freely within what it has.
- Repository text in English. See [CONTRIBUTING.md](CONTRIBUTING.md).

## chantier

- planning: https://github.com/gsemet/gsemet-foss-planning-surface, projects/chantier
- release: [CONTRIBUTING.md](CONTRIBUTING.md), "Release", and [docs/release-process.md](docs/release-process.md); the claims before a release: [evals/README.md](evals/README.md), "Before a release: the claims"
