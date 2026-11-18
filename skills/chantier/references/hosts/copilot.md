# Copilot (SDK host)

## Startup core

The host provides the role's named startup prompt and its declared tools. Read only this
section at boot; defer session, worktree and capability procedures until the action names them.

What is proper to this host: the tools, the heartbeat, the sessions. The cards say what a role
judges and point here. Read it with your card when you run on Copilot.

The lines below moved from the cards as they were, unchanged in substance. Copilot's marks:
nothing here was re-tried when they moved, so each line is **unproved** as to date and place
unless it says otherwise; no new Copilot finding, with two exceptions, each unproved like the rest: the question tool's row, a
user's statement dated 2026-11-14 (CR-250 answer 10), and the line that starts the Spec critic (and any
row a later change adds the same way), a new line. Never tell the user an unproved behaviour as a
fact.

## Tools

| Generic | Copilot |
| --- | --- |
| Start the Foreman's session | `create_session` with `model: "claude-opus-5.5"`, `workspace` = the repository, `worktree: false`, `title: "<title>"` |
| Set the Foreman's own title, first | when the host offers a way; else the title stays |
| Own session id | `$COPILOT_AGENT_SESSION_ID` (also the transcript's id) |
| Start a Driver or a worker | `task`, `mode: background`, `agent_type: <agent>`; the plugin's agent is `chantier-<role>`; no model, as the CLI prints the plugin's or your agent; when the CLI prints `agent=(generic)`, the row Start a generic agent instead; no effort |
| Start the Spec-writer (Chief of Staff) | `task`, `mode: background`, `agent_type: chantier-spec-writer`; no model, as the CLI prints the plugin's or your agent; when the CLI prints `agent=(generic)`, the row Start a generic agent instead; no effort |
| Start the Spec critic (Chief of Staff, Griller) | `task`, `mode: background`, `agent_type: chantier-spec-critic`; no model, as the CLI prints the plugin's or your agent; when the CLI prints `agent=(generic)`, the row Start a generic agent instead; no effort; Fable is not recorded on Copilot |
| Start the Retro critic (Foreman, Chief of Staff) | `task`, `agent_type: chantier-retro-critic`; no model, as the CLI prints the plugin's or your agent; when the CLI prints `agent=(generic)`, the row Start a generic agent instead; no effort; Fable is not recorded on Copilot |
| Models | each plugin agent's file names its model (`[display name, id]`): Luna, Sol, Terra, Sonnet 5.5 or Opus 5.5; the file's model runs when no model is passed. Every plugin agent's file sets `model-policy: required` except `chantier-coder`'s (removed for the eval's probe, `evals/copilot/RUNBOOK.md`, "Models"). The identifier is the display name in lower case, spaces as `-`, dots kept, as the CLI reference's "Supported models" lists them ([CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)). chantier's list of Copilot models is a copy of GitHub's tables (`github/docs`, `data/tables/copilot/`) and of the CLI reference's "Supported models", refreshed by `just copilot-models`; a model's plans are shown, none refused. Each role's default model is `config/chantier.defaults.yml`'s, unless the configuration (`hosts.<host>.roles`) sets one. An identifier the CLI reference does not list is derived by the rule, unproved until `listModels()`. An escalated role (`escalation` in the configuration; `coder`, `debugger`, `conflict-resolver`) starts as a generic agent on that model, printed `(generic)`; a role with the user's own agent does not escalate on Copilot (a user-written `escalation` on it is refused at validation; a shipped one does not apply). |
| Models at an agent's start (capability, start value) | named agent with a model: no, until the probe of `evals/copilot/RUNBOOK.md`, "Models", shows a named agent ran a requested model (`NAMED_AGENT_MODEL_AT_START`). Documented, unproved: a model given at the start wins over the file's unless the file sets `model-policy: required` ([CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#command-line-options)). Start value: the identifier, used by a generic start. A model changed in the configuration starts a generic agent; the user's own agent with a model is refused. Observed in the Copilot App (CR-296 rounds 5 and 6, 2026-11-16; record: the planning surface's `296-improve-skill-boot/work/handoff.md`, "Model evidence"): a plugin agent started through `task` with another model runs on its file's model, the host saying "Required model enforcement replaced requested model ..."; a generic agent took the model passed (`modelSelectionSource: explicit_override`) |
| Start a generic agent (a role configured with another model) | `task`, `mode: background` where the role's start row has it, the generic agent (`agent_type: general-purpose`, unproved as to the exact value: CR-296 round 6 ran a generic agent this way), `model:` the printed start value, the prompt with the printed contract lines; its tools are the caller's, not restricted. Proved: a generic `task` start with `model: gpt-6.1-sol` ran Sol (CR-296 round 6, the host's `subagent.started` record) |
| The model a role ran on | the steering session's `events.jsonl`, `subagent.started` and `subagent.completed`: `model`, `firstDispatchedModel`, `modelSelectionSource`, observed in CR-296 round 6 (record as above). `subagent.failed` carries `model` too, documented ([SDK custom agents](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/custom-agents)), not observed. After a start with a model, the parent reads in its session's `events.jsonl` the `model` of that start's `subagent.started` event; when it differs from the printed identifier, the parent stops that agent's work, reports both identifiers and the host's text (rule 7), and starts nothing else for it. Unproved as a routine; read after the start, not a guarantee before it. Check: `evals/copilot/RUNBOOK.md`, "Models" |
| Skills and tools of a session (what the Chief of Staff compares a role's needs with) | not known (unproved); trial: a `chantier.yaml` naming one skill that is installed and one that is not; the Chief of Staff names only the second |
| Message a Driver | `write_agent` to the agent id |
| Message the Chief of Staff | `send_message` to its session link |
| A Driver's hand-back to its steering session (the Foreman; in direct mode the Chief of Staff) | the Driver's final answer; in direct mode it returns to the Chief of Staff that started the Driver: unproved |
| Stop a Driver | `write_agent` `[foreman→driver <cr>] stop` |
| A Driver's start folder | the host's; no mod moves it (unproved; trial: a Copilot CR Driver runs its first shell and records the folder) |
| Stop a background task of one's own | the host's stop of a background shell, within the agent's `execute` tool set (unproved; trial: a Copilot CR Driver stops its CI watch before its hand-back and the host's events show no output from it afterwards) |
| Agent ids of the project | a file in `.github/agents/` or `~/.copilot/agents/` |
| Preflight P2 | `create_session` and `send_message` load |
| Ask the user a series of questions (grill, specification) | the host's question tool, at most 5 questions per call, at most 4 options per question (the general rule), the reference opening each question's text. The tool's exact name and whether it has its own free answer are not recorded here. Mark: the user's statement (2026-11-14, CR-250 answer 10), unproved; trial: one call with 5 questions on Copilot, all 5 shown, the tool's name and its free answer recorded |
| Run the board | the host's background shell with the command `$CHANTIER board --seat <id>`, its first lines read from the output, stopped with the host's stop of a background shell (unproved; trial: a Chief of Staff starts it, `GET /api/board` with the key answers from the machine, the output shows the start line). If the host has no background command, the Chief of Staff gives the one line of `session-start.md` and goes on: no workaround |
| Prompt cache TTL (the `cache_ttl` default, `5m`) | not known | unproved. Trial: a Copilot session's record that shows how long its prompt cache keeps a prefix (a cached read after a pause of known length, and a cold one after a longer pause); record the date and the models |
| `/every` in whole minutes | the CLI refuses a Copilot duration that is not whole minutes | proved: `/every 4m` (the heartbeat today); unproved: another value. Trial: `/every` armed with a configured value other than 4 minutes, its wakes arriving at that interval; then a form in seconds, to learn whether `/every` takes it, before the rule moves |
| Run the watcher | the host's background shell with the command `$CHANTIER watch --after <n>`; its end must start a turn of the idle Chief of Staff session, its output is read from the background task (unproved; trial: a batch's first merge with a watcher running, the transcript showing the end, the `forge saw merged` line, the forge check and the `order merged` that followed with no user message between). If the host has no background command or its end does not start a turn, the Chief of Staff starts no watcher and says so in one line: no workaround |
| The board when the session ends | whether the host ends a background command when the session ends (unproved; trial: start the board, end the session, ask `GET /api/board` with the key). Until proved, the board stops when the seat moves (the CLI) |
| The skills | the same four, same names: `skills/chantier` (the router), `skills/chief-of-staff`, `skills/griller`, `skills/status`, declared in `.github/plugin/plugin.json`; how Copilot passes the argument `foreman` or `direct`, or the argument `reload` (router, `chief-of-staff`, `griller`), is not known (unproved) |
| Set a session's own title (the Chief of Staff, a Griller) | when the host offers a way; else nothing (unproved) |
| List the sessions; is the seat's session alive | not known: the seat's session always "looks stopped" to a new session, and the "looks stopped" line of `session-start.md` is asked (unproved) |
| Message another session of the user (hand-over, a Griller's line) | `send_message` to its link (unproved) |
| A Griller in a worktree | its files sent as for a Griller on Claude Code (unproved) |
| A session in a planning surface writing in the project's clone and worktrees (outside its folder) | the host must allow those folders (unproved); the remote finding is Claude Code's: not tried on Copilot |

Known host issues: a `model` array once refused by the CLI ([copilot-cli#2133](https://github.com/github/copilot-cli/issues/2133)); an SDK-provided agent's model dropped at `session.create` ([copilot-sdk#1609](https://github.com/github/copilot-sdk/issues/1609)); an unknown identifier falling back silently ([copilot-sdk#2856](https://github.com/github/copilot-sdk/issues/2856)); sub-agents on another model than the session's with no sign, fixed in CLI v1.0.62 ([copilot-cli#3824](https://github.com/github/copilot-cli/issues/3824)).

## Heartbeat

In direct mode there is no Foreman chat: the Chief of Staff runs the same `/every` in its own session (unproved), its wake read from the
batch's `timing: Copilot other models:` line.
Otherwise the Chief of Staff arms it: on the Foreman's `ready <batch>`, it sends the Foreman chat `/every
<steering wake> chantier status --refresh --batch <batch> --epoch <n>`, the wake read from the
batch's `timing: Copilot <family> models:` line for the family of the model it started the Foreman
with, else from `timing: Copilot other models:`, written in `/every`'s form (`4m` by default). The Foreman cannot end `/every`. At
every pause, the automatic one (when the last CR ends) included, the Chief of Staff tells the user
to delete the `/every` in the Foreman chat (in direct mode, in its own session). The Foreman
also ends its heartbeat on the first wake that sees no Driver run for 30 minutes or more, whatever
the wake's interval (nothing can move): the Chief
of Staff then tells the user to delete the `/every`, and arms it again with the next order it
sends the Foreman. Whoever ends the heartbeat (the Foreman, or in direct mode the Chief of Staff)
first records it with `chantier status --stop-heartbeat --batch <batch> --epoch <n>` (`pause`
already does); while an `/every` still fires, its next wake clears the mark, which is true.

## Configuration

- Prerequisites, the same as Claude Code's for a batch: `git` and `uv` (P5), `gh` or `glab`
  logged in (P9). P9's forge side (rights and branch rules) runs on Copilot as on Claude Code: it
  is the card's check. P10 does not run on Copilot, and no host rule is recorded. A refusal of a
  force push on Copilot is reported like any refusal (rule 7), and the general rule of
  [concepts](../concepts.md) holds: a CR's branches must be force-pushable at all times.
- No permission configuration is recorded for Copilot: **unproved**; nothing is recommended
  until a Copilot trial records one.
- The capability table is the cards' commands, the same on both hosts: read it from
  [claude-code](claude-code.md), "Capabilities and their commands"; its rules are Claude Code's.
  The trials run as on Claude Code (the Chief of Staff's own calls, one per used capability), and
  a refusal is told and recorded with its exact text (`chief-of-staff.md`, "The trials before the
  go"): **unproved** until a Copilot batch runs them. P9's forge probes are the card's and run
  unchanged.
- The command hygiene of `concepts.md` rule 9 applies on both hosts.

## Compacting

Name no compacting command or setting to the user.

## Reload after a compaction

Not done yet. This change covers Claude Code only (the user's choice, 2026-11-10). Copilot has no
mod (its manifest names no hooks) and its own way to react to a compaction is not known. Until
then the manual reload ("chantier reload", `session-start.md`, "Reload") is the only one, and the
Chief of Staff names no compacting command (the "Compacting" section holds).

## Surfaces and options

Not done yet. How Copilot signals where the user is is not known. Until then the Chief of Staff
offers every option, each with its condition (the "host says nothing" case of "Offering options",
`chief-of-staff.md`). With no Remote Control signal known on Copilot, the no-argument mode follows
P1 and P2 only (`chief-of-staff.md`, "Starting a batch"), unproved.

## Sessions

The Foreman is started by `create_session`. A refused start is reported with its exact text.
Nothing else is recorded here about Copilot's sessions.

A Driver stopped from outside on Copilot is unproved; the card's rule (`foreman.md`, "A Driver stopped from outside") holds when the host says the Driver was stopped.
