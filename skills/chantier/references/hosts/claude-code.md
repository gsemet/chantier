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
| Set the Foreman's own title, first | `set_session_title` | unproved: not tried here; the trial is a Foreman that sets its title and `get_session("self")` shows it |
| Start a Driver or a worker | `Agent`, `run_in_background: true` for a Driver, `subagent_type: <agent>`; the plugin's agent is `chantier:<role>`; no model, no effort | proved, same |
| Message a Driver | `SendMessage` to the agent id | proved, same |
| Message the Chief of Staff | `SendMessage` to its session id | proved, same |
| A Driver messages the Foreman | `SendMessage` to `main` | proved, same |
| Stop a Driver | `TaskStop` | proved, same |
| Agent ids of the project | the `name:` of a file in `.claude/agents/` or `~/.claude/agents/` | proved, same |
| Models | the Foreman and the stack and release drivers run Opus 5.5; the CR and QA drivers and the workers Sonnet 5.5 | proved, same, except the CR driver: unproved; the trial is the model a CR driver's transcript shows in the next batch |
| Preflight P2 | `mcp__ccd_session__start_session` loads | proved, same |

"Proved, same" means seen in use in every batch since v0.3, with no dated trial kept: re-prove a
line by a trial before relying on it for something new.

**Limit on messages.** Claude Desktop limits messages between sessions (10 since someone last
typed): a refused send is reported, never sent another way. Proved in use, same; the figure comes from
the earlier card, with no dated trial.

## Heartbeat

The Foreman runs the `/loop` skill in dynamic mode with `chantier status --refresh --batch
<batch> --epoch <n>`, every `30m`, each wake scheduled with `ScheduleWakeup`. It ends the
heartbeat, never its session, with `ScheduleWakeup` `stop: true`: right after `land`, and on a
wake where no Driver of any kind (CR, stack, QA, release) has run since the last wake and no
order is undone. An order's line or a `ping` starts a turn; if it leaves a Driver running, the
Foreman arms the heartbeat again. No wake ever arriving is a stop. Proved: same.

## Compacting

Auto-compact is on by default. What the user sets is its window: the `/autocompact` command and
the `autoCompactWindow` setting. Documented: <https://code.claude.com/docs/en/settings>.
`/compact` continues the same conversation, connected devices follow it, and `$CHANTIER cost`
keeps the transcript; `/clear` may replace it. No role runs it: the person types it.

## Classes of session

| Class | How it is known | Can start a session | Fit for a Foreman |
| --- | --- | --- | --- |
| Desktop, typed at the keyboard | no Remote Control notice | yes | yes, it starts it alone |
| Desktop, driven by Remote Control | the host's Remote Control notice | no: refused, the message must be typed in the desktop app | it reuses the last Foreman, or the user acts |
| Session on the main checkout | `git rev-parse --git-dir` equals `--git-common-dir` | n/a | yes |
| Session in a worktree | they differ | n/a | no: Write refuses the main checkout, `change_directory` is refused, `request_directory` does not help |
| Cloud | the host's environment | n/a | no: no main checkout |

Proved: the worktree row, batch-06, 2026-11 (the user picked the `chantier` entry under "Remote
Control": it names the main checkout, shows no worktree option, the session landed in a
worktree, and Write refused `.agents/changes/`, so Drivers were blocked). The refusal on a
Remote Control session to start a session: proved in use. The cloud row: unproved; trial: start a
Foreman there and run `git rev-parse --show-toplevel`.

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

### `/compact`

Cost: none beyond the summary; the same conversation continues.

- **Where:** the session to compact, typed at its input.
- **Do:** type `/compact` and send.
- **Paste:** when I ask to keep something, the line I give you in its own code block.
- **You should see:** a summary and a smaller context size within a minute.
