# Drivers: when a step goes wrong

## Means: a worker that fails

- A worker refused for its first line, or ended by a host failure, gets
  one new start of the same role with the same brief (a worker refused because its prompt names
  no card gets that one new start with the role's opening lines copied as printed; the rest of
  the brief stays the same), `$CHANTIER note <cr> "restart: <cause>"`
  first, no `round`; a second refusal of the same start, a model included, is `handback blocked
  refused <exact text>`, never retried without the model.
- You never read a verdict, a pass or a choice into a reply out of format, never fix it, and never
  ask the worker by message to fix it. Record `$CHANTIER note <cr> "restart: reply out of format:
  <what is missing>"` and start one new worker of the same role with the same brief, as for a
  refused first line (no `round`); its brief also says what the failed reply lacked. For a Coder,
  this new start is the restart of a failing coder of "CR driver": it counts as that round's one
  restart. A second reply out of format from the restarted worker: a Coder's is the next round
  (`$CHANTIER round`), as "CR driver" says of a second failed coder; any other role's is
  `handback <cr> blocked question: <role> replied out of format twice: <what is missing>`, and the
  stack driver sends `[stack→foreman] anomaly <cr> <role> replied out of format twice: <what is
  missing>`. A worker is never resumed by a message to its
  agent: only a new start continues its task, and a new round is always a new child, never the
  previous round's Coder resumed.
- After a coder that
failed, a dirty worktree goes to a new `coder` in the same round, with no `$CHANTIER round`; its
brief names what the failed attempt left and what to do with it: keep it, fix it, or discard it
back to the round's starting head (then the coder's own git). That is a restart of a failing
child, not a new round. The coder is restarted at most once per round: a second failed coder in
the same round is the next round (`$CHANTIER round`), whose brief carries both failures. A
worktree left dirty by a failed rebase goes to a `conflict-resolver`.
- A long reply is read, not restarted. A reply in format that only passes its cap (more than ten
  lines for a Coder or a Verifier; more than 3,000 characters for an Inspector or an extra review
  step) is acted on as any other reply, and you record `$CHANTIER note <cr> "long reply: <role>:
  <n> lines"` (`<n> characters` for the JSON). It is no cause of a restart and counts as no failed
  worker. The brief of the role's next start in this CR (the next round's Coder, the next Verifier)
  says that the last reply passed its cap and that the details go to the work file. An extra key
  alone in an otherwise correct Inspector JSON is read and noted the same way, not restarted.

## Means: escalation

- Escalation ([concepts](concepts.md), "Escalation"): only when one of its triggers arises, read
  the role's `escalation=` on the `team:` line first, then the `escalate:` line of
  `$CHANTIER playbook --batch <batch>`, as printed.
- Escalation applies to the CR driver as to any parent ([concepts](concepts.md), "Escalation"): a
`debugger` that explains no red check, or a `conflict-resolver` that settles no conflict, gets a
second one on the escalation model. A note `escalate: rounds` or `escalate: blocked twice: ...`
means each new round's `coder` starts on the coder's escalation model; you keep your own model.
You never escalate yourself.

## Means: a remote command fails

