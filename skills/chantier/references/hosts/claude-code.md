# Claude Code (Claude Desktop)

What is proper to this host: the tools, the heartbeat, the sessions, and what only the user can
do. The cards say what a role judges and point here. Read it with your card when you run on
Claude Code.

Each behaviour carries a mark:

- **proved**: seen on the host, with where and when;
- **documented**: the host's documentation says so, with the link; not seen here;
- **unproved**: nobody has seen it, and the trial that settles it is named. Never tell the user an
  unproved behaviour as a fact: say it is not known, and what would settle it.

## Tools

| Generic | Claude Code | Mark |
| --- | --- | --- |
| Start the Foreman's session | `mcp__ccd_session__start_session` with `initiation: "user_asked"`, `title: "<title>"`, `context: "fresh"`, `use_worktree: false`, `model: "claude-sonnet-5-5"`, `effort: "medium"`, the user's permission mode; leave it linked | the start: proved, every batch started from Claude Desktop (v0.3 on); with this model: **unproved** until seen. Trial: batch-11, where the Foreman was switched to Sonnet 5.5 after its `ready` (CR-174), then the first batch started with this row: the transcript shows `claude-sonnet-5-5`, and `effort: "medium"` is accepted with it. Record the date once seen |
| Own session id and title | `get_session("self")`; the transcript's id is `$CLAUDE_CODE_SESSION_ID` | proved, same |
| Set a session's own title (the Chief of Staff, a Griller, the Foreman) | `set_session_title` | proved for a Chief of Staff's own session, 2026-11-08 (Battlestation, a session renamed itself); the Foreman's case stays unproved: the trial is a Foreman that sets its title and `get_session("self")` shows it |
| The skills | `/chantier:chantier` (the router), `/chantier:chief-of-staff [foreman|direct]`, `/chantier:griller`, `/chantier:status`, `/chantier:chantier reload` (the router with the argument `reload`): a plugin's `skills/<name>/` is `/<plugin>:<name>` | documented: <https://code.claude.com/docs/en/plugins-reference> (skills); the argument's handling (only the first word of `chief-of-staff` counts) is unproved until a session shows it, and the reload's until a reload runs; trial: type `/chantier:chantier reload` after a `/compact`, see the one line and no introduction |
| Load another skill (the router) | the host's Skill tool | unproved until the router runs; trial: `/chantier:chantier` in a session with no Chief of Staff, answer a role, see the skill load |
| List the sessions and their state; is the seat's session alive | the session tools found in the `mcp__ccd_session__` set: the exact tool and its states are not recorded | unproved; trial: two sessions on one repository, one stopped, list both and record the states |
| Message another session of the user (hand-over, a Griller's line) | `SendMessage` to its session id | proved for the Chief of Staff's session (the row above); between two sessions of the user, unproved; trial: a Griller's `ready` line to the Chief of Staff's session |
| A session's link (for the seat) | what `get_session` gives | unproved until recorded; trial: `get_session("self")` and note the link field |
| Start a Driver or a worker | `Agent`, `run_in_background: true` for a Driver, `subagent_type: <agent>`; the plugin's agent is `chantier:<role>`; the model, only when `$CHANTIER` printed one (`team:` or `playbook`): the `model` parameter, set to the printed start value (an alias: `opus`, `sonnet` or `haiku`), as printed; no effort | the agent: proved, same; the model: capability yes (alias), proved 2026-11-10 (trial below) |
| Start the Spec-writer (Chief of Staff) | `Agent`, `run_in_background: true`, `subagent_type: chantier:spec-writer`; the `model` parameter as in the row above, only when `$CHANTIER playbook` printed one; no effort | the agent: unproved until a CR is specified this way; the model: capability yes (alias), proved 2026-11-10 |
| Message a Driver | `SendMessage` to the agent id | proved, same |
| Message the Chief of Staff | `SendMessage` to its session id | proved, same |
| A Driver messages its steering session (the Foreman; in direct mode the Chief of Staff, which is `main` there) | `SendMessage` to `main` | proved, same; in direct mode the same mechanism, unproved until a direct batch runs |
| Stop a Driver | `TaskStop` | proved, same |
| Agent ids of the project | the `name:` of a file in `.claude/agents/` or `~/.claude/agents/` | proved, same |
| Models | the Spec-writer runs Opus 5.5; the Foreman, every Driver and the workers run Sonnet 5.5, unless the project's `chantier.yaml` sets a model; a task under escalation (`concepts.md`, "Escalation") runs the escalation model that `$CHANTIER playbook` prints | proved, same, except the CR driver, the stack and release drivers and the Foreman: unproved; the trial is the model their transcripts show in the next batch (the Foreman: the trial in the row "Start the Foreman's session") |
| Models at an agent's start (capability, start value) | capability: yes. Start value: an alias, which the CLI's table maps from the exact identifier: `claude-opus-5-5` (Claude Opus 5.5) is `opus`, `claude-sonnet-5-5` (Claude Sonnet 5.5) is `sonnet`, `claude-haiku-5-5` (Claude Haiku 5.5) is `haiku`. The full identifier is not recorded as accepted | proved 2026-11-10: a trial started a plugin agent through `Agent` with `model: haiku`, and its transcript showed `claude-haiku-5-5`; the other two aliases are the same mechanism, unproved one by one |
| Skills and tools of a session (what the Chief of Staff compares a role's needs with) | not recorded: how a session lists its skills and its tools, and whether a subagent sees what the session sees | unproved; trial: a `chantier.yaml` naming one skill that is installed and one that is not; the Chief of Staff names only the second; and a subagent started with a need says whether it has it |
| Preflight P2 | `mcp__ccd_session__start_session` loads | proved, same |
| Ask the user a series of questions (grill, specification) | the host's question tool (`AskUserQuestion`), at most 4 questions per call, at most 4 options per question, plus the tool's own free answer ("Other"); the reference opens each question's text (the tool's short header field, if used, does not need to hold it). Remote Control relays the same tool: the user sees the same 4-question form on the phone. Under Remote Control the form shows above the conversation and the text written before it is read by scrolling up: the text is written before every call all the same | the figures: the user's statements (2026-11-14, CR-250 answers 5 and 11), unproved; trials: one call with 4 questions shown and a fifth refused; the same series from the phone under Remote Control, all 4 shown. The scrolling: observed by the user, 2026-11-14 (CR-250 answer 17) |
| Run the board | `Bash` with `run_in_background: true` and the command `$CHANTIER board --seat <id>`; its first lines are read from the background task's output; stopped with the host's stop of a background shell | unproved; trial: a Chief of Staff starts it, `GET /api/board` with the key answers from the machine, and the output shows the start line |
| The board when the session ends | whether the host ends a background command when the session ends (closed, or stopped) | unproved; trial: start the board, end the session, ask `GET /api/board` with the key. Until proved, the board stops when the seat moves (the CLI), which does not depend on it |

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
run 1, 2026-11-12). Each wake is scheduled with `ScheduleWakeup`, 30 minutes (1800 seconds) after
the last. It ends the
heartbeat, never its session, with `ScheduleWakeup` `stop: true` (after `chantier status
--stop-heartbeat --batch <batch> --epoch <n>`, which `pause` already does): right after `pause`,
and on a wake where no Driver of any kind (CR, stack, QA, release) has run since the last wake
and no order is undone. An order's line or a `ping` starts a turn; if it leaves a Driver running, the
Foreman arms the heartbeat again. No wake ever arriving is a stop. Proved: same.

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
  card's usual route: the CR goes back to a Driver with `take <cr> --note "<why>"` (`foreman.md`,
  "Your means": a red check, or the ready PR that stopped merging with `--note "rebase: …"`). It
  never does what the event asks itself. If the forge shows nothing wrong, nothing is done.
