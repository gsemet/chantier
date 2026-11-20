# AGENTS.md

- Run `just check` before you hand back; it must pass on Linux, macOS and Windows.
- Before a CR's first push, its Driver runs `just check` in the worktree, at the rebased head it
  pushes; for a change under the CLI's `src/` (`skills/chantier/scripts/cli/src/`) or the eval kit
  (`evals/kit/`) it also runs `just eval-dry-run` there. A cards-only change does not owe it.
- The long gate is the pipeline's `just scenario (ubuntu-latest)` job, green at the PR's head: a
  change to the CLI, the cards or the scenario passes it before its PR; a change to the docs or the
  eval kit alone needs none. Windows coverage: in each batch, the CR on top of the stack also
  passes `just scenario` locally (`chantier gate`) at its head before the user merges; when a CR
  joins on top, the local run moves to it.
- A change to `hooks/` or `types/` passes `just mod` before its PR; the agent runs it itself, and
  one that cannot stops and says so, with no workaround.
- `main` is protected: work on a branch, open a PR, merge by rebase when CI is green.
- The plugin must work with no setup: the user's `AGENTS.md`, and optional `chantier.yaml` (or
  `chantier.yml`) files, at the project's root and, with an external planning surface, at the
  surface's root and in the project's folder there, are the only configuration, above the plugin's
  shipped `config/chantier.defaults.yml` (with none, chantier runs on the shipped defaults; `uv` is the only tool to install, and the CLI needs no network once uv's cache holds its
  packages, except the board's PRs page and the forge hub (below)), and chantier writes only in the planning folder (`.agents/changes/`, or the project's folder of an
  external planning surface), as plain JSON and Markdown (with the `.lease-hold.*.run` records of
  `lease hold`, never published), and the project's `chantier.yaml` in an
  external planning surface's project folder, from the board's Configuration page, and a CR's
  cleaned archive in its PR when the project asks for it, and fast-forwards a clean main checkout
  after a merge it records, the surface server keeps its key, and while it serves its PID, address
  and version, and the forge hub's PID, version and last reads, in the repository's git folder
  (`chantier/server.json`, with its write lock `chantier/server.json.lock`; the hub's lock is
  `chantier/hub.lock`),
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
  both. The CLI knows no role; one named exception: the cost code knows the two specification
  agents by their agent type (`spec-writer`, `spec-critic`), to put them on the grill line.
- The CLI's scope: the CR lifecycle, the batch's frame (limits, record, STATUS files), the means
  to synchronise, and a few tools (among them `validate`, a read-only check of a planning folder
  that a surface would otherwise keep in its own drifting script). The agents do the work, git and the forge included; a new
  CLI tool comes from measured token-costly behaviour, never from speculation. Two named
  exceptions. First, the end of a batch's last CR (`order merged`, `handback released`, `cancel`,
  `order drop`) removes the batch's merged CRs' worktrees and branches whose Driver has ended
  (`git worktree remove`, `git branch -D`, from the main checkout or the project's clone, with no
  `--force`), then pauses the batch; it does nothing else in git. Second, the surface server, `chantier board`: the web board's server, for the user on this machine and the local
  network, behind a key in its URL: it serves the record and the planning folder's files, and it
  edits the backlog (the inbox, `2-backlog/P1`...`P4`, `3-ready`: files and folder moves) and
  each role's agent, model and escalation, per host, and the two limits (`specifying.parallel`,
  `batch.slots`), in the project's configuration file in the planning
  surface (`projects/<name>/chantier.yaml`), only through the CLI's role-free commands and its
  own reading, checking and writing of that file; it never edits a batch and never messages an
  agent; one named exception, its PRs page: when that page asks, at most once every 10 s per project
  and batch shown, while a PR of the batch shown is not done, plus one read when the page opens and
  one at once on each change of the batch shown, it reads the forge, read-only, with the user's own
  `gh` or `glab`, on its own (no agent asks it), and needs the network for that, and a second, from
  the same page: when its forge read finds a PR of the batch in `4-batch/` merged that the record
  does not hold, it appends one line to `forge-journal.jsonl` (planning folder, never published), which
  `status` prints for the Chief of Staff to record at its next `status`; the
  board itself records nothing and messages no agent; a third, from its Configuration page: a save
  appends one `config@1` line to the same journal (`source: board`) for each key whose effective value it
  changes (the two limits, and each role's agent, model and escalation), which `status` and the
  watcher carry to the Chief of Staff; and each write it makes to the backlog also appends one
  `board@1` line to that project's `forge-journal.jsonl`, which the Chief of Staff's watcher reads;
  it takes its dependencies like the rest of the CLI and knows no role. The same process is the
  forge hub while it runs (one per planning surface and machine, started by the Chief of Staff on
  the user's yes): it holds the OS file lock in the git folder (`chantier/hub.lock`) and, with
  none running, the one watcher of the surface that holds that lock is the hub and yields it when
  a server starts. The hub reads the forge, read-only, with the user's
  own `gh` or `glab`, on its own (no agent asks it), and needs the network for that: at most once
  every 20 s, one query per project of the surface whose running batch has a PR the record does
  not hold merged or cancelled; it appends to that project's `forge-journal.jsonl` (planning
  folder, never published) one line per merge the record does not hold and per CI turning red on
  a PR ready to merge, and nothing else; each session's watcher, run for the Chief of Staff's
  whole session, with or without a batch, reads only its project's journal (the hub's lines and
  the board's), never the forge, and ends 20 s after the last new event for it that wakes, and no
  sooner than `events.wake_every` after its start, which wakes its session, or when the project's
  seat is another session's; the
  hub records nothing in a batch, runs no git and messages no agent (the server runs no git either, but its autosync join); every journal line, the CLI commands' included in their own process, goes through the one append function; each watcher holds a lock of
  its own in the git folder, `chantier/watch-<project>/<session>.lock` (one per project and session
  that ran a watcher, held while it runs, empty, never removed), which `status`, `open`, `take`,
  `order` and the switch to direct mode read to print the `watch: not running` line. Its measured cost to justify
  it: one round trip with the user per merge and per board session ("rescan").
  One more exception to the measured-cost rule, not a git one: `lease` (with `take --reclaim` and
  `lease hold`), a Driver's, the stack driver's and a QA driver's short lease on their unit, renewed
  by their commands, built on the user's answer of 2026-11-20 ("tout": all five of Board's ideas);
  `lease hold` runs only what a Driver gives it, to keep a lease live, and the hub writes nothing
  for leases.
- The CLI has two named git exceptions: the surface server, which may serve without joining the
  planning surface's autosync group (board and autosync permissions are independent; autosync
  participation is explicit opt-in and does not stop other participants; the board commits
  nothing itself), and the batch's end cleanup (above). The rest of the CLI keeps no git write.
- Never edit a version by hand: `just version X.Y.Z` or `just bump-version [minor|major]`.
- The CLI is one Python package declared in the root `pyproject.toml`, its dependencies listed
  there once and locked in `uv.lock`. One method runs it, `uvx --from <source> chantier`: as a
  plugin, from the plugin's own folder; in chantier's own checkout (a `.git` at the plugin root),
  `uv sync --locked --project` once at the moments the cards name (a session's start, a batch's
  start, after a merge that changes `uv.lock`), then `uv run --no-sync --project` runs the local
  code, live; never `uvx --from <checkout>`. A dependency ships wheels for Linux, macOS
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
- A change under `skills/chantier/scripts/cli/src/chantier/board/web/` reads its `DESIGN.md` first and
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
