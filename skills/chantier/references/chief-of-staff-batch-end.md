# Chief of Staff: the end of a batch

## While it runs: the pause and what follows

- **The pause:** on `[foreman→chief-of-staff] final <STATUS.md path>`, that file is the exit
  report with the cost to date: the CLI removed the merged CRs' worktrees and branches and paused the
  batch when the last CR ended (a `kept:` or `not removed:` line names a leftover, which `close`
  names too), and the Foreman stays idle. The Foreman wrote the retro of the batch in `4-batch/retro.md`
  after the pause and before its `final` (a section for this pause: one line per problem met, `- [<tag>] <problem>:
  <long-term fix>`, the tag `project` or `chantier`); read it. Give the Completion report, with
  its Retro offered by route, each point numbered:
  - A `project` point: on the user's word for it, `$CHANTIER file "<the point>"` files it in
    `1-inbox`. A point that matches an item already in the inbox or the backlog is named with that
    item, not offered twice.
  - A `chantier` point: never filed with `$CHANTIER file` (except in chantier's own repository,
    see "When the project is chantier itself" below). On the user's word for one point or a group
    of points, it goes the chantier route below.
  - The user may move a point to the other route ("13 is a project point"): follow that word and
    say the route it now takes.
  - A release's `work/retro.md` is offered once, with the batch's, each point by its own tag; its
    points went through the Foreman's critic with the batch's, so only the kept ones (marked
    `(release)` in the section) are offered.
  - The retro you read holds only the points the `retro-critic` kept; its section's header ends
    with `(critic: kept <k>, dropped <d>)`. After the numbered points, one line: `<d> points
    dropped by the critic; the list is on request.` Asked for it, read `4-batch/retro-dropped.md`
    and show it, before any `close`. A section of `nothing worth changing` is said as such:
    "Retro: nothing worth changing (<d> points dropped by the critic; the list is on request)."
    A section `retro not checked: <cause>` is said as such, with nothing offered; the drafted
    points are in `retro-dropped.md` on request. The routes below apply to the kept points only.

  Offer the Retro before any `close`, which writes `4-batch/retro.md` into the batch's record,
  `5-archives/batches/batch-NN.md`. Then, in the same turn, offer the close at once, unprompted,
  after the Completion report and the Retro: run `$CHANTIER close --batch <batch>` (the check, no
  `--yes`), show the bilan, the final cost, what goes, and its line of worktrees and branches to
  remove, which names the merged CRs' leftovers beside the trashed CRs' whatever `final` said
  (with why each was kept, from `final` or the cleanup lines), and its `kept, moved out with their
  work` line (the CRs dropped to the backlog or the next batch (`3-ready`): show it, remove nothing on it), and ask
  "close the batch?";
  `close --yes` only on the user's yes, as the Closing bullet says. The close is offered after
  `final`, never before: the Foreman's retro critic must have handed back.
  In Foreman mode your own `order merged <cr>` or `order drop <cr>` of the last CR prints the
  pause: still send its line to the Foreman (it cancels its armed wake, runs the fast-forward, the
  retro with its critic, and `final`), and wait for `final` before the close offer.
  New work for the paused batch is `order add`, once per CR: until the user's `close`, the paused
  batch is still the running batch, and a CR placed in `1-pending` (by `order add`) starts it again
  at the next `take`. The batch stays paused until the Foreman's first `take`; send the Foreman the usual order once all are added, and it pauses again
  at the end. Where the heartbeat is yours (the host's reference says),
  tell the user to delete it in the Foreman chat at the pause, and again when the Foreman ends it
  on the first wake that sees no Driver run for 30 minutes or more (nothing can move); arm it
  again with the next order you send the Foreman, at the wake `hosts/copilot.md` reads from the
  batch's `timing:` lines.
- **Any other list of changes you propose on your own.** Before proposing, on your own
  initiative, changes to chantier or to the project (a retro after a release or a closed batch, a
  report's suggestions, an answer to a question such as "are the workers useful?", even a single
  change), start one `retro-critic` ([`retro-critic.md`](retro-critic.md)) with the points and the
  evidence each cites, its first line copied from `$CHANTIER playbook`, and offer only the kept
  points, then the one line `<d> points dropped by the critic; the list is on request.` Here the
  dropped list stays in the chat (no file), shown on request in the same session. When it keeps
  nothing: "Nothing worth changing." and the dropped line. When it fails twice (restarted once),
  offer nothing, say "retro not checked: <cause>", and keep the drafted points for the user to ask
  for. A change the user asked for does not go through the critic, nor does a CR's own content (a
  specification, a gap, a Driver's hand-back), which have their own checks.
- **The chantier route** (a `chantier` point, on the user's word; nothing is drafted unless the
  user named the point for this route; all of it at the pause, before any `close`), in this order:
  1. The repository is the `repository` field of the plugin manifest
     (`<plugin root>/.claude-plugin/plugin.json` on Claude Code,
     `<plugin root>/.github/plugin/plugin.json` on Copilot), so a fork's manifest points to the
     fork.
  2. Already reported? When `gh` reaches it (`gh issue list --repo <owner/name> --state open
     --search "<key words>"`), a point that matches an open issue is named with that issue's link
     and not drafted again. When `gh` is absent or does not reach it, skip this check and say so
     in one line.
  3. Draft one file per issue with the host's Write tool (UTF-8, no BOM, concepts rule 9):
     `4-batch/chantier-issue-<n>.md`, `<n>` the number of the first point it carries. Its first
     line is the title (`Bug: ...` when chantier did something wrong, `Feature: ...` when it
     lacks a means); then the body: what happened (the problem), the long-term fix proposed,
     chantier's version (`$CHANTIER --version`) and the host and its version when known, one line
     saying it came from a batch retro, and, for a point caused by the host, that it may belong
     upstream. One point per issue, or a few points with one cause grouped, as the user chose. In
     English; no label is set.
  4. Check before showing. chantier's repository is public: the draft holds no project name, no
     private path (a home folder, a drive letter, the planning folder's path), no code or text of
     the target project, no CR number, slug or batch id, no person's name or data. A point that
     cannot be said without them is said in general terms; if it still cannot, say so and offer it
     as an inbox item instead.
  5. Show and ask, per issue: the title and body as text in the chat, the repository's link, and
     the tool that will post it. Ask for a yes for that issue. The user may edit, regroup,
     decline, or post it themselves (give the file's absolute path for that).
  6. Post on the yes only, and only you: `gh issue create --repo <owner/name> --title "<title
     line>" --body-file <path>`, the body (the draft without its title line) in its own file,
     `4-batch/chantier-issue-<n>-body.md`, so no text is typed in the command. Give the user the
     issue's link. When `gh` is absent, not logged in, or refused, nothing is posted: give the
     user the file's path and the repository's "new issue" link, and say what is missing.
  7. No record: the drafts stay in `4-batch/` until `close` deletes them with the batch's other
     files; the retro is not rewritten; the link of a posted issue is said in the chat only.
- **When the project is chantier itself:** its forge remote (`git remote get-url origin`) is the
  manifest's `repository` (compared without a trailing `.git` or `/`, ignoring case). Then both
  routes meet, and the Completion report's "For you" says, in one line: "This project is
  chantier: its `chantier` points are filed here as inbox items, like the project's; say 'as an
  issue' for a point to go to GitHub instead." The default is the inbox.
- **Closing:** `--yes` only on the user's word (their yes to the close offered at the pause, or
  "close the batch"). `$CHANTIER close --batch <batch>` without `--yes` is the check and prices
  the final cost; it is also run unprompted at the pause, to offer the close, and only once the
  retro critic has handed back (below). It refuses, naming each cause, while a CR is not merged or cancelled,
  an order is open, a stack agent is recorded, or an agent the batch holds (an id `agents set`
  recorded and `-` did not clear, or the current Foreman) has a transcript that shows it still runs
  (a tool call with no result, or a step under way: the CLI reads the end of each transcript,
  never the file's age), or a transcript cannot be read (missing, cut or undecodable; a held id
  with no transcript found too; on Copilot, until `copilot-close-end-event` lands, a held agent whose
  lease is live, a unit with no lease (`not measured`) and the Foreman's heartbeat under 10 minutes
  refuse too (a lease lives at most 10 minutes, up to 90 minutes after a hold; `agents set <cr> - --epoch <n>` after the agent's reported end ends it), and a Driver's leftover background work after its hand-back is no longer seen). The session's other subagents (grill, spec, critics, Drivers
  already replaced, a Driver's own subagents) and the replaced Foremans never block: the ones
  still running or unreadable are listed apart in the check's output, need no question to the
  user and no `--stopped`, and their calls are counted in the final cost only up to now. Offer or
  run `close` (the check or `--yes`) only after the steering session's retro critic has handed
  back: in Foreman mode after the Foreman's `final` (which comes after its critic's reply,
  `foreman-pause.md`); in direct mode after your own retro critic of the pause has handed back. A retro
  critic still running is not judged by `close`, so this rule is what keeps its calls in the
  final cost. It refuses too, with or without `--yes` and naming the cause, when nothing at
  all can be priced (no priced call in the batch; no Foreman transcript recorded, which leaves the
  batch no way through `close`). A model with no price does not refuse it: the final cost is a
  floor (`at least`) with its calls not priced, and the CLI says which id to add under `prices:`
  in `chantier.yaml`. On a batch set running again by a `take` or `order qa`, it names what
  runs (or says `pause --epoch <n>` comes first). Report a refusal to the user with its cause, do not retry in
  a loop, and do not `close --yes`. When the refusal names a held agent that still runs, wait for that
  agent's hand-back (its notification), then run `close` again, never on a timer. When you know
  the agent will not hand back, or the user says so, ask the user: ways to know are an app restart
  that cut it, the user's stop, or its hand-back that already reached you while its transcript
  reads as running. In the question quote each agent's name, cause and file, as the refusal gives
  them; ask the agent itself only as a last resort (a finished subagent cannot be messaged). On
  the user's yes, in that turn, run `close --batch <batch> --stopped <name> ...` (the check; the
  name is the held agent's file stem, `agent-<id>`, or the current Foreman's session id), show the
  bilan with its "declared stopped" lines and ask for the close as above; on that second yes run
  `close --batch <batch> --stopped <name> ... --yes`. Never pass `--stopped` without the user's
  yes for each named agent, and never to get past a transcript that cannot be read: the CLI
  refuses a name that is not a running held agent, and keeps the declaration in the
  batch's record. A held agent the refusal says cannot be read with no transcript found: tell the
  user, and clear it with `agents set <cr> - --epoch <n>` only once it is known not to run (a
  Driver of another session of the user's: on the user's word); never `--stopped`. A Driver run
  from another session of the user's is not in what it reads, so ask the user when you know of one. When it passes it prints the final cost and what goes (the batch's own files; each `3-done` CR moves to
  `5-archives`), where the retro and the record go (`5-archives/batches/batch-NN.md` and
  `.json`), and touches nothing. To know which batch the project is at, run `status`: its second
  line names the last closed batch. Show the user the bilan, the final Cost section and that
  list, and ask. Only on their yes,
  in that turn: `close --batch <batch> --yes`, then every entry of its line of worktrees and
  branches to remove, the trashed CRs' and the merged CRs' leftovers alike (not the `kept, moved
  out with their work` line), yourself, from the
  main checkout (`git -C <clone>` with a planning surface; `git worktree remove --force <path>`,
  `git branch -D <branch>`, as listed; for a folder git no longer knows, `git worktree prune` once
  it is deleted, then `git branch -D <branch>`).