- **Both steerings.** The same rule holds for whichever session steers: the Foreman, or the Chief
  of Staff in direct mode.
- **A PR that is not a batch's** (the user's own PR in the same session) is out of chantier's
  rule: it is between the user and the app. This section speaks of a batch's PRs only.
- **chantier never arms, disarms or unbinds the PR monitor.** No card uses the app's PR monitor
  (`mcp__ccd_pr__set_monitor`), to arm it or to disarm it, and chantier writes no setting of it (the only settings it
  writes are the allow rules of "Configuration", on the user's yes).
- **The cost.** Even ignored, each event starts a turn of the steering session, which the user
  pays for.
- **Turning Auto-fix off.** **Unproved**: no documentation and no dated trial gives the path, so
  none is given here. Trial that settles it: in the Claude Desktop app, find the setting that
  turns Auto-fix off for a session or a PR, turn it off, open a PR from a subagent, and see that
  no Auto-fix event arrives; record the labels and the date here. Turning it off also loses
  Auto-fix for the user's own PRs in that session.
- **During a normal batch chantier stays silent** about Auto-fix: it does not ask the user to turn
  it off, has no preflight check for it and gives no "For you" line for it (chantier cannot see
  whether Auto-fix is on, and a line at every go would be noise). It only ignores the events as
  above. Only the eval guide asks for Auto-fix off, before a real campaign. A tip may come later,
  from a measure of the ignored turns' cost in a real batch.
- **Mark of the section.** The rule (the live Driver, no live Driver and both-steerings points,
  and the event-is-not-an-order point) is **unproved** until the next real campaign shows it.
  Trial: an Auto-fix event arrives on a CR's PR during a real eval campaign, and the steering
  session ends its turn with no tool call on that PR and no message to its Driver (a CR with a
  live Driver), or checks the forge and uses `take --note` (a CR with none).

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
- The Foreman and the Drivers read this file with their card (their prompts already name it):
  "Auto mode" tells them what a refusal means and that it is reported, never worked around.
- The workers do not read this file; what they need (one command per call, read before you
  overwrite, no leading assignment, `git -C`) is in `concepts.md`, rule 9.

### Prerequisites

| Tool | Needed for | Checked by | Missing |
| --- | --- | --- | --- |
| `git` | every Driver, the CLI's reads | P5 (CLI) | preflight fails |
| `uv` | `$CHANTIER` (`uv run --locked --project` in chantier's own checkout, `uvx --from` as a plugin) | P5 (CLI) | preflight fails |
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
| `Bash(git push --force-with-lease -u origin chantier/*)` and `PowerShell(…)` | a Driver's push after a rebase, and the stack driver's restack, one command per branch (`driver.md`, Push) | a lease-protected force push of any `chantier/` branch | documented (rule form) |
| `Bash(git -C * push --force-with-lease -u origin chantier/*)` and `PowerShell(…)` | the same from outside the worktree, the form refused 4 times as "Git Destructive" | as above, in any repository the `-C` path names | documented (rule form) |
| `Bash(git push --force-with-lease=chantier/* origin *chantier/*)` and `PowerShell(…)` | the steering session's route for a refused force push: `git push --force-with-lease=<branch>:<expected> <remote> <sha>:refs/heads/<branch>` | as above | documented (rule form) |
| `Bash(uv run --locked --project * chantier *)` and `PowerShell(…)` | every `$CHANTIER` command in chantier's own checkout, the dev mode (`merge`, `ship`, `spawn`… were refused 5 times) | any local project whose script is named `chantier` | **unproved**: whether auto mode drops it as a "package-manager run command" is not documented (checked 2026-11-09); trial: enter auto mode with the rule set, run `$CHANTIER status`, see whether the classifier is asked |
| `Bash(uvx --from * chantier *)` and `PowerShell(…)` | every `$CHANTIER` command of an installed plugin, the plugin mode | any package that `uvx` can run from any source, named `chantier` | **unproved**: whether auto mode drops it as a "package-manager run command" is not documented (checked 2026-11-09); trial: enter auto mode with the rule set, run `$CHANTIER status`, see whether the classifier is asked |
| `Bash(gh pr create*)` and `PowerShell(…)` | a Driver opens its PR (refused once as "Git Destructive") | any PR on any repository `gh` can reach | documented (rule form) |
| `Bash(gh pr edit*)` and `PowerShell(…)` | a Driver's body (`--body-file`) and the stack driver's retarget (`--base`); refused in batch-15 | any edit of any PR `gh` can reach | documented (rule form) |
| `Bash(gh pr ready*)` and `PowerShell(…)` | a PR turned ready, or back to draft (`--undo`) | a PR turned ready, or back to draft | documented (rule form) |
| `Bash(gh pr checks*)` and `PowerShell(…)` | a Driver reads its CI | read-only | documented (rule form) |
| `Bash(gh pr view*)` and `PowerShell(…)` | a Driver or the steering session reads a PR | read-only | documented (rule form) |
| `Bash(gh stack*)` and `PowerShell(…)` | the stack on the forge, only when `gh extension list` names `gh-stack` | any operation of the extension | **unproved**: the rule form for an extension command is not documented; trial: set it, run `gh stack view` in auto mode |
| `Bash(glab mr create*)` and `PowerShell(…)` | a Driver opens its MR on GitLab (`driver.md`: `glab mr create --draft`) | any MR on any project `glab` can reach | documented (rule form) |
| `Bash(glab mr update*)` and `PowerShell(…)` | a Driver's description or the stack's retarget on GitLab | any MR edit on any project `glab` can reach | documented (rule form) |
| `Bash(glab mr view*)` and `PowerShell(…)` | a Driver reads its MR | read-only | documented (rule form) |
| `Bash(glab ci status*)` and `PowerShell(…)` | a Driver reads its CI on GitLab (`glab ci status --live`) | read-only | documented (rule form) |
| `SendMessage` | the Foreman and the Drivers message each other (refused twice) | any message between this session's agents and sessions | **unproved**: `SendMessage` as a rule is not documented (absent from tools-reference, checked 2026-11-09); trial: set it, enter auto mode, have the Foreman message a Driver |

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
      "Bash(uv run --locked --project * chantier *)",
      "PowerShell(uv run --locked --project * chantier *)",
      "Bash(uvx --from * chantier *)",
      "PowerShell(uvx --from * chantier *)",
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
      "Bash(gh stack*)",
      "PowerShell(gh stack*)",
      "Bash(glab mr create*)",
      "PowerShell(glab mr create*)",
      "Bash(glab mr update*)",
      "PowerShell(glab mr update*)",
      "Bash(glab mr view*)",
      "PowerShell(glab mr view*)",
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
  documented; the tool itself is Claude Desktop's, **unproved** here.
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
| Every batch | always | `$CHANTIER ...` (dev: `uv run --locked --project <checkout> chantier ...`; plugin: `uvx --from <plugin> chantier ...`); a Driver's push `git push -u <remote> chantier/...` and `git -C <worktree> push -u <remote> chantier/...`; the force push after a rebase `git [-C <worktree>] push --force-with-lease -u <remote> chantier/...`; the steering session's route `git push --force-with-lease=<branch>:<sha> <remote> <sha>:refs/heads/<branch>`; on GitHub `gh pr create`, `edit` (with `--base`), `ready` (with `--undo`), `checks`, `view`; on GitLab `glab mr create`, `update`, `view`, `glab ci status`; `SendMessage` | `git push -u origin chantier/*`<br>`git -C * push -u origin chantier/*`<br>`git push --force-with-lease -u origin chantier/*`<br>`git -C * push --force-with-lease -u origin chantier/*`<br>`git push --force-with-lease=chantier/* origin *chantier/*`<br>`uv run --locked --project * chantier *`<br>`uvx --from * chantier *`<br>`gh pr create*`<br>`gh pr edit*`<br>`gh pr ready*`<br>`gh pr checks*`<br>`gh pr view*`<br>`glab mr create*`<br>`glab mr update*`<br>`glab mr view*`<br>`glab ci status*`<br>and the bare tool rule SendMessage | `$CHANTIER preflight`; `git -C <main checkout> push --force-with-lease -u <remote> chantier/preflight-trial --dry-run`; `gh pr view --json number` (GitHub) or `glab mr view` (GitLab) | documented (rule form); the `chantier` and SendMessage rules **unproved** (see the table above) |
| A stack | `--mode stack` (or `order mode --note stack`) | the above, plus the native stack: `gh stack ...` when the user took the `gh stack` extension, else `$CHANTIER forge-stack create\|rebuild\|show` (covered by the `chantier` rule; it calls the stacks API itself) | `gh stack*` | `gh stack view`; with `forge-stack`, the stacks API probe of P9 | **unproved** (the rule form of an extension command) |
| A release on its own | `--autonomous-releases N` at `open`, or `order grant <release-cr> --note "releases=<n>..."` | the merge of the release PR by the steering session (`gh pr merge <pr> --<the project's method>`, `glab mr merge ...`), the tag push (`git push <remote> v1.2.3`), the publication (`gh release create v1.2.3 ...`, `glab release create v1.2.3 ...`), and what the project's procedure names (for chantier: `just tag`, `uv run --script scripts/release_notes.py ...`: the project's own, no rule offered) | `gh pr merge*`<br>`glab mr merge*`<br>`git push origin v*`<br>`gh release create*`<br>`glab release create*` | `git push <remote> v0.0.0-preflight-trial --dry-run`; `gh release create` and the merge: no trial, P10's rule check only | documented (rule form). Risk: any merge of any PR `gh` can reach, a push of any `v*` tag, any release on any repository `gh` can reach |
| Fixes on a grant | `--grant-fixes` at `open`, or `order grant ... fixes=on` | the merge of a fix PR by the steering session (`gh pr merge ...`, `glab mr merge ...`) | `gh pr merge*`<br>`glab mr merge*` | no harmless form: no trial, P10's rule check only | documented (rule form). Risk: any merge of any PR `gh` can reach |

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
  Name a subagent's file with a number first, such as `04-result.md`.

### Auto mode

- Allow, ask and deny matches resolve at once in auto mode, without the classifier, except
  protected paths, critical-path `rm`/`rmdir` and per-command domains (**documented**,
  <https://code.claude.com/docs/en/permission-modes>).
- The classifier label "Git Destructive" and `claude auto-mode defaults`, which lists the
  classifier's rules: **documented** (<https://code.claude.com/docs/en/auto-mode-config>). The
  labels "Merge Without Review" and "Create Public Surface", seen in the user's week:
  **unproved**, not documented (checked 2026-11-09).
- A refusal is reported with its exact text (concepts rule 7). A refused force push takes the
  route already written (`driver.md`, `foreman.md`: Driver → Foreman → Chief of Staff). Cause:
  the classifier blocks destructive git in subagents ("Git Destructive"); the steering session's
  own `git -C <worktree> push --force-with-lease=...` went through (**proved by use**,
  2026-11-11, batch-09; not always: refused on 2026-11-13 as a loop). So the route ends in the
  steering session, which judges and runs the push without asking the user
  (`chief-of-staff.md`).
- Batch-15 (night of 2026-11-12 to 13): the classifier refused lease-protected force pushes of
  `chantier/` branches to the stack driver, then to the steering session itself (a PowerShell
  loop), and it refused `gh pr edit --base`, a stack update through `gh api`, and `gh release
  create`. An allow rule resolves a matching command before the classifier; a loop, a script or a
  chain matches no prefix rule, so the classifier judges it alone: one command per branch.
- What a trial before the go can and cannot prove (the Chief of Staff's trials, "Capabilities and
  their commands"):
  - an allow rule resolves a matching command at once, before the classifier (documented): a
    trial that runs where P10 says a rule matches proves the host honours that rule's form, which
    settles the unproved rows (`uv run ... chantier *`, `uvx --from * chantier *`, `gh stack*`);
  - the host offers no way to try a rule ahead for the commands with no harmless form (`gh
    release create`, `gh pr merge`, `gh pr edit --base`, `SendMessage`): the classifier judges
    them at run time. Their only check before the go is P10's rule match;
  - a harmless form the classifier lets through with no rule proves nothing for the real command:
    it judges each command on its own;
  - a trial runs in the Chief of Staff's session; the classifier blocks destructive git in
    subagents, so a trial that passes there with no rule says nothing about a Driver.
- The alert the Chief of Staff gives, once, at its first turn: "Auto mode's classifier refuses
  some force pushes. They come with every rebase: a Driver's push after a rebase, and the stack
  driver's restack of every PR above a change. Without the rules below, an unattended batch
  waits for you at the first one, and in a remote session nobody may be there to answer."

### What the docs do not say

Each **unproved**, not documented (checked 2026-11-09):

- `CLAUDE_CODE_ENTRYPOINT` and its values (`claude-desktop`): preflight P1 relies on it, and it
  holds in use; the env-vars page does not list it.
- The exact text "File has not been read yet". Documented: a Write to an existing file not read
  first fails on older models; newer models may overwrite under conditions (v2.1.228+)
  (<https://code.claude.com/docs/en/tools-reference>). Seen 177 times in the user's week, mostly
  from subagents.
- PowerShell assignments and allow rules; `SendMessage` as a rule; plugin names in `Agent(…)`;
  the auto-mode fate of `uv run --locked --project * chantier *` and `uvx --from * chantier *` (as above).
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
first compaction recorded here.

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
automatic reload's line, which makes the model follow `session-start.md`, "5. Reload", and open
its next answer with one line saying chantier's rules were reloaded. It does not rely on the
summary or on the model noticing. It never vetoes a compaction, and it leaves a subagent's own
compaction alone (a Driver's, a worker's). The `status` skill does not count as a role.

The contract is the engine's own (`claude-code/index.d.ts`: the hook's `next(e)` resolves
`{ messages }`, to which the mod adds its message), checked 2026-11-10 against the engine's types
as they stood on 2026-11-06. **Unproved** until seen in a session; trial: a Chief of Staff session,
`/compact`, then the next answer opens with the reload line and the cards are read (tool calls
visible). The mod is Claude Code's only (`CONTRIBUTING.md`): the automatic reload exists only
where the plugin's mod loads. The manual reload ("chantier reload", or `/chantier:chantier
reload`) works everywhere, and is what a session without the mod has.

## The write guard

The plugin's mod also hooks `agent.spawn` and `tool.call`. It reads one line of a spawn's
prompt, `writes: <absolute folder>; <absolute folder>` (a worker's prompt holds it, with the
worktree first and the CR folder second; a CR Driver's holds its CR folder, then the archive path
when `take` prints one: `concepts.md`, "Starting an agent"). It knows no role
and no card wording. A spawn whose prompt holds the line starts in the first folder (the mod
rewrites the spawn's `cwd`, except on a resume), and the mod records its agent id with the
folders. That agent's Write, Edit or NotebookEdit outside every folder is refused, with the one
message `refused: <path> is outside the folders this agent may write in (<folder>; <folder>);
write there`; a relative path is read against the folder it runs in. The arguments of a
`tool.call` sit flat beside `tool` (`file_path` for Write and Edit, `notebook_path` for
NotebookEdit), and the mod reads nothing else.

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
driver, the QA driver, the Spec-writer, the Griller, the Demo explorer, any agent with no
`writes:` line, and the shell writes the mod cannot see (an interpreter's inline code such as
`python -c` or `node -e`, a script's own writes): the card's rule covers those, and after a
report's `git status` of the main checkout, the steering session names what changed there
(`chief-of-staff.md`). The host's scratchpad is outside the worktree: a
worker writes in its work folder instead. Copilot has no such guard, and the line is inert there.

The refusals are proved by `hooks/register.test.tsx`, run with `just mod`. The passes are proved
by the next real eval's normal use, and the audit checks each worker's prompt holds the line:
**Unproved** until that eval reports. No refusal is planted.

## Classes of session

| Class | How it is known | Can start a session | Fit for a Foreman |
| --- | --- | --- | --- |
| Desktop, typed at the keyboard | no Remote Control notice | yes | yes, it starts it alone |
| Desktop, driven by Remote Control | the host's Remote Control notice | no: refused, the message must be typed in the desktop app | it reuses the last Foreman, or the user acts |
| Session on the main checkout | `git rev-parse --git-dir` equals `--git-common-dir` | n/a | yes |
| Session in a worktree | they differ | n/a | no: Write refuses the main checkout, `change_directory` is refused, `request_directory` does not help |
| Remote or app session | often starts in a linked worktree, `.claude/worktrees/<name>`: the row above | n/a | no, as the worktree row says; proved 2026-11-10, Battlestation, session `epic-lamport-b88c2f`: preflight P6 and P7 failed and the hook refused writes in the main checkout's planning folder |
| Cloud | the host's environment | n/a | no: no main checkout |
| Session in a planning surface | its folder is the surface's root | n/a | yes, if the host lets it write in the project's clone and worktrees, which are outside its folder (`checkout.yml`); **unproved** |

With no argument the Chief of Staff's batches are direct in the Remote Control row and on any
entry where the Foreman-mode P1 fails (terminal, VS Code), and Foreman in the "Desktop, typed" row
(`chief-of-staff.md`, "Starting a batch").

Proved: the worktree row, batch-06, 2026-11 (the user picked the `chantier` entry under "Remote
Control": it names the main checkout, shows no worktree option, the session landed in a
worktree, and Write refused `.agents/changes/`, so Drivers were blocked). The refusal on a
Remote Control session to start a session: proved in use. The cloud row: unproved; trial: start a
Foreman there and run `git rev-parse --show-toplevel`; the same trial tells a cloud session, for
`Remote` in the title. A Remote Control session is told by its notice (the Remote Control row),
for the offer to fork.

`mcp__ccd_directory__change_directory` to the repository's root was refused for a session in an
isolated worktree, even clean with no commit (proved 2026-11-10, same session). So moving to the
main checkout is the user's step: a new session on the main checkout, without worktree ("For you"
below).

**A Chief of Staff and Grillers in remote: the user's own finding (2026-11-10), not a proved
trial.** A remote session cannot be started outside a worktree, which blocks chantier's planning
on the default branch; nested sessions are a problem in remote too. So the Chief of Staff is
started locally (desktop, no worktree), then put in remote (Remote Control). In remote the setup
is: reuse the Chief of Staff's session (its next batch is direct by itself), plus, optionally, Griller sessions in
worktrees that are never merged (their files go to the Chief of Staff, which places them).

Documented, not proved here: the desktop docs say Worktree is off by default and is set per
environment (<https://code.claude.com/docs/en/desktop>); `claude remote-control --spawn
same-dir` keeps the folder and `--spawn worktree` isolates
(<https://code.claude.com/docs/en/remote-control>). Not documented: creating a session from a
phone on a Desktop host, and its options.

**The trial that settles a new Foreman from a remote client** (unproved until it is run, on the
user's word): from the remote client, pick the "Remote Control" entry and, in a second try, the
"Local" group's entry or a saved environment with Worktree off; in each, run `git rev-parse
--git-dir --git-common-dir`. Record here the path that lands on the main checkout. If none does,
a new Foreman needs the desktop, and the reuse is offered.

## Surfaces and options

The surfaces where the user can be: the phone (or another device) on Remote Control; the desktop
app, typed at the keyboard; a terminal (the CLI).

How the host signals the surface: the desktop app adds a Remote Control notice to the conversation
when the user works through Remote Control (proved 2026-11-10, Battlestation: said at each turn's
end that day). A terminal gives no signal, and no signal is said when the user is at the desktop
app's keyboard: the absence of the notice does not prove the user is at the machine. The class row
"no Remote Control notice" ("Desktop, typed") above is qualified by this. Where there is no
notice, the host says nothing: offer every option that fits, each with its condition ("Offering
options", `chief-of-staff.md`). The notice also sets the mode of a batch planned with no argument:
direct (`chief-of-staff.md`, "Starting a batch"). Whether the notice appears on a turn typed at the
desktop in a session connected to Remote Control (the setting "Connect new sessions to Remote
Control") is **unproved**; trial: in such a session, type one turn at the desktop and one from the
phone, and record which carries the notice. Until then the rule holds as written and a forced
`foreman` is the user's way. The rest of this section is **unproved** except where a mark says
otherwise.

| Option | Desktop, typed | Remote Control | Terminal | Why and mark |
| --- | --- | --- | --- | --- |
| Switch to Foreman mode | yes | only by reusing a Foreman ("Reusing the last Foreman"), else no | no | preflight P1 fails in a terminal; proved by the classes table for the first two |
| Run a command in a terminal | yes | no | yes | Remote Control has no shell; unproved |
| Open `localhost` or a file path | yes | no: send the file or a forge link | yes | unproved |
| `/permissions`, `/config` | no: the app's own settings | no | yes | terminal dialogs; unproved |
| Restart the app, `/reload-plugins`, open in an editor | yes (terminal: restart the CLI) | no | restart the CLI | the machine; unproved |
| `/chantier-board` | yes | the pane does not show in a Remote Control view (`docs/boards.md`) | yes | documented in `docs/boards.md` |
| The remote board (`chantier board`) | yes | yes, from any device on the local network, through the link | yes | unproved; trial: open the board's link from the phone on the local network during a batch |
| Review renders, review and merge a PR | yes | yes | yes | the forge, from any device |
| A host feature (scheduled wake, start a session, a monitor) | where the host has it | `start_session` is refused (classes table) | where the host has it | proved for `start_session`, unproved for the rest |
| Work in the main checkout | not during an eval, not from a worktree session | same | same | the classes table and the project's rules |
| Resume a stopped subagent | `SendMessage` to its agent id resumes it with its context | same | same | proved, batch-15 (a refused spec-writer resumed by a message); chantier uses it only for the `taken back:` note of `foreman.md`: a refused agent answers it with its refusal |
| End a subagent's turn with nothing running in the background | the host asks for its hand-back at once (`[handback-send-enforce] Your report has not been delivered. Call SubagentHandback…`), before a resumed worker's reply arrives; a background shell's end wakes it (the CI wait of `driver.md`) | same | same | proved, batch-16 (the CR-216 Driver, agent `ac87782157e90d829`; the CR-215 Driver's Inspector reply came after its hand-back) |

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

Cost: none beyond a fresh context; a worktree session blocks writes, so the folder must be the
main checkout. **Unproved**: the entry that lands on the main checkout is not known (trial
above). Until it is run, do not state any entry as fact: say the new Foreman needs the desktop
and offer the reuse. Once the trial recorded a path, the block is:

- **Where:** the remote client, on the device the trial named.
- **Do:** the labels the trial recorded, in order, ending on the main checkout.
- **Paste:** the Foreman's prompt of "Starting a batch", complete.
- **You should see:** the Foreman's `ready <batch>` in my session within a few minutes; else tell
  me what the session shows, and run `git rev-parse --git-dir --git-common-dir` in it.

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

Built on the user's own finding (2026-11-10), not a proved trial: a remote session cannot start
outside a worktree, so the Chief of Staff starts locally. Chantier explains the steps and never
does them. The path is **unproved** until followed once by hand.

1. Start the Chief of Staff locally, in the desktop app, with no worktree and the tools allowed in
   auto mode (your own steps), then run `/chantier:chief-of-staff` (or `/chantier:chantier`).
2. Put that session in remote (Remote Control). In remote, reuse this session; with no argument its next batch is direct by itself.
3. Optionally, start Griller sessions in worktrees that are never merged: they send their files
   to the Chief of Staff, which places them.
4. Each session renames itself.

What is not possible on the host (a fork that cannot be told apart, nested sessions in remote) is
written here as found, with no workaround.

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
with the project's remote name in place of `origin`, complete, no placeholder. Each was run by
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
