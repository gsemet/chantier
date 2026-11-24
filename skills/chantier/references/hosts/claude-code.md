# Claude Code (Claude Desktop)

What is proper to this host: the tools, the heartbeat, the sessions, and what only the user can
do. The cards say what a role judges and point here. Read it with your card when you run on
Claude Code.

## Startup core

The host provides the role's named startup prompt and its declared tools.

Each behaviour carries a mark:

- **proved**: seen on the host, with where and when;
- **documented**: the host's documentation says so, with the link; not seen here;
- **unproved**: nobody has seen it, and the trial that settles it is named. Never tell the user an
  unproved behaviour as a fact: say it is not known, and what would settle it.

## Tools

| Generic | Claude Code | Mark |
| --- | --- | --- |
| Start the Foreman's session | `mcp__ccd_session__start_session` with `initiation: "user_asked"`, `title: "<title>"`, `context: "fresh"`, no `cwd`, no `preset`, `use_worktree: false`, `model: "claude-sonnet-5-5"`, `effort: "medium"`, the user's permission mode; leave it linked | the start: proved, every batch started from Claude Desktop (v0.3 on); from Remote Control: proved 2026-11-20 (the Studio's batch-07 Foreman); with this model: **unproved** until seen. Trial: batch-11, where the Foreman was switched to Sonnet 5.5 after its `ready` (CR-174), then the first batch started with this row: the transcript shows `claude-sonnet-5-5`, and `effort: "medium"` is accepted with it. Record the date once seen |
| Own session id and title | `get_session("self")`; the transcript's id is `$CLAUDE_CODE_SESSION_ID` | proved, same |
| Set a session's own title (the Chief of Staff, a Griller, the Foreman) | `set_session_title` | proved for a Chief of Staff's own session, 2026-11-08 (Battlestation, a session renamed itself); the Foreman's case stays unproved: the trial is a Foreman that sets its title and `get_session("self")` shows it |
| The skills | `/chantier:chantier` (the router), `/chantier:chief-of-staff [foreman|direct]`, `/chantier:griller`, `/chantier:status`, `/chantier:chantier reload` (the router with the argument `reload`), `/chantier:chief-of-staff reload`, `/chantier:griller reload`: a plugin's `skills/<name>/` is `/<plugin>:<name>` | documented: <https://code.claude.com/docs/en/plugins-reference> (skills); the argument's handling (only the first word of `chief-of-staff` counts) is unproved until a session shows it, and the reload's until a reload runs; the argument `reload` of the two role skills is unproved until seen, its trial the one of "Reload after a compaction"; trial: type `/chantier:chantier reload` after a `/compact`, see the one line and no introduction |
| Load another skill (the router) | the host's Skill tool | unproved until the router runs; trial: `/chantier:chantier` in a session with no Chief of Staff, answer a role, see the skill load |
| List the sessions and their state; is the seat's session alive | the session tools found in the `mcp__ccd_session__` set: the exact tool and its states are not recorded | unproved; trial: two sessions on one repository, one stopped, list both and record the states |
| Message another session of the user (hand-over, a Griller's line) | `SendMessage` to its session id | proved for the Chief of Staff's session (the row above); between two sessions of the user, unproved; trial: a Griller's `ready` line to the Chief of Staff's session |
| A session's link (for the seat) | what `get_session` gives | unproved until recorded; trial: `get_session("self")` and note the link field |
| Start a Driver or a worker | `Agent`, `run_in_background: true` for a Driver, `subagent_type: <agent>`; the plugin's agent is `chantier:<role>`; the model, only when `$CHANTIER` printed one (`team:` or `playbook`): the `model` parameter, set to the printed start value (an alias: `opus`, `sonnet` or `haiku`), as printed; no effort | the agent: proved, same; the model: capability yes (alias), proved 2026-11-10 (trial below) |
| Start the Spec-writer (Chief of Staff) | `Agent`, `run_in_background: true`, `subagent_type: chantier:spec-writer`; the `model` parameter as in the row above, only when `$CHANTIER playbook` printed one; no effort | the agent: unproved until a CR is specified this way; the model: capability yes (alias), proved 2026-11-10 |
| Start the Spec critic (Chief of Staff, Griller) | `Agent`, `run_in_background: true`, `subagent_type: chantier:spec-critic`; the `model` parameter as for the Spec-writer, only when `$CHANTIER playbook` printed one or the user asked for Fable; no effort | the agent: unproved until a CR's specification is checked this way (the trial on CR-250's specification did not use this agent); Fable through the `model` parameter: unproved. Trials: the first impactful CR specified after the merge; one critic run on Fable, its transcript showing the model |
| Message a Driver | `SendMessage` to the agent id | proved, same |
| Message the Chief of Staff | `SendMessage` to its session id | proved, same |
| A Driver messages its steering session (the Foreman; in direct mode the Chief of Staff, which is `main` there) | For a steering session of Claude Desktop (a session id `local_…`: every Foreman, and the Chief of Staff of a direct batch run from Claude Desktop): the Driver's final report only (the host's hand-back, `SubagentHandback`), once, at its end; before its end a background subagent has no means to reach that session, and `SendMessage` to `main` does not reach it. Its `Steering:` line, as the parent copies it into each Driver's prompt (with its own session id, and "the Chief of Staff" for "the Foreman" in a direct batch; this holds for every Driver: CR, stack, release, QA): `Steering: the Foreman (session <id>, for the record). Nothing reaches it before your end: send no message. Your one send is your final report (the host's hand-back): its first line is your hand-back line, then every other line due (`anomaly`, `push`), one per line, as the cards word them. Record an `anomaly` when it happens: `$CHANTIER note <cr> "anomaly: <text>"`. A `ping` needs no answer: go on.` For a direct batch run from a terminal or VS Code: `SendMessage` to `main`, and the `Steering:` line names it. | Foreman mode: the final report as the hand-back's route is proved (batch-16, batch-18, the rows below); that no message reaches a Desktop Foreman before it: seen, Studio batch-06, 2026-11-20 (its retro, `projects/markdown-okf-schema-studio/changes/5-archives/batches/batch-06.md` in the planning surface), the host's exact text not recorded. Trial: in the next Foreman batch, a Driver's transcript shows what a `SendMessage` to `main` returns; record the text and the date here. Direct mode from Claude Desktop: unproved, same trial in a direct batch. Direct mode from a terminal: unproved; trial: the first direct batch run there, a Driver's `anomaly` line arriving before its hand-back |
| Stop a Driver | `TaskStop` | proved, same; after its own `TaskStop` with no restart at once, the steering session clears the recorded id (`foreman-lost-driver.md`, "A Driver stopped from outside") |
| A CR Driver's start folder | the mod's, as "The write guard" says | unproved; trial: the first CR Driver of the batch after the merge runs `pwd` (or `Get-Location`) and gets its worktree, or the main checkout or the clone on a first take |
| Stop a background task of one's own (a shell, a monitor) | `TaskStop` with the id its start returned (`Bash` or `PowerShell` with `run_in_background: true`, or `Monitor`); the Driver agents list `TaskStop` in their tools for it | unproved; trial: a CR Driver of the first batch after the merge stops its CI watch when its gate fails first, or a task before its hand-back, and its transcript shows the `TaskStop` call and no notification from that task after it |
| Name the holders of the checkout's environment (before a dev-mode sync) | on Windows, the `PowerShell` tool: `Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '<plugin root with backslashes>\.venv\*' } | Select-Object ProcessId, ParentProcessId, CommandLine`; on macOS and Linux, the `Bash` tool: `ps -eo pid,ppid,args | grep -F "<plugin root>/.venv/"` (the grep line itself excluded). Reading: a `chantier.exe` and its child `python.exe` are one holder, named by the top process's PID, its subcommand (`serve`, `watch`, `gate`, `status`...) and its `--project` value, from its command line. "Own", by its evidence: own board = its command line holds `--seat <this session's id>` and this session's `serve --seat` did not print `board already running`; own watcher = a `watch` process with this project's `--project` while this session holds a running watcher task (a monitor or a shell) and the project's seat; anything else is not own (the Foreman's watcher, a `watch` of the Foreman's session, is the Foreman's, never own for the Chief of Staff). Read-only; never `Stop-Process`, `taskkill` or `kill` on a holder | the Windows listing exercised on 2026-11-21 by this CR's spec-writer on the user's Windows machine (it listed a Studio board, a Studio watcher, chantier's watcher and a Studio command, each a `chantier.exe` with its `python.exe` child, both under `.venv\Scripts`); the macOS and Linux listing untested; no allow rule (a path-bearing pipeline rule is unproved), so it may prompt outside auto or bypass mode, rarely (only after a `uv.lock` change, since the check comes first); a process holding a `.venv` file without running from `.venv` is not listed (then the skill's `an unlisted process`); on macOS and Linux a gate started between the listing and the sync is not caught (no os error 32 there); whether the host's stop of a background shell ends its process tree (the `chantier.exe` and its `python.exe` child) is unproved, so a holder may stay listed after the stop (waited on, never killed) |
| Stop an ended Driver that wakes again (`foreman-lost-driver.md`, "An ended Driver that wakes again") | `TaskStop` with the Driver's agent id, as "Stop a Driver" | the stop: proved, same as "Stop a Driver"; whether it also ends the background tasks that Driver left running: unproved; trial: the next such stop, then no task notification from that Driver's tasks in the steering transcript |
| Stop another session (a Foreman not answering, on the user's yes) | `mcp__ccd_session_mgmt__stop_session` with the session's id | unproved. Trial: the first switch to direct mode with a Foreman not answering, the Foreman's session shown stopped afterwards. From Remote Control: unproved |
| Agent ids of the project | the `name:` of a file in `.claude/agents/` or `~/.claude/agents/` | proved, same |
| Start the Retro critic (Foreman, Chief of Staff) | `Agent`, `subagent_type: chantier:retro-critic`; the `model` parameter only when `$CHANTIER playbook` printed one or the user asked for Fable; no effort | the agent: unproved until a retro is cut this way. Trial: the first pause after the merge, the Foreman's transcript showing the agent and its model; Fable through the `model` parameter: unproved |
| Models | the Spec-writer, the Spec critic and the Retro critic run Opus 5.5; the Foreman, every Driver and the workers run Sonnet 5.5, unless the configuration (`hosts.<host>.roles`) sets one (the default models are `config/chantier.defaults.yml`'s); a task under escalation (`concepts.md`, "Escalation") runs the role's `escalation` model, set per role in the configuration and printed by `$CHANTIER playbook` (only `coder`, `debugger` and `conflict-resolver` escalate) | proved, same, except the CR driver, the stack and release drivers and the Foreman: unproved; the trial is the model their transcripts show in the next batch (the Foreman: the trial in the row "Start the Foreman's session") |
| Models at an agent's start (capability, start value) | capability: yes; named agent with a model: yes (`NAMED_AGENT_MODEL_AT_START`); a model changed in the configuration starts the role's named agent with that model, its tools unchanged. Start value: an alias, which the CLI's table maps from the exact identifier: `claude-opus-5-5` (Claude Opus 5.5) is `opus`, `claude-sonnet-5-5` (Claude Sonnet 5.5) is `sonnet`, `claude-haiku-5-5` (Claude Haiku 5.5) is `haiku`. The full identifier is not recorded as accepted | proved 2026-11-10: a trial started a plugin agent through `Agent` with `model: haiku`, and its transcript showed `claude-haiku-5-5`; the other two aliases are the same mechanism, unproved one by one |
| Skills and tools of a session (what the Chief of Staff compares a role's needs with) | not recorded: how a session lists its skills and its tools, and whether a subagent sees what the session sees | unproved; trial: a `chantier.yaml` naming one skill that is installed and one that is not; the Chief of Staff names only the second; and a subagent started with a need says whether it has it |
| Preflight P2 | `mcp__ccd_session__start_session` loads | proved, same |
| Ask the user a series of questions (grill, specification) | the host's question tool (`AskUserQuestion`), at most 4 questions per call, at most 4 options per question, plus the tool's own free answer ("Other"); the reference opens each question's text (the tool's short header field, if used, does not need to hold it). Remote Control relays the same tool: the user sees the same 4-question form on the phone. Under Remote Control the form shows above the conversation and the text written before it is read by scrolling up: the text is written before every call all the same | the figures: the user's statements (2026-11-14, CR-250 answers 5 and 11), unproved; trials: one call with 4 questions shown and a fifth refused; the same series from the phone under Remote Control, all 4 shown. The scrolling: observed by the user, 2026-11-14 (CR-250 answer 17) |
| Run the board | `Bash` with `run_in_background: true` and the command `$CHANTIER serve --seat <id>`, with `--forge-always` on a host that cannot run the watcher (`session-start-chief-of-staff.md`); `$CHANTIER serve --restart --seat <id>` runs by the same means; its first lines are read from the background task's output; stopped with the host's stop of a background shell | unproved; trial: a Chief of Staff starts it, `GET /api/board` with the key answers from the machine, and the output shows the start line |
| The board's Griller (the surface server starts it) | `claude -p` with the JSON output, as the agent `chantier:board-griller` with `--model <effective model>`, the conversation fixed by an id and resumed by it, the prompt on standard input, no user, project or local settings loaded, the plugin loaded explicitly, the allow list alone (the Griller card's "Started from the board", the spec's section 3); the exact flags the trial proved, the variables cleared from its environment and the Claude Code version the trial ran (`claude --version`; recorded only: no warning or refusal on another version) are recorded here once it has run | **unproved** until the trial (the trial's date, what it showed, each refusal quoted, and the reads it allows: the project, the planning folder and the plugin's skill folder, read-only). Each of these points is **unproved** until the trial shows it: the prompt on standard input with `-p`; `--agent chantier:board-griller` (a plugin agent) under `-p`; `--model` together with `--agent` under `-p` (the model the JSON result reports is the one passed, not the agent file's); an agent's `tools:` narrowing a main-thread agent; `PowerShell(...)` allow rules; no settings loaded while the sign-in still resolves; how the server tells that the host saved a conversation for an id |
| Trust of a workspace inside a trusted folder | a folder the user has trusted once in Claude Desktop at the desk covers every new folder created inside it later, so a session started on such a folder from Remote Control does not ask for trust | unproved; trial: the first `real-direct` run after the eval root change, started from the phone on `<eval root>/real-direct-<date>`; the operator's `git rev-parse --git-dir`, `--git-common-dir` and `--show-toplevel` before `preflight` (evals README, "The operator"); on Pass the row is marked proved, with the date and the machine, on Fail it records what was seen |
| Move a started session to another folder | a session started with no `cwd` may move with `mcp__ccd_directory__change_directory` into a folder inside a trusted folder (the `Projets` tree): no question is asked in auto mode, the next turn runs there (`pwd`), and the move does not reload project instructions: the session keeps the `AGENTS.md` of the folder it started in. Clearing another session from the Chief of Staff (`clear_session` on another id) is denied by the auto mode classifier, and no chantier route uses it. Not recorded here: the operator's route, the self-clear, and where a session started by a moved session lands | proved 2026-11-20, Battlestation (the move and the denial; `01-intent.md` of CR-414); the other three: not recorded |
| Prompt cache TTL (the `cache_ttl` defaults) | a session's cache writes are 1-hour (`cache_creation.ephemeral_1h_input_tokens` in its transcript's usage), a subagent's 5-minute (`ephemeral_5m_input_tokens`) | measured once, 2026-11-17, one account; unproved in general. Trial: on another account, or after a host update, one session and one subagent each write the cache, and their transcripts' `cache_creation` fields show the same split; record the date and the account's kind |
| Steering wake bound (60 minutes) | the CLI refuses a `steering_wake` over 60 minutes | proved: 30 minutes (real-direct run 1, 2026-11-12); unproved: 55 minutes, the shipped default since CR-479, and any other value up to 60; the first batch run on this version is the trial of 55: the Foreman's transcript shows a `ScheduleWakeup` of 3300 seconds and a wake about 55 minutes later, or an event wake before it. Trial for the bound: a batch with `session: steering_wake: 60m` whose Foreman's transcript shows a `ScheduleWakeup` of 3600 seconds and a wake about an hour later; then one over 60 minutes, to learn whether the host accepts it, before the bound moves |
| Run the watcher | `Monitor`, with no timeout, running the command the `watch: not running`, `still running` or `no event for <name> in 2 h` line prints, as is (it ends with `--stream`); each notification (event lines closed by `... still watching`) starts a turn of the idle Chief of Staff session, and so does the monitor's end (its last line). Auto mode drops every `Monitor` allow rule ("What not to add"): the start is the classifier's call | unproved; trial: a batch with two merges and one watcher, the Chief of Staff's transcript showing two notifications, two forge checks and two `order merged`, no watcher started and no user message between. A `config@1` line the board writes (a limit saved on its Configuration page) wakes the watcher like a merge: unproved; trial: save `batch.slots` on the board with a watcher running, see the `config changed on the board` line in its notification. The trial also covers a board move with no batch running and the session's turn that follows. The Foreman runs a watcher of its own the same way (`Monitor`, no timeout, the `watch: not running: for the Foreman` command as printed), which starts no board and ends when the batch records another Foreman or closes; whether a notification starts a turn of an idle Foreman session is unproved; trial: a batch whose Foreman is idle when a PR merges, the transcript showing the notification, the forge check and the `order merged` with no heartbeat wake before it, and one with the Foreman's session ended while the batch runs, to see whether the watcher outlives it; the first batch on this version runs both, and records the date and result here. The `no event for <name> in 2 h` line: start again at once as printed, nothing told. The watcher may start the board as a detached process (`serve --seat <id> --stop-idle`), no background task of the session: unproved that it outlives the watcher and that the host does not see it as one; trial: with no board running, start the watcher, see its `started the board (PID <n>)` line; stop the watcher's task, then ask `GET /api/board` with the key: it answers, and the host lists no board task; end the session, ask again: it answers (until the seat leaves or 30 minutes with no client); the trial, when run, records its date and result in this row. |
| The watcher when the session ends | whether the host ends a background command when the session ends | unproved; trial as for the board's row. Until then an orphaned watcher ends once the project's seat is another session's or, with no batch in flight, 2 h after its last event or its batch's end (the CLI); a Foreman's watcher also ends when the batch records another Foreman or closes, and, with no PR of the batch open, 2 h after its last event (it keeps running while the batch is paused); while one is in flight it runs until the seat moves (accepted, watcher-limit-Q1); the board it observed stops 30 minutes after it ends; the trial, when run, records its date and result in this row |
| The board when the session ends | whether the host ends a background command when the session ends (closed, or stopped) | unproved; trial: start the board, end the session, ask `GET /api/board` with the key. Until proved, the board stops when the seat moves (the CLI), which does not depend on it. A board a watcher started is no background task: it stops when the seat moves or 30 minutes after its last client (the CLI), which does not depend on the host. |

"Proved, same" means seen in use in every batch since v0.3, with no dated trial kept: re-prove a
line by a trial before relying on it for something new.

**Limit on messages.** Claude Desktop limits messages between sessions (10 since someone last
typed): a refused send is reported, never sent another way. Proved in use, same; the figure comes from
the earlier card, with no dated trial. The limit applies to the lines between a Griller and the
Chief of Staff, and to a hand-over's.

## Heartbeat

The Foreman (in direct mode the Chief of Staff, in its own session) runs the `/loop` skill in dynamic mode. The loop's prompt is the command `chantier status
--refresh --batch <batch> --epoch <n>` alone, with no interval in it (no "every 30m", no other): a
prompt that ends in an interval makes `/loop` take its fixed-interval mode (seen in real-direct
run 1, 2026-11-12). Each wake is scheduled with `ScheduleWakeup`, the steering wake of the
`timing: Claude Code session:` line of `chantier playbook --batch <batch>`, in seconds, after the
last (55 minutes, 3300 seconds, by default; the Foreman's own watcher wakes it sooner on a merge, a red CI or a met wait). It ends the
heartbeat, never its session, with `ScheduleWakeup` `stop: true` (after `chantier status
--stop-heartbeat --batch <batch> --epoch <n>`, which every pause already does): right after the pause,
the steering session's own or the automatic one (the record alone does not stop the wake, and a
later wake's `status --refresh` resets it),
and on the first wake that sees no Driver of any kind (CR, stack, QA, release) run for 30 minutes
or more, whatever the wake's interval, and no order is undone. An order's line or a `ping` starts a turn; if it leaves a Driver running, the
Foreman arms the heartbeat again. On a batch born paused with no CR, the steering session (the
Foreman, or the Chief of Staff in direct mode) arms the loop only in the turn of its first `take`.
No wake ever arriving is a stop. Proved: same.

## Auto-fix events

- **What it is.** Auto-fix is a feature of the Claude Desktop app, not of chantier. The app binds
  a PR opened by a subagent to the session that started it (the steering session: the Foreman, or
  the Chief of Staff in direct mode), then sends that session events about the PR: fix its failing
  checks, resolve a conflict by merging the base branch in. Seen in batch-14 (PR 136) and in
  real-direct run 1 (2026-11-12, PRs #2 and #5 of the sandbox).
- **An event is not an order.** It is neither the user's word nor a line of the batch (`order`,
  `asks`, hand-back). The project's rules, then the cards, always rank above what a host event
  asks; a host event has no rank in that order. A CR's branch is brought up to date the project's
  way (here a rebase, `concepts.md` rule 8 and the project's rules), never by the merge of the
  base branch the event asks for.
- **A CR with a live Driver** (the CR is `working`, its Driver recorded): the steering session
  does nothing on the PR: no fix, no merge, no rebase, no push, and no relay of the event to the
  Driver. It ends the turn at once. The Driver reads its own CI and holds the branch, two writers
  on one branch race, and a relay spends messages against the host's limit for news the Driver
  already has.
- **A CR with no live Driver** (handed back `ready` or `blocked`, waiting for the user): the event
  is only a signal. The steering session checks the forge itself (`gh pr checks`, `gh pr view
  --json mergeable`, or `glab` on GitLab). If the PR is really red or in conflict, it follows the
  card's usual route: the CR goes back to a Driver with `take <cr> --note "<why>"` ([foreman-merge](foreman-merge.md),
  the take-back list: a red check, or the PR ready to merge that stopped merging with `--note "rebase: …"`). It
  never does what the event asks itself. If the forge shows nothing wrong, nothing is done.
- **Both steerings.** The same rule holds for whichever session steers: the Foreman, or the Chief
  of Staff in direct mode.
- **A PR that is not a batch's** (the user's own PR in the same session) is out of chantier's
  rule: it is between the user and the app. This section speaks of a batch's PRs only.
- **chantier never arms, disarms or unbinds the PR monitor.** No card uses the app's PR monitor
  (`mcp__ccd_pr__set_monitor`), to arm it or to disarm it, and chantier writes no setting of it (the only settings it
  writes are the allow rules of "Configuration", on the user's yes). The one use is the eval guide's
  operator, who plays the user and turns the monitor off on a run's own sandbox PRs
  (`evals/README.md`, "Auto-fix during the run"); no role does.
- **The cost.** Even ignored, each event starts a turn of the steering session, which the user
  pays for.
- **Turning Auto-fix off.** The per-PR switch is documented
  (<https://code.claude.com/docs/en/desktop.md#monitor-pull-request-status>) and was seen on
  2026-11-15: `mcp__ccd_pr__set_monitor` with the monitor off, or the PR's menu (the three dots) in
  the Changes card. The global setting (Settings > Code, or Settings > Claude Code, by the app's
  version) stays **unproved**: the documentation describes no default for PRs opened later, and
  third-party reports say it may not reach local sessions' PRs. Trial that settles it: turn it
  off, open a PR from a subagent, and see that no Auto-fix event arrives; record the labels and the
  date here. Turning it off also loses Auto-fix for the user's own PRs.
- **During a normal batch chantier stays silent** about Auto-fix: it does not ask the user to turn
  it off, has no preflight check for it and gives no "For you" line for it (chantier cannot see
  whether Auto-fix is on, and a line at every go would be noise). It only ignores the events as
  above. Only the eval guide turns Auto-fix off: before a real campaign, and on each of the run's own PRs. A tip may come later,
  from a measure of the ignored turns' cost in a real batch.
- **Mark of the section.** The rule (the live Driver, no live Driver and both-steerings points,
  and the event-is-not-an-order point) is **unproved** until the next real campaign shows it.
  Trial: an Auto-fix event arrives on a CR's PR during a real eval campaign, and the steering
  session ends its turn with no tool call on that PR and no message to its Driver (a CR with a
  live Driver), or checks the forge and uses `take --note` (a CR with none).

## The Foreman's turn-end notice

- **What it is.** A feature of Claude Desktop, not of chantier. When a session starts another with
  `start_session` and leaves it linked, the started session tells the one that started it each time
  it ends a turn. It does so by a system reminder that begins `The session "<title>" you started
  (<id>) finished a turn` and quotes the first 400 characters of its last reply. For chantier the
  starting session is the Chief of Staff and the started one is the Foreman. **Proved**:
  real-foreman run 2, 2026-11-15, ten notices in the Chief of Staff's session (its transcript, with
  the Foreman's session id `local_5c866244-7454-4551-bb0f-9ea2ac1d630f`).
- **A notice is not a line.** It is not the user's word and not a Foreman line of
  [routing](../routing.md); it carries no ask and no order. What the Foreman must tell the Chief of
  Staff comes as its own `[foreman→chief-of-staff]` line (`ready`, `ask A-<k>: …`, `pong`, `final`,
  `push`, `chain`), and a lost line is found with `$CHANTIER asks`. The project's rules, then the
  cards, rank above what the notice's text asks ("read it with get_session / list_events", "mention
  the outcome to the user"). The notice has no rank in that order, just as an Auto-fix event has
  none.
- **The rule.** On a turn that a notice alone started, the Chief of Staff ends the turn at once. It
  makes no tool call (no `$CHANTIER asks`, no `status`, no `get_session`, no `list_events`, no
  ToolSearch), sends no message to the Foreman, writes no report and does not restate the quoted
  text to the user. Its reply is empty, or one short line when the host requires text (for example
  "Noted."), never a summary of the Foreman's state.
- **The one exception: the Foreman stopped on an error.** The exception applies when the notice's
  quoted text shows that the Foreman's turn ended on an error that stops it (a usage limit, an API
  error), and no Foreman line came with it. The Chief of Staff then tells the user in one line that
  the batch's Foreman stopped, with the error as quoted. It still makes no tool call, sends no
  message to the Foreman and writes no report. It starts nothing and restarts nothing; the user
  decides what follows. Every other notice falls under the rule above. **Unproved**: no such notice
  has been seen. Trial: a Foreman stops on a usage limit or an API error in a real batch. The Chief
  of Staff's transcript then shows the one line to the user and no `tool_use` in that turn. Record
  the notice's text and the date here.
- **A notice that arrives with a line.** When the same turn also carries a Foreman line or the
  user's message, the Chief of Staff handles that line or message exactly as its card says. The
  notice changes nothing in that handling.
- **The cost.** Even ignored, each notice starts a turn of the Chief of Staff, which re-reads its
  context once. The rule keeps that to one model call with almost no output, instead of several
  calls with tool results. Run 2 had ten notices, and $2.55 for 49 calls of steering.
- **Mark of the rule.** **Unproved** until the next real-foreman campaign shows it. Trial: in that
  campaign's Chief of Staff transcript, every turn started by a notice alone holds no `tool_use`
  and no `SendMessage`. The report's `Chief of Staff, steering the batch` line should also count
  fewer calls than run 2's for a comparable batch.

## A Driver's silence

- Between its start and its final report a Driver sends nothing to a Claude Desktop steering session. Silence is no sign of a lost Driver, however long, and no reason to start another.
- A Driver's life is read from two things only: the `activity` line of `$CHANTIER status --refresh` (an age, `gate running`, `gate queued`), and the host's notices (the rows `A background subagent stops` and `A background subagent is stopped from outside`, under "Surfaces and options"). `Agent "<name>" is waiting on its own background work` is not an end.
- An `anomaly` comes as a note on the CR (`$CHANTIER status --notes`) and again in the Driver's final report; handle it when the report arrives, as the card says for the line.
- **The `ping`.** No `pong` can come. A `ping` to a suspect is still sent (it wakes a waiting Driver). At the next wake, the proof of life is that unit's `activity` age, younger than the ping. An age older than the ping, with no `gate running` and no `gate queued`, is the missing `pong` of the proof of death in [foreman-lost-driver](foreman-lost-driver.md). **Unproved**; trial: in a Foreman batch, ping a Driver that waits on its own background work, and read at the next `status --refresh` an `activity` age younger than the ping; record the batch and the date here.
- A second Driver for a unit (a CR, the stack, a QA order) is started only by the restart path of [foreman-lost-driver](foreman-lost-driver.md), after one of its proofs of death or the first one's final report: never on silence alone. For the stack: `agents set stack -` only once the stack driver's report arrived or a proof of death holds.
- Seen: Studio batch-06, 2026-11-20, a second stack Driver started 25 minutes before the first one's hand-back arrived.

## Configuration

What the user configures so chantier runs on Claude Code with few interruptions. chantier never
writes the user's settings in one case only: on the user's yes, the Chief of Staff adds to
`~/.claude/settings.json` the allow rules P10 named, and nothing else there. Preflight's P10
compares; the Chief of Staff asks. Marks as above; a doc-check
of 2026-11-09 against <https://code.claude.com/docs> gave the **documented** lines, each with its
page (`https://code.claude.com/docs/en/<page>`).

### Who reads it, when

- The Chief of Staff, at its first turn of a session and at each batch's preflight: it runs the
  check (P5, P9, P10). For missing allow rules it asks the question of `chief-of-staff.md`
  ("The project") and adds the rules on the yes; it gives the command line of "Allow rules to
  add" only when the host refuses the edit or when the file cannot be read. P10 checks the commands the agents run, not the rules' text; P9 checks the forge's rights.
  Each P10 line's `<k> of <n>` counts commands of its capability: `<n>` is that capability's
  samples that apply to the project (any forge, the remote's forge, and for a stack `gh stack`
  when `gh extension list` names it), plus `SendMessage` for every batch, and `<k>` those the
  settings do not let through. On Windows a command counts as allowed only
  when both its Bash and PowerShell forms are. A count from before 0.9.0 counted rule strings
  and is not comparable.
- The Foreman reads this file with its card. A Driver reads the sections its card's "Opening
  reads" names ("Tools", "Auto mode", "Compacting", "The write guard"), when the step comes:
  "Auto mode" tells it what a refusal means and that it is reported, never worked around.
- The workers do not read this file; what they need (one command per call, read before you
  overwrite, no leading assignment, `git -C`) is in each worker's own card.

### Prerequisites

| Tool | Needed for | Checked by | Missing |
| --- | --- | --- | --- |
| `git` | every Driver, the CLI's reads | P5 (CLI) | preflight fails |
| `uv` | `$CHANTIER` (`uv run --no-sync --project` in chantier's own checkout, when the session's project is chantier, after the steering session's checked sync, which waits for holders (the skill's `$CHANTIER` paragraph), `uvx --from` as a plugin) | P5 (CLI) | preflight fails |
| `gh` or `glab`, logged in to the remote's host | the Drivers' PRs and CI | P9 (the Chief of Staff: `gh auth status` / `glab auth status`) | preflight fails |
| `python` | none directly: `uv run` and `uvx` provide the interpreter | not checked | say so; on Windows a `python` that resolves to the Microsoft Store alias fails (seen 15 times in the user's week): the fix is the user's (App execution aliases); **unproved** as to which roles call `python` |
| `bash` | Claude Code's Bash tool on POSIX | not checked | **unproved** whether chantier needs it on Windows, where the PowerShell tool is used |
| `claude` | not a batch's need | not checked | seen missing from PATH 5 times in the user's week; no card calls it |

The last three rows are not checked: a default the Driver of this change chose to keep, and may
change on its judgment.

### Windows PowerShell 5.1

On Windows PowerShell 5.1 (the PowerShell tool), a `gh` or `glab` argument that holds spaces or
double quotes, such as a `--jq` or `--template` expression, can reach the program split or
stripped of its quotes (`accepts 1 arg(s), received 3`): print `--json <fields>` alone and read
the JSON, or write the expression with no space and no double quote.

### Allow rules

How rules match (each line **documented**, <https://code.claude.com/docs/en/permissions>):

- `*` matches anywhere; `cmd *` (with a space) is a word boundary and also matches bare `cmd`.
- `Bash(git push …)` does not match `git -C <path> push …`: the `-C` form needs its own rule.
- `PowerShell(...)` rules have the Bash shape; aliases are canonicalized; matching is
  case-insensitive.
- A compound command passes only when every part is allowed (Bash: `&&`, `||`, `;`, `|`, `&`,
  newline; PowerShell: `|`, `;`, and `&&`, `||` from PowerShell 7).
- Bash: an allow rule does not match past a leading assignment (`X=1 cmd`), except known-safe
  environment variables; deny and ask rules do. PowerShell assignments (`$w='…'; cmd`):
  **unproved**, not documented (checked 2026-11-09).
- `mcp__<server>__<tool>` is an exact tool name; a bare tool name matches all its uses.
- `Edit(~/path/**)`: `~` is the home folder, `**` gitignore-style; an Edit rule covers Write and
  NotebookEdit (<https://code.claude.com/docs/en/tools-reference>).
- Settings precedence: managed > command line > local > project > user; deny > ask > allow; a
  user deny blocks a project allow (<https://code.claude.com/docs/en/settings>, permissions).

The recommended rules, in the order P10 lists them. Each has a `Bash(…)` and a `PowerShell(…)`
form (P10 checks the Bash forms on POSIX, both on Windows). P10 does not compare these strings: it
holds the commands the cards make the agents write, and asks whether some allow rule of your
settings lets each one through. A narrower or different rule of yours counts when it matches the
same commands, for instance `PowerShell(git push --force-with-lease=chantier/* origin *chantier/*)`.
In the rules below, `origin` is the project's remote name.

| Rule | chantier's use | Risk accepted | Mark |
| --- | --- | --- | --- |
| `Bash(git push -u origin chantier/*)` and `PowerShell(…)` | a Driver's plain push (`driver.md`: `git push -u <remote> <branch>`, branches `chantier/<batch>/…`) | `*` matches any further text, so a flag added after the branch passes too; a remote not named `origin` is not covered | documented (rule form) |
| `Bash(git -C * push -u origin chantier/*)` and `PowerShell(…)` | the same with `git -C <worktree>` | as above | documented (rule form) |
| `Bash(git push --force-with-lease -u origin chantier/*)` and `PowerShell(…)` | a Driver's push after a rebase, and the stack driver's restack, one command per branch (`driver.md`, Push) | a lease-protected force push of any `chantier/` branch; a Driver pushes only its own CR's branch (`driver.md`, Push); the rule's `*` does not enforce that, the card does | documented (rule form) |
| `Bash(git -C * push --force-with-lease -u origin chantier/*)` and `PowerShell(…)` | the same from outside the worktree, the form refused 4 times as "Git Destructive" | as above, in any repository the `-C` path names; a Driver pushes only its own CR's branch (`driver.md`, Push); the rule's `*` does not enforce that, the card does | documented (rule form); **refused with the rule set**: batch-23, CR-318, a Driver in auto mode, `Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Destructive or Unwanted Actions].` |
| `Bash(git push --force-with-lease=chantier/* origin *chantier/*)` and `PowerShell(…)` | the steering session's route (the Foreman's, then the Chief of Staff's) for a refused force push: `git push --force-with-lease=<branch>:<expected> <remote> <sha>:refs/heads/<branch>` | as above | documented (rule form) |
| `Bash(git -C * push --force-with-lease=chantier/* origin *chantier/*)` and `PowerShell(…)` | the steering session's route when its directory is not the main checkout, always with a planning surface (the project's clone that `take` names): `git -C <checkout> push --force-with-lease=<branch>:<expected> <remote> <sha>:refs/heads/<branch>` | a lease-protected force push of any `chantier/` branch, in any repository the `-C` path names; the steering session pushes only a branch the check ties to this batch (`foreman-refused.md`, "A Driver's refused force push"); the rule's `*` does not enforce that, the card does | documented (rule form) |
| `Bash(git -C * rebase origin/*)` and `PowerShell(…)` | the Driver's rebase onto the base (`driver.md`, "Means: rebase and push"): `git -C <worktree> rebase <remote>/<branch>`, a CR on the default branch, and the GitLab fold onto the remote branch | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(git -C * rebase chantier/*)` and `PowerShell(…)` | the same onto the bare `chantier/` branch of the CR under it in a series or a stack (the command refused in markdown-okf-schema-studio batch-09, 2026-11-23) | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(git -C * rebase --onto chantier/* *)` and `PowerShell(…)` | a restack onto a `chantier/` base: `git -C <worktree> rebase --onto <chantier/ branch> <sha or branch>` (`driver.md`) | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(git -C * rebase --onto origin/* *)` and `PowerShell(…)` | the CR at the bottom after a drop: `git -C <worktree> rebase --onto <remote>/<default branch> <branch>` (`driver.md`) | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(git -C * rebase --continue)` and `PowerShell(…)` | a rebase stopped at a conflict, continued by the conflict-resolver (`conflict-resolver.md`) | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(git -C * rebase --abort)` and `PowerShell(…)` | a rebase given up (`driver.md`) | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(git rebase origin/*)` and `PowerShell(…)` | the same without `-C`, from the checkout the session stands in (`chief-of-staff.md`, the surface's checkout) | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(git rebase chantier/*)` and `PowerShell(…)` | the same onto a `chantier/` branch, without `-C` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(git rebase --onto chantier/* *)` and `PowerShell(…)` | the same restack, without `-C` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(git rebase --onto origin/* *)` and `PowerShell(…)` | the same, without `-C` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(git rebase --continue)` and `PowerShell(…)` | the same, without `-C` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(git rebase --abort)` and `PowerShell(…)` | the same, without `-C` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented (rule form); the classifier on a subagent's matching command **unproved** (the batch-23 case stands); refused with no rule set in markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions" |
| `Bash(uv run --no-sync --project "<checkout>" chantier *)` and `PowerShell(…)`, `<checkout>` filled with the checkout's real path as P10 prints it | every `$CHANTIER` command in chantier's own checkout, when the session's project is chantier, the dev mode (`merge`, `ship`, `spawn`… were refused 5 times) | every chantier subcommand of the checkout at that path (`gate` runs only the long gates the code repository's `chantier.yaml` names, and `lease hold` runs nothing) | rule matching proved (main session, `dontAsk`; 2026-11-21, Claude Code 2.1.326, Windows 11); auto mode and a Driver (subagent) **unproved**: whether auto mode drops it as a "package-manager run command" is not documented (checked 2026-11-09); trial: enter auto mode with the rule set, run `$CHANTIER status`, see whether the classifier is asked |
| `Bash(uv sync --locked --project "<checkout>")` and `PowerShell(…)`, `<checkout>` filled the same way | the steering session's checked sync of chantier's own checkout, which waits for holders, when the session's project is chantier, at a session's or a batch's start and after a merge that changes `uv.lock` (the dev mode) | a sync of the checkout at that path, from its lockfile | rule matching proved (main session, `dontAsk`; 2026-11-21, Claude Code 2.1.326, Windows 11); auto mode and a Driver (subagent) **unproved** |
| `Bash(uv sync --locked --check --project "<checkout>")` and `PowerShell(…)`, `<checkout>` filled the same way | the steering session's read-only check before a sync, the dev mode: exit 0 in sync, 1 with "The environment is outdated" (the skills' `$CHANTIER` paragraph) | none: it writes nothing | rule form documented; trial by hand on a throwaway project, 2026-11-21, uv 0.13.6, Windows 11: `uv sync --locked` then `--check` gave 0; after a version bump in `pyproject.toml` and in `uv.lock`'s own package, `--check` gave 1 with "The environment is outdated"; with a stale `uv.lock` (a dependency added to `pyproject.toml` only), `--check` gave 1 with the same text and the real `uv sync --locked` failed with "The lockfile at `uv.lock` needs to be updated"; matching with the rule set, auto mode and a Driver **unproved** |
| `Bash(uvx --from "<plugin root>" chantier *)` and `PowerShell(…)`, `<plugin root>` filled with the plugin's real path as P10 prints it | every `$CHANTIER` command of an installed plugin, or of another project's session run from chantier's checkout, the plugin mode | every chantier subcommand of the plugin at that path (`gate` runs only the long gates the code repository's `chantier.yaml` names, and `lease hold` runs nothing); for another project run from chantier's checkout, the rule names the checkout's path and lets through every chantier subcommand of the build uv caches from it | rule matching proved (main session, `dontAsk`; 2026-11-21, Claude Code 2.1.326, Windows 11); auto mode and a Driver (subagent) **unproved**: whether auto mode drops it as a "package-manager run command" is not documented (checked 2026-11-09); trial: enter auto mode with the rule set, run `$CHANTIER status`, see whether the classifier is asked |
| `Bash(gh pr create*)` and `PowerShell(…)` | a Driver opens its PR (refused once as "Git Destructive") | any PR on any repository `gh` can reach | documented (rule form) |
| `Bash(gh pr edit*)` and `PowerShell(…)` | a Driver's body (`--body-file`) and the stack driver's retarget (`--base`); refused in batch-15 | any edit of any PR `gh` can reach | documented (rule form) |
| `Bash(gh pr ready*)` and `PowerShell(…)` | a PR turned ready, or back to draft (`--undo`) | a PR turned ready, or back to draft | documented (rule form) |
| `Bash(gh pr checks*)` and `PowerShell(…)` | a Driver reads its CI | read-only | documented (rule form) |
| `Bash(gh pr view*)` and `PowerShell(…)` | a Driver or the steering session reads a PR | read-only | documented (rule form) |
| `Bash(gh pr close*)` and `PowerShell(…)` | the Chief of Staff's drop of a CR to the trash closes its PR (`order drop`, `cancel`) | closing any PR `gh` can reach | documented (rule form) |
| `Bash(gh pr reopen*)` and `PowerShell(…)` | a restored CR's PR reopens | reopening any PR `gh` can reach | documented (rule form) |
| `Bash(gh stack*)` and `PowerShell(…)` | the stack on the forge, only when `gh extension list` names `gh-stack` | any operation of the extension | **unproved**: the rule form for an extension command is not documented; trial: set it, run `gh stack view` in auto mode |
| `Bash(glab mr create*)` and `PowerShell(…)` | a Driver opens its MR on GitLab (`driver.md`: `glab mr create --draft`) | any MR on any project `glab` can reach | documented (rule form) |
| `Bash(glab mr update*)` and `PowerShell(…)` | a Driver's description or the stack's retarget on GitLab | any MR edit on any project `glab` can reach | documented (rule form) |
| `Bash(glab mr view*)` and `PowerShell(…)` | a Driver reads its MR | read-only | documented (rule form) |
| `Bash(glab mr close*)` and `PowerShell(…)` | the same close, on GitLab | closing any MR `glab` can reach | documented (rule form) |
| `Bash(glab mr reopen*)` and `PowerShell(…)` | a restored CR's MR reopens | reopening any MR `glab` can reach | documented (rule form) |
| `Bash(glab ci status*)` and `PowerShell(…)` | a Driver reads its CI on GitLab (`glab ci status --live`) | read-only | documented (rule form) |
| `SendMessage` | the Foreman and the Drivers message each other (refused twice) | any message between this session's agents and sessions | **unproved**: `SendMessage` as a rule is not documented (absent from tools-reference, checked 2026-11-09); trial: set it, enter auto mode, have the Foreman message a Driver |

A broad chantier rule, a `*` where the path belongs (`uvx --from * chantier *`,
`uv run --no-sync --project * chantier *`, `uv sync --locked --project *`, `uv sync *`, and the
older `uv run --script * *` and `uv run --locked --project * chantier *`), lets any command
through: `uvx` runs any package from any source, and the middle `*` of the `uv run` forms matches
`uv run --no-sync --project . python -c ... chantier x`. P10 judges by matching, finds each
broad rule in your settings, names it with its file and the real-path rule that replaces it
(marked `present` when it is set too), or says "no chantier command needs it"; it warns even when
every command is allowed. The Chief of Staff offers to add the replacing rules at once, and you
remove the broad rule by hand: chantier never removes or edits a rule of yours, so no command
meets a prompt in between.

The plugin's real path changes when the host moves the plugin's folder (an update, if the host's
folder holds the version: **unproved**): the old rule then stops matching, P10 names the new rule
as missing and the old one as stale, with its file, and the Chief of Staff asks again, one
question per update; you remove the stale rule by hand. In the plugin mode P10 takes any other
plugin-form path as an old copy, on the assumption of one plugin copy per install (**unproved**);
in the dev mode it leaves plugin-form rules alone, and names a dev rule stale only when its
folder no longer exists.

There is no `gh api` rule: it would allow any API write. The stack on the forge is changed only
by `$CHANTIER forge-stack` (covered by the two `chantier` rules) or the `gh stack` extension.

The base set holds no release, merge or tag rule, by design: a release is rare, public and
irreversible, and the host's check is a second guard at publication. When the user grants a
release to run on its own, or fixes to merge on a grant, the Chief of Staff offers the rules of
that capability ("Capabilities and their commands"), and only then.

The same rules as one block, ready to paste into the `permissions.allow` array of
`~/.claude/settings.json` (a test compares it with the CLI's list):

```json
{
  "permissions": {
    "allow": [
      "Bash(git push -u origin chantier/*)",
      "PowerShell(git push -u origin chantier/*)",
      "Bash(git -C * push -u origin chantier/*)",
      "PowerShell(git -C * push -u origin chantier/*)",
      "Bash(git push --force-with-lease -u origin chantier/*)",
      "PowerShell(git push --force-with-lease -u origin chantier/*)",
      "Bash(git -C * push --force-with-lease -u origin chantier/*)",
      "PowerShell(git -C * push --force-with-lease -u origin chantier/*)",
      "Bash(git push --force-with-lease=chantier/* origin *chantier/*)",
      "PowerShell(git push --force-with-lease=chantier/* origin *chantier/*)",
      "Bash(git -C * push --force-with-lease=chantier/* origin *chantier/*)",
      "PowerShell(git -C * push --force-with-lease=chantier/* origin *chantier/*)",
      "Bash(git -C * rebase origin/*)",
      "PowerShell(git -C * rebase origin/*)",
      "Bash(git -C * rebase chantier/*)",
      "PowerShell(git -C * rebase chantier/*)",
      "Bash(git -C * rebase --onto chantier/* *)",
      "PowerShell(git -C * rebase --onto chantier/* *)",
      "Bash(git -C * rebase --onto origin/* *)",
      "PowerShell(git -C * rebase --onto origin/* *)",
      "Bash(git -C * rebase --continue)",
      "PowerShell(git -C * rebase --continue)",
      "Bash(git -C * rebase --abort)",
      "PowerShell(git -C * rebase --abort)",
      "Bash(git rebase origin/*)",
      "PowerShell(git rebase origin/*)",
      "Bash(git rebase chantier/*)",
      "PowerShell(git rebase chantier/*)",
      "Bash(git rebase --onto chantier/* *)",
      "PowerShell(git rebase --onto chantier/* *)",
      "Bash(git rebase --onto origin/* *)",
      "PowerShell(git rebase --onto origin/* *)",
      "Bash(git rebase --continue)",
      "PowerShell(git rebase --continue)",
      "Bash(git rebase --abort)",
      "PowerShell(git rebase --abort)",
      "Bash(uv run --no-sync --project \"<checkout>\" chantier *)",
      "PowerShell(uv run --no-sync --project \"<checkout>\" chantier *)",
      "Bash(uv sync --locked --project \"<checkout>\")",
      "PowerShell(uv sync --locked --project \"<checkout>\")",
      "Bash(uv sync --locked --check --project \"<checkout>\")",
      "PowerShell(uv sync --locked --check --project \"<checkout>\")",
      "Bash(uvx --from \"<plugin root>\" chantier *)",
      "PowerShell(uvx --from \"<plugin root>\" chantier *)",
      "Bash(gh pr create*)",
      "PowerShell(gh pr create*)",
      "Bash(gh pr edit*)",
      "PowerShell(gh pr edit*)",
      "Bash(gh pr ready*)",
      "PowerShell(gh pr ready*)",
      "Bash(gh pr checks*)",
      "PowerShell(gh pr checks*)",
      "Bash(gh pr view*)",
      "PowerShell(gh pr view*)",
      "Bash(gh pr close*)",
      "PowerShell(gh pr close*)",
      "Bash(gh pr reopen*)",
      "PowerShell(gh pr reopen*)",
      "Bash(gh stack*)",
      "PowerShell(gh stack*)",
      "Bash(glab mr create*)",
      "PowerShell(glab mr create*)",
      "Bash(glab mr update*)",
      "PowerShell(glab mr update*)",
      "Bash(glab mr view*)",
      "PowerShell(glab mr view*)",
      "Bash(glab mr close*)",
      "PowerShell(glab mr close*)",
      "Bash(glab mr reopen*)",
      "PowerShell(glab mr reopen*)",
      "Bash(glab ci status*)",
      "PowerShell(glab ci status*)",
      "SendMessage"
    ]
  }
}
```

Two rules described here that P10 does not check:

- `mcp__ccd_pr__set_monitor`: Claude Desktop's PR monitor (auto-fix), refused twice in the
  user's week. No chantier card uses it, to arm or to disarm (see "Auto-fix events"). Risk: the session arms auto-fix on a PR. Rule form
  documented; the tool itself is Claude Desktop's, **unproved** here. The eval kit's workspace
  allows it for its operator (`evals/README.md`).
- `Edit(<the folder that holds the repository and its .worktrees>/**)` (the user's form:
  `Edit(~/Projets/**)`): lets agents edit in the CR worktrees next to the repository. Risk: every
  file below that folder. Not checked: the path is the user's.

What not to add, and why (**documented**, <https://code.claude.com/docs/en/permission-modes>,
<https://code.claude.com/docs/en/auto-mode-config>): auto mode drops on entry, and restores on
leaving, broad rules: `Bash(*)`, `PowerShell(*)`, interpreter wildcards, package-manager run
commands (`PowerShell(uv run *)`), every `Agent` rule and every `Monitor` rule. So no
`Agent(chantier:cr-driver)` rule is recommended: starting a Driver in auto mode stays the
classifier's call (refused 3 times in the user's week). The `Agent(Name)` form exists
(documented); plugin agent names in it (`chantier:<role>`): **unproved**, not documented.

### Capabilities and their commands

The one table of what chantier's agents run, by capability. P10's `SAMPLES` follow its order and
a test compares them. P10 checks only the capabilities the batch will use (`$CHANTIER preflight
--mode stack --autonomous-releases N --grant-fixes`, as `open` takes them) and names those it did
not check. Each rule is written `Bash(<rule>)` and, on Windows, `PowerShell(<rule>)`; `origin` is
the project's remote name. A missing rule is a strong warning, never a failure: the host's
auto-mode classifier judges each command at run time, and in a remote session (Remote Control)
nobody may be there to answer its prompt.

| Capability | Used when | Commands its agents run | Rules | Trial before the go | Mark |
| --- | --- | --- | --- | --- | --- |
| Every batch | always | `$CHANTIER ...` (dev, chantier's own checkout, when the session's project is chantier: `uv run --no-sync --project "<checkout>" chantier ...`, after the steering session's checked sync, which waits for holders (the skill's `$CHANTIER` paragraph); plugin: `uvx --from "<plugin root>" chantier ...`; the two placeholders filled with the real path P10 prints); a Driver's push `git push -u <remote> chantier/...` and `git -C <worktree> push -u <remote> chantier/...`; the rebase `git [-C <worktree>] rebase <base>` (and `--onto`, `--continue`, `--abort`; never `--exec`) and the force push after it `git [-C <worktree>] push --force-with-lease -u <remote> chantier/...`; the steering session's route `git [-C <checkout>] push --force-with-lease=<branch>:<sha> <remote> <sha>:refs/heads/<branch>`; on GitHub `gh pr create`, `edit` (with `--base`), `ready` (with `--undo`), `checks`, `view`, `close`, `reopen`; on GitLab `glab mr create`, `update`, `view`, `close`, `reopen`, `glab ci status`; `SendMessage` | `git push -u origin chantier/*`<br>`git -C * push -u origin chantier/*`<br>`git push --force-with-lease -u origin chantier/*`<br>`git -C * push --force-with-lease -u origin chantier/*`<br>`git push --force-with-lease=chantier/* origin *chantier/*`<br>`git -C * push --force-with-lease=chantier/* origin *chantier/*`<br>`git -C * rebase origin/*`<br>`git -C * rebase chantier/*`<br>`git -C * rebase --onto chantier/* *`<br>`git -C * rebase --onto origin/* *`<br>`git -C * rebase --continue`<br>`git -C * rebase --abort`<br>`git rebase origin/*`<br>`git rebase chantier/*`<br>`git rebase --onto chantier/* *`<br>`git rebase --onto origin/* *`<br>`git rebase --continue`<br>`git rebase --abort`<br>`uv run --no-sync --project "<checkout>" chantier *`<br>`uv sync --locked --project "<checkout>"`<br>`uv sync --locked --check --project "<checkout>"`<br>`uvx --from "<plugin root>" chantier *`<br>`gh pr create*`<br>`gh pr edit*`<br>`gh pr ready*`<br>`gh pr checks*`<br>`gh pr view*`<br>`gh pr close*`<br>`gh pr reopen*`<br>`glab mr create*`<br>`glab mr update*`<br>`glab mr view*`<br>`glab mr close*`<br>`glab mr reopen*`<br>`glab ci status*`<br>and the bare tool rule SendMessage | `$CHANTIER preflight`; `git -C <main checkout> push --force-with-lease -u <remote> chantier/preflight-trial --dry-run`; `gh pr view --json number` (GitHub) or `glab mr view` (GitLab) | documented (rule form); the `chantier` and SendMessage rules **unproved** (see the table above); a Driver's `git -C` force push was refused with its rule set (batch-23, CR-318); the stack driver's rebase and force push were refused with no rebase rule set (markdown-okf-schema-studio batch-09, 2026-11-23, "Destructive or Unwanted Actions"); a refusal climbs the ladder of `foreman-refused.md`, "A Driver's refused force push" or "A Driver's refused rebase" |
| A stack | `--mode stack` (or `order mode --note stack`, from any mode) | the above, plus the native stack: `gh stack ...` when the user took the `gh stack` extension, else `$CHANTIER forge-stack create\|rebuild\|show\|unstack` (covered by the `chantier` rule; it calls the stacks API itself) | `gh stack*` | `gh stack view`; with `forge-stack`, the stacks API probe of P9 | **unproved** (the rule form of an extension command) |
| A release on its own | `--autonomous-releases N` at `open`, or `order grant <release-cr> --note "releases=<n>..."` | the merge of the release PR by the steering session (`gh pr merge <pr> --<the project's method>`, or on GitHub for a PR in a native stack `gh api -X PUT repos/<owner>/<repo>/pulls/<pr>/merge-async ...` and its result `gh api -X GET .../merge-async/<uuid>`, after the stack read `gh api -X GET repos/<owner>/<repo>/stacks ...`; `glab mr merge ...`), the tag push (`git push <remote> v1.2.3`), the publication (`gh release create v1.2.3 ...`, `glab release create v1.2.3 ...`), and what the project's procedure names (for chantier: `just tag`, `uv run --script scripts/release_notes.py ...`: the project's own, no rule offered) | `gh pr merge*`<br>`gh api -X GET repos/*/stacks*`<br>`gh api -X PUT repos/*/pulls/*/merge-async*`<br>`gh api -X GET repos/*/pulls/*/merge-async/*`<br>`glab mr merge*`<br>`git push origin v*`<br>`gh release create*`<br>`glab release create*` | `git push <remote> v0.0.0-preflight-trial --dry-run`; `gh release create`, the merge and the asynchronous merge: no trial, P10's rule check only | documented (rule form); the merge route for a PR in a native stack is unproved by an agent. Risk: any merge of any PR `gh` can reach, any asynchronous merge of any PR `gh` can reach (it merges every open PR below it in its stack), a push of any `v*` tag, any release on any repository `gh` can reach |
| Fixes on a grant | `--grant-fixes` at `open`, or `order grant ... fixes=on` | the merge of a fix PR by the steering session (`gh pr merge ...`, or for a PR in a native stack the stack read and the asynchronous merge of the release row, `glab mr merge ...`) | `gh pr merge*`<br>`gh api -X GET repos/*/stacks*`<br>`gh api -X PUT repos/*/pulls/*/merge-async*`<br>`gh api -X GET repos/*/pulls/*/merge-async/*`<br>`glab mr merge*` | no harmless form: no trial, P10's rule check only | documented (rule form); the route for a PR in a native stack is unproved by an agent. Risk: any merge of any PR `gh` can reach, any asynchronous merge of any PR `gh` can reach (it merges every open PR below it in its stack) |

The rows "A release on its own" and "Fixes on a grant" are offered only when the user grants them:
without a grant, the host's prompt and its classifier keep guarding these commands. They are not
in the pasteable block above. A tag whose name does not start with `v` is not covered by the tag
rule and gets the strong warning.

### What stays refused

No allow rule for these; when the host refuses or asks, the agent reports it (concepts rule 7),
and chantier does not do them unasked. Each with why:

- `git commit --amend --reset-author`: rewrites authorship.
- `git branch -D` with `git push origin --delete`, and `git update-ref -d`: delete refs; the
  Foreman's removal of a merged CR's branch and the Chief of Staff's of a dropped CR's (on the
  user's word) stay asked, not allowed.
- `Remove-Item -Recurse -Force` (or `rm -rf`) on `.claude`, or on temporary folders named by a
  wildcard (`claude-eval-*`, `chsmoke-*`): a pattern can reach what is not chantier's.
- A subagent's Write of a `.md` file whose name starts with `report`, `summary`, `findings` or
  `analysis` (case-insensitive, the file name only): the host refuses it before any permission
  check, with "Subagents should return findings as text, not write report files. Include this
  content in your final response instead." The rule is as users report it in
  <https://github.com/anthropics/claude-code/issues/44657> and
  <https://github.com/anthropics/claude-code/issues/101519>: **unproved** by Anthropic. Proof by
  probe (Write by a subagent, 2026-11-10): refused `report.md`, `findings.md`,
  `report-format.md`, `summary.md`, `analysis.md`; accepted `04-result.md`, `04-report.md`,
  `04-summary.md`, `04-findings.md`, `04-analysis.md`, `status-layout.md`, `progress-report.md`
  and the other chantier names (`delivery.md`, `STATUS.md`, `retro.md`, `work/` files, ...).
  Name a subagent's file with a number first, such as `04-result.md` (the rule: concepts,
  "Starting an agent"); this is the host's own rule on the name, before the auto-mode classifier
  and any permission check.

### Auto mode

- Allow, ask and deny matches resolve at once in auto mode, without the classifier, except
  protected paths, critical-path `rm`/`rmdir` and per-command domains (**documented**,
  <https://code.claude.com/docs/en/permission-modes>). Seen otherwise for a subagent. In batch-23
  (CR-318), the classifier refused a Driver's `git -C <worktree> push --force-with-lease -u origin
  chantier/...` that the user's allow rule matched (P10 said allowed). Whether the classifier
  judges a subagent's command despite a matching allow rule is **unproved**, not documented. A
  refusal goes the route of `driver.md`.
- 2026-11-23 (markdown-okf-schema-studio, batch-09, stack mode, no rebase rule set): the classifier
  refused the stack driver's `git rebase` of the CR-470 worktree onto CR-471, then its `git push
  --force-with-lease`, with "Destructive or Unwanted Actions"; the question climbed Driver,
  Foreman, Chief of Staff, user. P10 now names the rebase rules, and a Driver's prompt holds a
  `Rewrites:` line that names the rebase and the push and their scope ("A Driver's prompt",
  `concepts.md`). Trial, to record here with its date and exact text: the next batch in auto mode
  where a Driver, with the `Rewrites:` line and the rules set, rebases onto a `chantier/` base and
  force-pushes, accepted or refused. Whether the line changes the classifier's judgement is
  **unproved**.
- The classifier label "Git Destructive" and `claude auto-mode defaults`, which lists the
  classifier's rules: **documented** (<https://code.claude.com/docs/en/auto-mode-config>). The
  labels "Merge Without Review" and "Create Public Surface", and "Destructive or Unwanted Actions"
  (batch-23), seen in the user's week:
  **unproved**, not documented (checked 2026-11-09).
- A refusal is reported with its exact text (concepts rule 7). A refused force push climbs the
  ladder written in `foreman-refused.md`, "A Driver's refused force push" (Driver, Foreman, Chief of
  Staff, the user's yes); the Driver records the refused command and text before it sends the push
  line (`driver.md`), so a refusal on a command an allow rule matches is told apart from one with
  no rule. Cause: the classifier blocks destructive git in subagents ("Git Destructive"); the
  steering session's own `git -C <worktree> push --force-with-lease=...` went through (**proved
  by use**, 2026-11-11, batch-09; not always: refused on 2026-11-13 as a loop). Batch-09 was a
  direct batch, the Chief of Staff steering (its archive:
  `5-archives/261111-1247-171-batch-09-retro-fixes/work/retro.md`, "direct mode, the Chief of
  Staff steering"; `261111-0840-170-force-push-judgement/02-answers.md`), so that use proves the
  Chief of Staff's case, not the Foreman's. The Foreman's push, per case: the Foreman is not a
  subagent but a session of its own, started with the user's permission mode (row "Start the
  Foreman's session");
  - **with the route rule set:** an allow rule resolves a matching command before the classifier
    for a steering session (**documented**, <https://code.claude.com/docs/en/permission-modes>;
    not yet seen for the Foreman);
  - **without it** (P10 names it missing): the Foreman does not try (`push not tried: route rule
    missing`); whether the classifier would pass it is **unproved**;
  - trial: the next Driver refusal in a Foreman batch, the Foreman's push accepted or refused, its
    exact text recorded here with the date.
- **The user's yes:** the classifier judges a command with the conversation as context; a user's
  own yes in the Chief of Staff's conversation, to a question that names the exact command, is what
  lets it see that the push is wanted. Mark: **unproved** unless the auto-mode docs say it (the
  Driver checks <https://code.claude.com/docs/en/auto-mode-config> and marks it documented with the
  link, or unproved with "checked <date>"); trial: the first push asked to the user this way,
  accepted or refused, recorded here.
- Batch-15 (night of 2026-11-12 to 13): the classifier refused lease-protected force pushes of
  `chantier/` branches to the stack driver, then to the steering session itself (a PowerShell
  loop), and it refused `gh pr edit --base`, a stack update through `gh api`, and `gh release
  create`. An allow rule resolves a matching command before the classifier (except batch-23, CR-318, above); a loop, a script or a
  chain matches no prefix rule, so the classifier judges it alone: one command per branch.
- What a trial before the go can and cannot prove (the Chief of Staff's trials, "Capabilities and
  their commands"):
  - an allow rule resolves a matching command at once, before the classifier (documented), for the steering session; for a Driver, see batch-23 above: a
    trial that runs where P10 says a rule matches proves the host honours that rule's form, which
    settles the unproved rows (the auto-mode fate of `uv run --no-sync --project "<checkout>" chantier *` (chantier's own checkout, when the session's project is chantier) and `uvx --from "<plugin root>" chantier *`, `gh stack*`);
  - the host offers no way to try a rule ahead for the commands with no harmless form (`gh
    release create`, `gh pr merge`, `gh api -X PUT .../merge-async`, `gh pr edit --base`, `SendMessage`): the classifier judges
    them at run time. Their only check before the go is P10's rule match;
  - a harmless form the classifier lets through with no rule proves nothing for the real command:
    it judges each command on its own;
  - a trial runs in the Chief of Staff's session; the classifier blocks destructive git in
    subagents, so a trial that passes there with no rule says nothing about a Driver.
- The alert the Chief of Staff gives, once, at its first turn: "Auto mode's classifier refuses
  some rebases and force pushes. They come with every rebase: a Driver's rebase and its push after it, and the stack
  driver's restack of every PR above a change. Without the rules below, an unattended batch
  waits for you at the first one; with them, a Driver's force push may still be refused (batch-23). A refused one goes to the Foreman, then to the Chief of Staff, who each run a legitimate one on the Driver's own branch without asking you; you are asked only if the host refuses the Chief of Staff too, or when a judgement finds a push not legitimate; a push of a branch that is not chantier's is never run, you are told of it; and in a remote session nobody may be there to answer."

### What the docs do not say

Each **unproved**, not documented (checked 2026-11-09):

- `CLAUDE_CODE_ENTRYPOINT` and its values (`claude-desktop`): preflight P1 relies on it, and it
  holds in use; the env-vars page does not list it.
- The exact text "File has not been read yet". Documented: a Write to an existing file not read
  first fails on older models; newer models may overwrite under conditions (v2.1.228+)
  (<https://code.claude.com/docs/en/tools-reference>). Seen 177 times in the user's week, mostly
  from subagents.
- PowerShell assignments and allow rules; `SendMessage` as a rule; plugin names in `Agent(…)`;
  the auto-mode fate of `uv run --no-sync --project "<checkout>" chantier *` (chantier's own checkout, when the session's project is chantier) and `uvx --from "<plugin root>" chantier *` (as above).
- Whether a running session picks up a change of the settings files: not checked; the block of
  "Allow rules to add" says to start a new session.

## Compacting

Auto-compact is on by default. What the user sets is its window: the `/autocompact` command and
the `autoCompactWindow` setting. Documented: <https://code.claude.com/docs/en/settings>.
`/compact` continues the same conversation, connected devices follow it, and `$CHANTIER cost`
keeps the transcript; `/clear` may replace it. No role runs it: the person types it.

Documented (<https://code.claude.com/docs/en/settings-reference>,
<https://code.claude.com/docs/en/prompt-caching>):

- `autoCompactWindow`: 100000 to 1000000; the default is tuned per model; capped at the model's
  context window.
- `idleCompaction`: default true; compacts after about an hour idle; Claude Code v2.1.290 and
  later.
- The prompt cache lasts 1 h on a subscription within plan usage, 5 min on an API key or a cloud
  provider; `promptCacheTtl` sets it. Why it matters: Chief of Staff and Foreman sessions last
  days (393 messages and 50 compactions in 45 h for one), with pauses past the cache's life.

**Measured** (batch-16 and batch-17, 2026-11-13): agents set to `autoCompactWindow: 200000` on
`claude-sonnet-5-5` compacted after a last prompt of 161,951 to 166,684 tokens (three Coders).
Sessions set to 300000 compacted around 165 to 170k (the user's week). This matches a window capped
at the model's 200,000 with a reserve of about 35k, but the cap's value stays unproved until the
trial reads it back: one session, the setting read with `/autocompact`, the token count at the
first compaction recorded here. Drivers of batch-18 and of both eval runs of 2026-11-15 peaked at
80k to 124k with no compaction.

**Recommendation**, not a proved fact: keep `idleCompaction` on (its default), and set
`autoCompactWindow` to 300000 in `~/.claude/settings.json` for the Chief of Staff's and the
Foreman's sessions (the plugin's agents carry 200,000 in their files). Why: long sessions with
pauses past the cache's life. The window is capped at the model's context window (documented,
above): if Sonnet 5.5's window is below 300K, the cap applies. Whether 300000 holds, given the
measured 165 to 170k compaction above (which concerns this very value), is unproved: the same
trial settles the recommendation and records the cap.

```json
{ "idleCompaction": true, "autoCompactWindow": 300000 }
```

## Reload after a compaction

The plugin's mod hooks the engine's `session.compact` event. After every compaction of the main
conversation, manual (`/compact`) or automatic, of a session that loaded the `chantier`,
`chief-of-staff` or `griller` skill, it adds one message to the compacted conversation: the
role line ("You are the <role> in a chantier session; after this compaction, call your chantier
skill again with the argument reload."; the router's line, "You are in a chantier session; ...",
when no role), the role being the last role skill loaded. The skill then reads the seat and
follows `session-start.md`, "5. Reload" (loading the other role's skill when the seat says so),
and the answer opens with one line saying chantier's rules were reloaded. It does not rely on the
summary or on the model noticing. It never vetoes a compaction, and it leaves a subagent's own
compaction alone (a Driver's, a worker's). The `status` skill does not count as a role.

The contract is the engine's own (`claude-code/index.d.ts`: the hook's `next(e)` resolves
`{ messages }`, to which the mod adds its message), checked 2026-11-10 against the engine's types
as they stood on 2026-11-06. **Unproved** until seen in a session; trial: a Chief of Staff session,
`/compact`, then the next turn calls a chantier skill with `reload` (Skill tool call visible:
record which one the model picked, the role's or the router) and the answer opens with the
reloaded line. The mod is Claude Code's only (`CONTRIBUTING.md`): the automatic reload exists only
where the plugin's mod loads. The manual reload ("chantier reload", or `/chantier:chantier
reload`, `/chantier:chief-of-staff reload`, `/chantier:griller reload`) works everywhere, and is what a session without the mod has.

## The write guard

The plugin's mod also hooks `agent.spawn` and `tool.call`. It reads one line of a spawn's
prompt, `writes: <absolute folder>; <absolute folder>` (a worker's prompt holds it, with the
worktree first and the CR folder second; a CR Driver's holds its CR folder, then the absolute archive path
when `take` prints one: `concepts.md`, "A Driver's prompt"). It knows no role
and no card wording. A spawn whose prompt holds the line starts in the first folder,
except a spawn whose prompt also holds a `worktree:` line (a CR Driver's). That one starts in
that worktree, or, while the worktree does not exist yet, in the project's root its first line
names (the main checkout, or the project's clone with a planning surface). With neither, it
starts in its parent's folder, still guarded, with the board's note. The mod rewrites the
spawn's `cwd`, except on a resume. The mod records its agent id with the
folders. That agent's Write, Edit or NotebookEdit outside every folder is refused, with the one
message `refused: <path> is outside the folders this agent may write in (<folder>; <folder>);
write there`; a relative path is read against the folder it runs in. On Windows a Git Bash drive path (`/c/Users/...`) is read as its drive form (`C:/Users/...`), for Write, Edit, NotebookEdit and the shell targets alike. The arguments of a
`tool.call` sit flat beside `tool` (`file_path` for Write and Edit, `notebook_path` for
NotebookEdit), and the mod reads nothing else. An entry is a bare absolute path: the guard reads
anything after it as part of the folder's name, so every write is refused.

The same agent's Bash or PowerShell call is judged by the same rule, on the write forms the mod
can see with a target path: a redirection `>` or `>>`, `tee`, `sed -i`, `perl -i`, `cp`, `mv`,
`rm`, `touch`, `truncate`, `Set-Content`, `Add-Content`, `Out-File`, `Clear-Content`, `New-Item`,
`Copy-Item`, `Move-Item`, `Remove-Item`, `Rename-Item` and `[IO.File]::Write*`. A target outside
every folder, read against the agent's folder like a relative path of Write, is refused with
`refused: a shell write to <path> is outside the folders this agent may write in (<folder>;
<folder>); the shell follows the same rule as Write and Edit`. Passed: a write to a null device
(`$null`, `/dev/null`, `NUL`) or `2>&1`, and a command that is `git`, `gh`, `glab` or the
chantier CLI, which write by their nature. The guard is role-free: a worker's shell writes in its
worktree and CR folder pass, as its Write does.

A guard that cannot judge lets the call pass and says so in the CR board's note, for instance
`Write guard: could not read the Write call of agent <id> (no file_path); the call passed.`: a
missing, empty or non-text path, a `writes:` line it cannot read (an entry that is not an
absolute path leaves the agent unguarded and unmoved), a shell target that holds a variable or
`~`, follows a `cd`, `Set-Location` or `pushd`, or a call the mod cannot parse, or anything its
own code throws. A guard at fault costs nothing.

Not guarded: the main session (the Chief of Staff, the Foreman), the Release driver, the stack
driver, the QA driver, the Spec-writer, the Spec critic, the Griller, the Demo explorer, any agent with no
`writes:` line, and the shell writes the mod cannot see (an interpreter's inline code such as
`python -c` or `node -e`, a script's own writes): the card's rule covers those, and after a
report's `git status` of the main checkout, the steering session names what changed there
(`chief-of-staff-steering.md`). The host's scratchpad is outside the worktree: a
worker writes in its work folder instead. The host's instruction to send scripts and intermediate
results to its scratchpad does not apply to a CR's work, which goes in the CR's folder
([concepts](../concepts.md)). Copilot has no such guard, and the line is inert there.

The refusals are proved by `hooks/register.test.tsx`, run with `just mod`. The passes are proved
by the next real eval's normal use, and the audit checks each worker's prompt holds the line:
**Unproved** until that eval reports. No refusal is planted.

## Classes of session

| Class | How it is known | Can start a session | Fit for a Foreman |
| --- | --- | --- | --- |
| Desktop, typed at the keyboard | no Remote Control notice | yes | yes, it starts it alone |
| Desktop, driven by Remote Control | the host's Remote Control notice | yes, with no `cwd` and no `preset`, in its own folder; a start with `cwd` or `preset` is refused (proved 2026-11-20) | yes, on a main checkout: it starts a new Foreman in its own folder, or reuses the last one |
| Session on the main checkout | `git rev-parse --git-dir` equals `--git-common-dir` | n/a | yes |
| Session in a worktree | they differ | n/a | no: Write refuses the main checkout, `change_directory` is refused, `request_directory` does not help |
| Remote or app session | often starts in a linked worktree, `.claude/worktrees/<name>`: the row above | n/a | no, as the worktree row says; proved 2026-11-10, Battlestation, session `epic-lamport-b88c2f`: preflight P6 and P7 failed and the hook refused writes in the main checkout's planning folder |
| Cloud | the host's environment | n/a | no: no main checkout |
| Session in a planning surface | its folder is the surface's checkout, or the project's main checkout (its clone) with the surface added as a working directory; preflight P6 and P7 accept both and refuse a linked worktree of either | n/a | yes, in both setups: the sessions run there and write the planning folder by absolute paths; a session started with no `cwd` lands there (proved 2026-11-20, the Studio's batch-07 Foreman and chantier's batch-29 Foreman). Whether the host lets it write in the project's clone and worktrees, outside its folder (`checkout.yml`), on the surface's checkout: **unproved** |

With no argument the Chief of Staff's batches are direct in the Remote Control row and on any
entry where the Foreman-mode P1 fails (terminal, VS Code), and Foreman in the "Desktop, typed" row
(`chief-of-staff-batch-start.md`, "Starting a batch").

Proved: the worktree row, batch-06, 2026-11 (the user picked the `chantier` entry under "Remote
Control": it names the main checkout, shows no worktree option, the session landed in a
worktree, and Write refused `.agents/changes/`, so Drivers were blocked). The refusal on a
Remote Control session to start a session in another place: proved in use, 2026-11-20 (a start with a `cwd`, the planning surface or the eval root, or with a saved `preset` is refused with "The user is working over Remote Control, and this turn can't start that session"). The cloud row: unproved; trial: start a
Foreman there and run `git rev-parse --show-toplevel`; the same trial tells a cloud session, for
`Remote` in the title. A Remote Control session is told by its notice (the Remote Control row),
for the offer to fork.

`mcp__ccd_directory__change_directory` to the repository's root was refused for a session in an
isolated worktree, even clean with no commit (proved 2026-11-10, same session). So moving to the
main checkout is the user's step: a new session on the main checkout, without worktree ("For you"
below).

**The rule: starting a session from Remote Control (proved 2026-11-20).** From a session driven by
Remote Control, every session start (a Foreman, a Griller) is `mcp__ccd_session__start_session`
with **no `cwd` and no `preset`** and `use_worktree: false`. Remote Control refuses a start in
another place, not every start: a `cwd` (the planning surface, the eval root) or a saved `preset`
gets "The user is working over Remote Control, and this turn can't start that session". With
neither, the new session lands in the steering session's own folder, its main checkout
(`--git-dir` equals `--git-common-dir`). That folder must be a main checkout, in one of two
setups: the planning surface's checkout, or the project's main checkout with the surface added as
a working directory. Preflight P6 and P7 accept both main checkouts (the surface's, the project's clone) and refuse a linked worktree of either; a Foreman started with no `cwd` lands in the same folder and its preflight passes the same way. A worktree session is unfit, as the worktree row says. What lies outside that
folder reaches the new session by absolute paths in its prompt (`$CHANTIER` already carries
`--project <absolute folder>`; the Foreman's prompt gives `Repository:` and the skill's folder as
absolute paths). At the desk the same start works and stays the default; no card names a `cwd`.
Seen 2026-11-20, Battlestation: the Studio's Chief of Staff ran in the Studio's main checkout, and
its batch-07 Foreman (Sonnet 5.5, effort medium), started with no `cwd`, landed there, passed its
worktree check, claimed its batch, wrote to the surface by absolute paths and started a Driver;
two Grillers were started the same way. chantier's own Chief of Staff runs in
`C:\Users\gaeta\Projets\chantier` with the surface added: its batch-29 Foreman landed in that
folder, and session `local_9ef60aad-22ce-4ab4-9dd6-80cf84213736` was started there too.

**A Chief of Staff and Grillers in remote.** Proved, batch-06 (2026-11-10): a session the user
creates from the remote client's "Remote Control" entry lands in a worktree, which blocks
chantier's planning on the default branch. Proved 2026-11-20: a session started *by* a Chief of
Staff driven by Remote Control, with no `cwd`, lands on that Chief of Staff's main checkout (the
rule above). So the Chief of Staff is still started locally (desktop, no worktree), then put in
remote (Remote Control). From there it can start a Foreman in its own folder, and a Griller
session on the user's word; a Griller in a never-merged worktree is no longer the only way to
have a Griller in remote. The Chief of Staff's own next batch is direct by itself.

Documented, not proved here: the desktop docs say Worktree is off by default and is set per
environment (<https://code.claude.com/docs/en/desktop>); `claude remote-control --spawn
same-dir` keeps the folder and `--spawn worktree` isolates
(<https://code.claude.com/docs/en/remote-control>). Not documented: creating a session from a
phone on a Desktop host, and its options.

**The trial that settles a new Foreman from a remote client.** Settled 2026-11-20 for a Foreman
started by the Chief of Staff with no `cwd` (the rule above, the trials quoted there). Still
unproved: a session the user creates from the remote client's own New session on a chosen folder
(trial, on the user's word: from the remote client, pick the "Remote Control" entry and, in a
second try, the "Local" group's entry or a saved environment with Worktree off; in each, run `git
rev-parse --git-dir --git-common-dir`, and record the path that lands on the main checkout).

## Surfaces and options

The surfaces where the user can be: the phone (or another device) on Remote Control; the desktop
app, typed at the keyboard; a terminal (the CLI).

How the host signals the surface: the desktop app adds a Remote Control notice to the conversation
when the user works through Remote Control (proved 2026-11-10, Battlestation: said at each turn's
end that day). A terminal gives no signal, and no signal is said when the user is at the desktop
app's keyboard: the absence of the notice does not prove the user is at the machine. The class row
"no Remote Control notice" ("Desktop, typed") above is qualified by this. Where there is no
notice, the host says nothing: offer every option that fits, each with its condition ("Offering options", `chief-of-staff-any.md`). The notice also sets the mode of a batch planned with no argument:
direct (`chief-of-staff-batch-start.md`, "Starting a batch"). Whether the notice appears on a turn typed at the
desktop in a session connected to Remote Control (the setting "Connect new sessions to Remote
Control") is **unproved**; trial: in such a session, type one turn at the desktop and one from the
phone, and record which carries the notice. Until then the rule holds as written and a forced
`foreman` is the user's way. The rest of this section is **unproved** except where a mark says
otherwise.

| Option | Desktop, typed | Remote Control | Terminal | Why and mark |
| --- | --- | --- | --- | --- |
| Switch to Foreman mode | yes | yes: a new Foreman with no `cwd`, or a reused one ("Reusing the last Foreman") | no | preflight P1 fails in a terminal; proved 2026-11-20 for the first two (the rule above) |
| Switch to direct mode | yes | yes, except the stop of a Foreman not answering (needs the machine) | yes | needs only the Chief of Staff's own session; unproved until a real switch runs (trial: the first real switch, its events showing the `steering` event `direct` and each `resume: switch to direct mode` take) |
| Run a command in a terminal | yes | no | yes | Remote Control has no shell; unproved |
| Open `localhost` or a file path | yes | no: send the file or a forge link | yes | unproved |
| `/permissions`, `/config` | no: the app's own settings | no | yes | terminal dialogs; unproved |
| Restart the app, `/reload-plugins`, open in an editor | yes (terminal: restart the CLI) | no | restart the CLI | the machine; unproved |
| `/chantier-board` | yes | the pane does not show in a Remote Control view (`docs/boards.md`) | yes | documented in `docs/boards.md` |
| The remote board (`chantier serve`) | yes | yes, from any device on the local network, through the link, once `board.host: network` (or `--host`) opens it to the local network | yes | unproved; trial: open the board's link from the phone on the local network during a batch |
| Review renders, review and merge a PR | yes | yes | yes | the forge, from any device |
| A host feature (scheduled wake, start a session, a monitor) | where the host has it | `start_session` with no `cwd` and no `preset` works; with either, it is refused | where the host has it | proved 2026-11-20 for `start_session`, unproved for the rest |
| Work in the main checkout | not during an eval, not from a worktree session | same | same | the classes table and the project's rules |
| Resume a stopped subagent | `SendMessage` to its agent id resumes it with its context | same | same | proved, batch-15 (a refused spec-writer resumed by a message); not for a subagent the host stopped (its `task_status` `killed`, the notice `Task "<name>" (<id>) was stopped.`): `SendMessage` gets `Agent <id> was stopped and won't be resumed. Treat its work as cancelled; only launch a new agent if the user explicitly asks.`, proved, batch-22 (agents `a0106566b6aa3f0cb`, `a103955deaf241307`, `a164f7a02355addd0`, refused at 20:49:19Z to 20:49:22Z on 2026-11-16); chantier uses it for the `taken back:` note and the `record your hand-back` note of `foreman.md`: a refused agent answers it with its refusal; proved again, batch-18, twice (`a2c1f342e038708e6` and `ae6e32e6270cf2ba5` recorded their hand-back within 10 seconds of the message) |
| End a subagent's turn with nothing running in the background | the host asks for its hand-back at once (`[handback-send-enforce] Your report has not been delivered. Call SubagentHandback…`), before a resumed worker's reply arrives; a background shell's end wakes it (the CI wait of `driver.md`) | same | same | proved, batch-16 (the CR-216 Driver, agent `ac87782157e90d829`; the CR-215 Driver's Inspector reply came after its hand-back) |
| A background subagent stops | `<task-notification>` summary `Agent "<name>" is waiting on its own background work`: the agent stopped with background work of its own running, and resumes when that work reports, so it has not ended. `Agent "<name>" finished`: it stopped with no live background child, and its `SubagentHandback` report arrives as a message | same | same | proved, batch-18, Foreman session `446cff2e-8291-4f73-9ff0-f19c29743e6e` (four Drivers that waited for their own gate, each with the first notification) |
| A background subagent is stopped from outside | what chantier detects, and nothing else: the stop a compaction snapshot reports (the steering transcript's `attachment` record `task_status` with `status: "killed"` and the agent's id as `taskId`, seen by the session as `Task "<name>" (<id>) was stopped.`), and the refusal of a message to it | same | same | proved, batch-22, a manual compaction (Chief of Staff session `91f1382a-eacd-437e-b5a8-f9e545753a8c`, agents `a0106566b6aa3f0cb`, `a103955deaf241307`, `a164f7a02355addd0`). Unproved: what a stop made by the user in the app leaves in the steering transcript; trial: in a session with a background subagent, the user stops it in the app; record whether and when a `task_status` `killed` record or another record appears, before and after a compaction |

## A Foreman in a worktree asks

The Foreman checks before it claims its epoch (its card). In a worktree it takes no CR and sends
the ask. The Chief of Staff tells the user the impact: Write is refused in the planning folder, so
no Driver can leave its work and evidence there. Then it gives the "For you" block of a new
Foreman, to start again on the main checkout. This reference names no way around the refusal. A
user may allow one for a batch: that word stays in that batch, is sent with the user's own
words, and never becomes a rule.

## Reusing the last Foreman

When the previous batch's Foreman session still exists, even stopped, the Chief of Staff may
reuse it with the new batch and its epoch 1 (a new batch starts at 0). It does not continue the
old Foreman's epoch. Its title names the old batch: the prompt's title makes it rename itself.

- An idle session answers a message (`SendMessage`): **proved**, a Chief of Staff's message
  started a turn in an idle Foreman session.
- `foreman set --epoch 1` accepted in a reused session: **proved**, same trial.
- A session whose process has ended (closed): **unproved**. Claude Code's docs do not say a
  message reaches it, and describe waking it by a reply from the user, who pastes the prompt into
  it. Trial: after closing a Foreman session, send it a message from the Chief of Staff and see
  whether a turn starts. Do not tell the user that a message wakes a closed session.

What a choice costs, said first: a new session starts with an empty context; a reused Foreman
carries its old context, and the batch pays for it. Before a reuse, always recommend `/compact`
in the Foreman's session, not `/clear`.

## Sessions of one repository

- The seat: liveness is asked of the host (the Tools row), never read from a date. Where the host
  cannot tell, the session asks the user (the "looks stopped" line of `session-start.md`).
  Unproved until the session tool is recorded.
- A fork: what it inherits (the conversation), whether it gets its own session id and transcript
  id (`$CLAUDE_CODE_SESSION_ID`), and whether anything tells it it is a fork: unproved; trial:
  fork a Chief of Staff session, compare `get_session("self")` and the variable with the seat. If
  the fork has its own id, comparing it with the seat at its next turn makes it a Griller; if not,
  record here that a fork cannot be told apart and that the user says "you are a griller" in it.
- A Griller in a worktree sends its files by `SendMessage` to the seat's session, naming the
  absolute paths; the Chief of Staff on the main checkout reads them under
  `.claude/worktrees/<name>/`. Unproved; trial: one file sent and placed.
- The two-Chiefs case and the hand-over lines travel by `SendMessage` like the rest (unproved
  between two sessions of the user, as the Tools row says).

## The "For you" block

Whenever a step is the user's, the Chief of Staff gives one block, in the user's language, always
these four parts, and says first what the choice costs when it has one:

1. **Where:** the device and the app.
2. **Do:** each choice by its label on screen, in order.
3. **Paste:** the text in its own code block, complete: no placeholder left.
4. **You should see:** what comes next and within how long; otherwise, say what you see.

Every block below is **unproved** until it was followed once by hand; the Chief of Staff says
"I have not tested this path" for it.

### A new Foreman, at the desktop

Nothing for the user: `start_session` as above. The user only gives the go.

### A new Foreman, from a remote client

Nothing for the user: the Chief of Staff starts it with no `cwd`, as at the desk (proved
2026-11-20). Cost: none beyond a fresh context; a worktree session blocks writes, so the Chief of
Staff's session must be on a main checkout. The user only gives the go. A session the user
creates from the remote client's own New session on a chosen folder stays unproved (trial above).

### A planning surface: the project's folders

Cost: none. **Unproved** (trial: a Chief of Staff in a surface whose Driver creates a worktree
from the clone and commits there). A session in the surface writes in the project's clone and
worktrees, outside its folder; the host must allow them.

- **Where:** Claude Code, the surface's session.
- **Do:** add the project's clone and its worktrees folder as additional working directories
  (`/add-dir <path>`, or `additionalDirectories` in `.claude/settings.json`).
- **Paste:** the two absolute paths `checkout.yml` resolves to, complete.
- **You should see:** the Driver's `git worktree add` and commit accepted; else tell me the
  refusal as written.

### A reused Foreman

Cost: its context is carried, and the batch pays for it.

- **Where:** the Foreman's session, on any device.
- **Do:** type `/compact`; wait for it to end.
- **Paste:** nothing; I send the prompt by message. If the session is closed, paste the prompt
  into it (next block).
- **You should see:** `ready <batch>` in my session within a few minutes.

### A closed Foreman session

Cost: as a reuse. Unproved that a message wakes it, so the user pastes.

- **Where:** the desktop app, the Foreman's session in the list.
- **Do:** open the session, then click its input.
- **Paste:** the prompt, in its own code block, complete.
- **You should see:** the session starts a turn and I hear `ready <batch>` within a few minutes.

### A session on the main checkout

Cost: a fresh context; the files hold the state, nothing is lost once the start check found the
worktree clean with no commit. **Unproved** until followed once.

- **Where:** the Claude Desktop app (or the remote client).
- **Do:** start a new session on the repository's folder, with Worktree off (the labels as the
  desktop docs give them; documented: <https://code.claude.com/docs/en/desktop>).
- **Paste:** `/chantier:chief-of-staff` or `/chantier:griller`.
- **You should see:** the session's introduction with no start-check failure; else tell me what
  the session shows.

### A Chief of Staff and Grillers in remote

Built on the batch-06 finding (2026-11-10: a session the user creates from the remote client
lands in a worktree) and the 2026-11-20 rule (a session the Chief of Staff starts with no `cwd`
lands on its main checkout), so the Chief of Staff starts locally. Chantier explains the steps and
never does them. The path is **unproved** as a whole until followed once by hand.

1. Start the Chief of Staff locally, in the desktop app, with no worktree and the tools allowed in
   auto mode (your own steps), then run `/chantier:chief-of-staff` (or `/chantier:chantier`).
2. Put that session in remote (Remote Control). In remote, reuse this session; with no argument
   its next batch is direct by itself, and a forced `foreman` starts a new Foreman in its own
   folder.
3. Optionally, on your word the Chief of Staff starts a Griller session with no `cwd`, in its own
   folder; or you start Griller sessions in worktrees that are never merged: they send their files
   to the Chief of Staff, which places them.
4. Each session renames itself.

What is not possible on the host (a fork that cannot be told apart) is written here as found, with
no workaround.

### `/compact`

Cost: none beyond the summary; the same conversation continues.

- **Where:** the session to compact, typed at its input.
- **Do:** type `/compact` and send.
- **Paste:** when I ask to keep something, the line I give you in its own code block.
- **You should see:** a summary and a smaller context size within a minute.

### Allow rules to add

The command line the Chief of Staff gives when the host refused its edit of
`~/.claude/settings.json`, or when that file cannot be read as JSON (P10 prints
`unreadable: ...`). Otherwise the Chief of Staff adds the rules itself, on the user's yes
(`chief-of-staff.md`, "The project"). Unproved until a user has followed it once, like every
block above.

- **Where:** at the computer running Claude Desktop, not on the phone, in your shell (Windows
  PowerShell 5.1, or a POSIX shell).
- **Do:** run one command line, the one for your shell, with the rules P10 named in its list. Then
  start a new session: whether a running session picks up a settings change is **unproved** (see
  "What the docs do not say").
- **Paste:** that line. It merges exactly the rules P10 named into `permissions.allow` of
  `~/.claude/settings.json`. It creates the file and the keys when they are absent, keeps every
  other key and rule, adds no rule twice, and never replaces or removes anything. It writes valid
  JSON in UTF-8 with no byte-order mark.
- **You should see:** at the next preflight, `P10 ok`, or a P10 line that no longer names them.

The Chief of Staff fills in only the list of rules: the strings P10 named, in their table order,
with the project's remote name in place of `origin` and the real path in place of `<checkout>` or
`<plugin root>` (the check rule's `<checkout>` too), complete, no placeholder. A path holding a `'` breaks the quoting of the two
command lines below: the Chief of Staff says so instead of giving them. Each was run by
hand on a scratch home folder in three cases (file absent, file with other keys, file already
holding some of the rules), twice each: valid JSON, no byte-order mark, no duplicate, nothing
removed, and `preflight` reads it back as `P10 ok`.

Windows PowerShell 5.1 (the file is rewritten as compact JSON, with the same keys and values; a
character such as `<` or `'` in another value of the file may come back as its `\u` escape):

```powershell
Add-Type -AssemblyName System.Web.Extensions; $r = '<rule 1>','<rule 2>'; $p = Join-Path $HOME '.claude\settings.json'; $js = New-Object System.Web.Script.Serialization.JavaScriptSerializer; $d = if (Test-Path $p) { $js.DeserializeObject([IO.File]::ReadAllText($p, [Text.Encoding]::UTF8)) } else { @{} }; if (-not $d.ContainsKey('permissions')) { $d['permissions'] = @{} }; if (-not $d['permissions'].ContainsKey('allow')) { $d['permissions']['allow'] = @() }; $a = @($d['permissions']['allow']); foreach ($x in $r) { if ($a -notcontains $x) { $a += $x } }; $d['permissions']['allow'] = $a; New-Item -ItemType Directory -Force (Split-Path $p) | Out-Null; [IO.File]::WriteAllText($p, $js.Serialize($d), (New-Object Text.UTF8Encoding $false))
```

POSIX shell (needs `uv`, which chantier needs anyway; the file is rewritten with a two-space
indent):

```sh
uv run --no-project python -c 'import json,os,sys;p=os.path.expanduser("~/.claude/settings.json");d=json.load(open(p,encoding="utf-8-sig")) if os.path.exists(p) else {};a=d.setdefault("permissions",{}).setdefault("allow",[]);a+=[r for r in dict.fromkeys(sys.argv[1:]) if r not in a];s=json.dumps(d,indent=2,ensure_ascii=False)+"\n";os.makedirs(os.path.dirname(p),exist_ok=True);open(p,"w",encoding="utf-8",newline="\n").write(s)' '<rule 1>' '<rule 2>'
```