- CI's `timing:` line is, on Claude Code, the `subagent` one; on Copilot, the line of your model's family,
  else `other models`. An infrastructure failure of a CI job gets at most the CI re-runs of that line (1 by
  default; 0: none), each at the same head, and a failure the CR does not touch that passes on a re-run is
  a flake: a `note` names the test, the run and the symptom, for the Chief of Staff to file. Once the
  re-runs are used up and the job is still red on the infrastructure, end with
  `handback <cr> blocked infra: CI <job> red on the infrastructure after <n> re-runs` (the stack
  driver: `[stack→foreman] anomaly <cr> infra: …`). With no result after 3 hours on one head, stop waiting
  and end with `handback <cr> blocked infra: CI still running after 3 hours` (a longer CI in the
  project's rules gives its own limit).
- A remote command (`git fetch`, `git push`, `gh`, `glab`) that fails with a forge server error
  (an HTTP 5xx) or a network failure (no route, a reset or timed-out connection, a name that does
  not resolve) runs the same command once more, at once and with no `sleep`. Before re-running a
  command that creates or moves something (`git push`, `gh pr create`, `glab mr create`, `gh pr
  edit`), first check whether the first attempt took effect (`git ls-remote <remote> <branch>`,
  `gh pr list --head <branch>`, or the forge's equivalent) and do not run it again if it did.
  Note it: `$CHANTIER note <cr> "infra re-run: <command>: <exact error>"`. If the second attempt
  fails the same way, the CR Driver and the Release driver end with `handback <cr> blocked infra:
  <command>: <exact error>`; the stack driver sends `[stack→foreman] anomaly <cr> infra:
  <command>: <exact error>`. A refusal (an HTTP 4xx, a denied permission, a protected branch, a
  failed lease) is not an infrastructure failure: it keeps its own routes (`blocked refused`, the
  force-push route, a failed lease examined), with no re-run. The CI rule (an infrastructure
  failure gets at most the CI re-runs of your `timing:` line) is about a CI job, and the Release
  driver's "On the infrastructure" is about a step of the procedure; both stay, and the remote
  command's one re-run above is not the `timing:` line's. This is the same rule for a single command.

## Means: CI beside the long gate

- When the project's rules name a pipeline job as the long gate
  ([concepts](concepts.md)), run no `gate`: push and open the PR after the approved round (the
  first push starts the gate, so no wait before it; `ship`'s `off: no long gate passed at <sha>`
  is then expected), read CI as the "CI" bullet says, and once that job is green at the PR's head
  with the `VERIFIED` verdict there, hand back `ready <link> … --no-gate "<the rule>"`, quoting
  the rule; a red run of that job is a red CI job, a round. A rebase needs no gate carry: the job
  runs again at the pushed head. (GitLab and Copilot: unproved.)
- With the `ci: beside the long gate` line (a CR Driver only), after the approved round,
    the commit and the rebase: push, open the PR as a draft or update it (the audit pass on
    `pr-body.md` first), `ship`, then start the long gate (`$CHANTIER gate <cr> <name>…`)
    and the CI watch (`gh pr checks <pr> --watch --fail-fast`; on GitLab `glab ci status
    --live`, unproved; trial: a red job of a GitLab pipeline ends the watch or shows in its
    output before the pipeline's end), each in its own background shell by the host's means
    (Claude Code `Bash` with `run_in_background: true`, Copilot's background shell). Do
    everything that needs neither result, end your turn, and the first shell to end wakes you.
    Unproved; trial: a CR Driver of a batch with the line pushes at the approved round, runs its
    gate while CI runs, and on a red CI job stops its gate and starts a debugger before the gate
    ends. The outcomes:
    - A red job that is the CR's (not an infrastructure failure, not a job also red on the
      default branch, judged as above): at once, without waiting for the gate or the other jobs,
      `$CHANTIER gate <cr> --stop` (recorded `stopped`: no pass, not a round), a `note` naming
      the job and the head, `gh run view <run> --log-failed > <work folder>/ci-<run>.log`, a
      `debugger` on it, the next round.
    - An infrastructure failure, or a job also red on the default branch: its rule above (the
      `timing:` line's re-runs, or a note). The gate is not stopped, its result still counts.
    - The gate fails first: a round, as today. Stop the CI watch's shell you started, by its
      id; CI at that head no longer counts.
    - The gate passes first: go on waiting for CI. CI is green first: go on waiting for the
      gate.
    - Both done, the gate passed and CI green or judged by the rules: the `verifier` at the
      pushed head, as today.
    - The early push of a PR that exists (every batch, no line needed) uses these same
      outcomes after a rebase that needs a long gate: the PR is a draft, pushed at once, and
      leaves draft only once the gate has passed and CI is green at that same head.
    The 3-hour limit, the "no CI" looks, the head check and the CI note's form stay.
- With the `ci: beside the long gate` line, a CR Driver reads the systems CI covers from the
forge's list of checks at the pushed head (job names such as `just check (ubuntu-latest)` name
their system) and compares them with the system the long gate ran on. In Known gaps it writes one
bullet naming the systems only CI covers and which commands of the long gate ran only there, for
example "The long gate ran on Windows only; Linux and macOS are covered by CI alone." A forge
that lists no check gives no such bullet; the "no CI" rule says what to write then.

## Means: stopping a long gate

- Stop only your own CR's running long gate, only with `$CHANTIER gate <cr> --stop`, never
  another CR's. Do it only when the run's result can no longer count (the head is about to
  move: a `rebase:` note, a change that needs a round, or a red CI job that is the CR's, see the
  "CI" bullet) or on the steering session's `stop`;
  never because the gate is slow, since a run that would still be a valid pass is worth more
  finished than restarted. A stopped run is recorded `stopped`: not a failure, so not a round;
  no pass, and it voids an earlier pass at that head, so run the long gate again at the head you
  push. A gate of yours still waiting for the lock (its log says `waiting for the long gate of
  …`) has started no suite, and `--stop` refuses it because the lock names another CR: end it
  by ending the `gate` command you started, by its id. A wait in the queue is never refused for
  its length; a refusal for the hour names the gate that holds the lock (or whose suite runs on)
  at that moment: report it to the steering session as it is, do not read it as a stale lock,
  and never stop another CR's gate. `cancel` is the steering session's
  command for a CR the user dropped, never a Driver's, whatever the reason.
- The queue of long gates: the next merge's first (in a stack or series batch, the first CR of the order not
  merged or cancelled, a fix CR and the release CR excepted), then those the Foreman moved first, then
  arrival order.
- A long gate still running at your hand-back is left to finish: the CLI records its result for the next
  Driver. Stop only what waits on it or reads it besides its shell. When that gate's end wakes you after
  your hand-back, send nothing and end your turn.

## Means: when CI lists no check

- The rules do not replace the look: even when they say the project has no CI, the claim comes
  from the forge's list; the rules only say how to judge it. A list that contradicts them (a check
  where they say none, none where they say some) is said in a `note`.
- The note for no check reads `CI: no check listed at abc1234 (gh pr checks 12, two looks, the second a
  minute after the push)`.
- "No CI" needs two looks: an empty first look, or a watch that ends at once because no check is
    reported yet, is not a conclusion; a forge registers its checks a few seconds after the push.
    Say "No CI" only when a second look, a minute or more after the push, still lists no check at
    the same head. Fill that minute with the work that needs no CI result, which comes first. A
    second look that lists checks leads to the normal long wait.
  - The one bounded wait: when that work ends before a minute has passed since the push, run one
    bounded wait, once (for instance a single `sleep` of the seconds that remain), then take the
    second look. It is the one exception to rule 8 of [concepts](concepts.md) ("No `sleep`, no
    polling loop"): at most once per pushed head, never a loop.

## Means: a git command in the wrong place

- A Driver and its workers write nothing in the repository's git folder (`.git/info/exclude`,
  `.git/config`, `.git/hooks`), by any tool or shell command; git's own commands write there as git
  does. A file to ignore is ignored by the worktree's own files (a `.gitignore` change goes through a
  `coder`, in a round, as any project file) or not at all; a file that should not be committed is
  simply not staged (staging is by name).
- The main checkout moves only by the steering session's post-merge fast-forward ([concepts](concepts.md),
  rule 8; `foreman-merge.md`, "The main checkout after a merge"), never by a Driver's command.
- A git command run in the
  wrong place by mistake: stop, undo only what is safe to undo (`git -C <main checkout> rebase
  --abort`, `merge --abort`), and `note` it; anything else left in the main checkout goes to the
  steering session as it is, by an `anomaly` (stack driver) or a `blocked question:` hand-back,
  never cleaned by force.
