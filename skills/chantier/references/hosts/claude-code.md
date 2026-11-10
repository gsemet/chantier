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
| Start the Foreman's session | `mcp__ccd_session__start_session` with `initiation: "user_asked"`, `title: "<title>"`, `context: "fresh"`, `use_worktree: false`, `model: "claude-opus-5-5"`, `effort: "medium"`, the user's permission mode; leave it linked | proved: every batch started from Claude Desktop (v0.3 on) |
| Own session id and title | `get_session("self")`; the transcript's id is `$CLAUDE_CODE_SESSION_ID` | proved, same |
| Set a session's own title (the Chief of Staff, a Griller, the Foreman) | `set_session_title` | proved for a Chief of Staff's own session, 2026-11-08 (Battlestation, a session renamed itself); the Foreman's case stays unproved: the trial is a Foreman that sets its title and `get_session("self")` shows it |
| The skills | `/chantier:chantier` (the router), `/chantier:chief-of-staff [direct]`, `/chantier:griller`, `/chantier:status`: a plugin's `skills/<name>/` is `/<plugin>:<name>` | documented: <https://code.claude.com/docs/en/plugins-reference> (skills) |
| Load another skill (the router) | the host's Skill tool | unproved until the router runs; trial: `/chantier:chantier` in a session with no Chief of Staff, answer a role, see the skill load |
| List the sessions and their state; is the seat's session alive | the session tools found in the `mcp__ccd_session__` set: the exact tool and its states are not recorded | unproved; trial: two sessions on one repository, one stopped, list both and record the states |
| Message another session of the user (hand-over, a Griller's line) | `SendMessage` to its session id | proved for the Chief of Staff's session (the row above); between two sessions of the user, unproved; trial: a Griller's `ready` line to the Chief of Staff's session |
| A session's link (for the seat) | what `get_session` gives | unproved until recorded; trial: `get_session("self")` and note the link field |
| Start a Driver or a worker | `Agent`, `run_in_background: true` for a Driver, `subagent_type: <agent>`; the plugin's agent is `chantier:<role>`; no model, no effort | proved, same |
| Start the Spec-writer (Chief of Staff) | `Agent`, `run_in_background: true`, `subagent_type: chantier:spec-writer`; no model, no effort | unproved until a CR is specified this way |
| Message a Driver | `SendMessage` to the agent id | proved, same |
| Message the Chief of Staff | `SendMessage` to its session id | proved, same |
| A Driver messages its steering session (the Foreman; in direct mode the Chief of Staff, which is `main` there) | `SendMessage` to `main` | proved, same; in direct mode the same mechanism, unproved until a direct batch runs |
| Stop a Driver | `TaskStop` | proved, same |
| Agent ids of the project | the `name:` of a file in `.claude/agents/` or `~/.claude/agents/` | proved, same |
| Models | the Foreman, the stack and release drivers and the Spec-writer run Opus 5.5; the CR and QA drivers and the workers Sonnet 5.5 | proved, same, except the CR driver: unproved; the trial is the model a CR driver's transcript shows in the next batch |
| Preflight P2 | `mcp__ccd_session__start_session` loads | proved, same |

"Proved, same" means seen in use in every batch since v0.3, with no dated trial kept: re-prove a
line by a trial before relying on it for something new.

**Limit on messages.** Claude Desktop limits messages between sessions (10 since someone last
typed): a refused send is reported, never sent another way. Proved in use, same; the figure comes from
the earlier card, with no dated trial. The limit applies to the lines between a Griller and the
Chief of Staff, and to a hand-over's.

## Heartbeat

The Foreman (in direct mode the Chief of Staff, in its own session) runs the `/loop` skill in dynamic mode with `chantier status --refresh --batch
<batch> --epoch <n>`, every `30m`, each wake scheduled with `ScheduleWakeup`. It ends the
heartbeat, never its session, with `ScheduleWakeup` `stop: true`: right after `pause`, and on a
wake where no Driver of any kind (CR, stack, QA, release) has run since the last wake and no
order is undone. An order's line or a `ping` starts a turn; if it leaves a Driver running, the
Foreman arms the heartbeat again. No wake ever arriving is a stop. Proved: same.

## Configuration

What the user configures so chantier runs on Claude Code with few interruptions. chantier never
writes the user's settings: preflight's P10 compares, the user adds. Marks as above; a doc-check
of 2026-11-09 against <https://code.claude.com/docs> gave the **documented** lines, each with its
page (`https://code.claude.com/docs/en/<page>`).

### Who reads it, when

- The Chief of Staff, at its first turn of a session and at each batch's preflight: it runs the
  check (P5, P9, P10) and gives the user the block of "Allow rules to add" for what is missing.
- The Foreman and the Drivers read this file with their card (their prompts already name it):
  "Auto mode" tells them what a refusal means and that it is reported, never worked around.
- The workers do not read this file; what they need (one command per call, read before you
  overwrite, no leading assignment, `git -C`) is in `concepts.md`, rule 9.

### Prerequisites

| Tool | Needed for | Checked by | Missing |
| --- | --- | --- | --- |
| `git` | every Driver, the CLI's reads | P5 (CLI) | preflight fails |
| `uv` | `$CHANTIER` (`uv run --script`) | P5 (CLI) | preflight fails |
| `gh` or `glab`, logged in to the remote's host | the Drivers' PRs and CI | P9 (the Chief of Staff: `gh auth status` / `glab auth status`) | preflight fails |
| `python` | none directly: `uv run --script` provides the interpreter | not checked | say so; on Windows a `python` that resolves to the Microsoft Store alias fails (seen 15 times in the user's week): the fix is the user's (App execution aliases); **unproved** as to which roles call `python` |
| `bash` | Claude Code's Bash tool on POSIX | not checked | **unproved** whether chantier needs it on Windows, where the PowerShell tool is used |
| `claude` | not a batch's need | not checked | seen missing from PATH 5 times in the user's week; no card calls it |

The last three rows are not checked: a default the Driver of this change chose to keep, and may
change on its judgment.

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

The recommended rules, in the order P10 checks them. Each has a `Bash(…)` and a `PowerShell(…)`
form (P10 compares only the Bash forms on POSIX):

| Rule | chantier's use | Risk accepted | Mark |
| --- | --- | --- | --- |
| `Bash(git push --force-with-lease*)` and `PowerShell(…)` | a Driver's push after a rebase (`driver.md`, Push) | any `--force-with-lease` push, to any branch, and any flag after it | documented (rule form) |
| `Bash(git -C * push --force-with-lease*)` and `PowerShell(…)` | the same from outside the worktree, the form refused 4 times as "Git Destructive" | as above, in any repository the `-C` path names | documented (rule form) |
| `Bash(git push -u origin chantier/*)` and `PowerShell(…)` | a Driver's plain push (`driver.md`: `git push -u <remote> <branch>`, branches `chantier/<batch>/…`) | `*` matches any further text, so a flag added after the branch passes too; a remote not named `origin` is not covered | documented (rule form) |
| `Bash(git -C * push -u origin chantier/*)` and `PowerShell(…)` | the same with `git -C <worktree>` | as above | documented (rule form) |
| `Bash(uv run --script *chantier.py *)` and `PowerShell(…)` | every `$CHANTIER` command (`merge`, `ship`, `spawn`… were refused 5 times) | any script whose path ends in `chantier.py` | **unproved**: whether auto mode drops it as a "package-manager run command" is not documented (checked 2026-11-09); trial: enter auto mode with the rule set, run `$CHANTIER status`, see whether the classifier is asked |
| `Bash(gh pr create*)` and `PowerShell(…)` | a Driver opens its PR (refused once as "Git Destructive") | any PR on any repository `gh` can reach | documented (rule form) |
| `Bash(gh pr checks*)` and `PowerShell(…)` | a Driver reads its CI | read-only | documented (rule form) |
| `Bash(glab mr create*)` and `PowerShell(…)` | a Driver opens its MR on GitLab (`driver.md`: `glab mr create --draft`) | any MR on any project `glab` can reach | documented (rule form) |
| `Bash(glab ci status*)` and `PowerShell(…)` | a Driver reads its CI on GitLab (`glab ci status --live`) | read-only | documented (rule form) |
| `SendMessage` | the Foreman and the Drivers message each other (refused twice) | any message between this session's agents and sessions | **unproved**: `SendMessage` as a rule is not documented (absent from tools-reference, checked 2026-11-09); trial: set it, enter auto mode, have the Foreman message a Driver |

The same rules as one block, ready to paste into the `permissions.allow` array of
`~/.claude/settings.json` (a test compares it with the CLI's list):

```json
{
  "permissions": {
    "allow": [
      "Bash(git push --force-with-lease*)",
      "PowerShell(git push --force-with-lease*)",
      "Bash(git -C * push --force-with-lease*)",
      "PowerShell(git -C * push --force-with-lease*)",
      "Bash(git push -u origin chantier/*)",
      "PowerShell(git push -u origin chantier/*)",
      "Bash(git -C * push -u origin chantier/*)",
      "PowerShell(git -C * push -u origin chantier/*)",
      "Bash(uv run --script *chantier.py *)",
      "PowerShell(uv run --script *chantier.py *)",
      "Bash(gh pr create*)",
      "PowerShell(gh pr create*)",
      "Bash(gh pr checks*)",
      "PowerShell(gh pr checks*)",
      "Bash(glab mr create*)",
      "PowerShell(glab mr create*)",
      "Bash(glab ci status*)",
      "PowerShell(glab ci status*)",
      "SendMessage"
    ]
  }
}
```

Two rules described here that P10 does not check:

- `mcp__ccd_pr__set_monitor`: Claude Desktop's PR monitor (auto-fix), refused twice in the
  user's week. No chantier card uses it. Risk: the session arms auto-fix on a PR. Rule form
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

### What stays refused

No allow rule for these; when the host refuses or asks, the agent reports it (concepts rule 7),
and chantier does not do them unasked. Each with why:

- `git commit --amend --reset-author`: rewrites authorship.
- `git branch -D` with `git push origin --delete`, and `git update-ref -d`: delete refs; the
  Foreman's removal of a merged CR's branch and the Chief of Staff's of a dropped CR's (on the
  user's word) stay asked, not allowed.
- `Remove-Item -Recurse -Force` (or `rm -rf`) on `.claude`, or on temporary folders named by a
  wildcard (`claude-eval-*`, `chsmoke-*`): a pattern can reach what is not chantier's.

### Auto mode

- Allow, ask and deny matches resolve at once in auto mode, without the classifier, except
  protected paths, critical-path `rm`/`rmdir` and per-command domains (**documented**,
  <https://code.claude.com/docs/en/permission-modes>).
- The classifier label "Git Destructive" and `claude auto-mode defaults`, which lists the
  classifier's rules: **documented** (<https://code.claude.com/docs/en/auto-mode-config>). The
  labels "Merge Without Review" and "Create Public Surface", seen in the user's week:
  **unproved**, not documented (checked 2026-11-09).
- A refusal is reported with its exact text (concepts rule 7). A refused force push takes the
  route already written (`driver.md`, `foreman.md`: Driver → Foreman → Chief of Staff).

### What the docs do not say

Each **unproved**, not documented (checked 2026-11-09):

- `CLAUDE_CODE_ENTRYPOINT` and its values (`claude-desktop`): preflight P1 relies on it, and it
  holds in use; the env-vars page does not list it.
- The exact text "File has not been read yet". Documented: a Write to an existing file not read
  first fails on older models; newer models may overwrite under conditions (v2.1.228+)
  (<https://code.claude.com/docs/en/tools-reference>). Seen 177 times in the user's week, mostly
  from subagents.
- PowerShell assignments and allow rules; `SendMessage` as a rule; plugin names in `Agent(…)`;
  the auto-mode fate of `uv run --script *chantier.py *` (as above).
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

**Unproved**, not explained by the docs (checked 2026-11-09): sessions with `autoCompactWindow:
300000` compacting around 165 to 170k tokens (the user's week). Trial: one session, the setting
read back with `/autocompact`, the token count at the first compaction recorded here.

**Recommendation**, not a proved fact: keep `idleCompaction` on (its default), and set
`autoCompactWindow` to 400000 in `~/.claude/settings.json` for the Chief of Staff's and the
Foreman's sessions (the plugin's agents carry 200,000 in their files). Why: long sessions with
pauses past the cache's life. Whether 400000 holds, given the unexplained 165 to 170k compaction
above, is unproved: the same trial settles it.

```json
{ "idleCompaction": true, "autoCompactWindow": 400000 }
```

## Classes of session

| Class | How it is known | Can start a session | Fit for a Foreman |
| --- | --- | --- | --- |
| Desktop, typed at the keyboard | no Remote Control notice | yes | yes, it starts it alone |
| Desktop, driven by Remote Control | the host's Remote Control notice | no: refused, the message must be typed in the desktop app | it reuses the last Foreman, or the user acts |
| Session on the main checkout | `git rev-parse --git-dir` equals `--git-common-dir` | n/a | yes |
| Session in a worktree | they differ | n/a | no: Write refuses the main checkout, `change_directory` is refused, `request_directory` does not help |
| Remote or app session | often starts in a linked worktree, `.claude/worktrees/<name>`: the row above | n/a | no, as the worktree row says; proved 2026-11-10, Battlestation, session `epic-lamport-b88c2f`: preflight P6 and P7 failed and the hook refused writes in the main checkout's `.agents/changes/` |
| Cloud | the host's environment | n/a | no: no main checkout |

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
below). Whether a remote session can start without a worktree: unproved; trial: start one with
Worktree off and run `git rev-parse --git-dir --git-common-dir`.

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

## A Foreman in a worktree asks

The Foreman checks before it claims its epoch (its card). In a worktree it takes no CR and sends
the ask. The Chief of Staff tells the user the impact: Write is refused in `.agents/changes/`, so
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

The guided flow, **unproved** until followed once by hand. Chantier explains the steps and never
does them (the fork, auto mode, no worktree).

1. Start a remote session with no worktree and the tools allowed in auto mode (your own steps).
2. Run `/chantier:chief-of-staff` (or `/chantier:chantier`): it becomes the Chief of Staff.
3. After the boot, fork the session (the label on screen, recorded by the trial): the fork
   becomes a Griller by itself, or asks with a batch active.
4. Each renames itself; you grill in the fork.

What is not possible on the host (a fork that cannot be told apart, a remote session that cannot
start without a worktree) is written here as found, with no workaround.

### `/compact`

Cost: none beyond the summary; the same conversation continues.

- **Where:** the session to compact, typed at its input.
- **Do:** type `/compact` and send.
- **Paste:** when I ask to keep something, the line I give you in its own code block.
- **You should see:** a summary and a smaller context size within a minute.

### Allow rules to add

The block the Chief of Staff gives when P10 warns. Unproved until followed once by hand, like
every block above.

- **Where:** the computer running Claude Desktop, the file `~/.claude/settings.json` (or the
  project's `.claude/settings.json`, which the team shares through git, or
  `.claude/settings.local.json`, the user's own in this project).
- **Do:** open the file; add the lines below to `permissions.allow` (create the key if absent);
  save; then start a new session. Whether a running session picks up a settings change is
  **unproved** (see "What the docs do not say").
- **Paste:** only the missing rules P10 named, as JSON strings, in their table order, copied
  from "Allow rules"; complete, no placeholder.
- **You should see:** at the next preflight, `P10 ok`.