- **Recovery:** a stale heartbeat says something only while a CR is `working`; with none, the
  Foreman has stopped waking, as it should. "Heartbeat stopped" is a loop ended on purpose. After a break, a restart or a stale heartbeat, prove the Foreman is alive
  (`$CHANTIER foreman get`; the host knows the session and it answers a `ping`) before
  reporting progress. An app restart stops every session: tell the user, and on "resume" run
  preflight again and start a new Foreman with the next epoch (or, on the user's word, switch to
  direct mode, "Switching to direct mode"), adding "Resume: relaunch each
  CR still working by the restart path (`agents set <cr> - --epoch <n>`, `handoff`, `take <cr>
  --note "resume: <cause>" --epoch <n>`, a new Driver, `agents set <cr> <id> --epoch <n>`); a relaunched
  CR's stale long gate is stopped by its new Driver with `$CHANTIER gate <cr> --stop`." `cancel`
  follows only a drop the user ordered (`order drop <cr> --note …`): never use it to stop the
  processes of a CR that goes on. A Driver whose id was cleared with `agents set <cr> -` (an app restart,
  a Driver stopped from outside, a context restart) and a Foreman replaced by a new one are never
  a blocker at `close`: their transcripts are listed apart and need no `--stopped`. In a direct
  batch, a Driver stopped from outside is restarted by you with no question to the user
  ([foreman](foreman.md), "A Driver stopped from outside"), and when you stop a Driver yourself
  and do not restart it at once, you clear its recorded id in the same turn.
- **Putting back:** on the user's word, a CR in `6-trash/` returns to `1-inbox/` by moving its
  folder, without the date prefix.
