# Chief of Staff: the start of a batch

## The trials before the go

At step 1 of "Starting a batch", after the preflight with the batch's options: **one harmless
trial per used capability**, run by you, each command alone (rule 9), in this session's permission
mode, with the user there. A command the CLI ran would be a child process the host's permission
check never sees, so the trials are your own tool calls. The forms (the host reference's column
"Trial before the go", "Capabilities and their commands"):

- every batch: the `$CHANTIER preflight` you just ran; `git -C <main checkout> push
  --force-with-lease -u <remote> chantier/preflight-trial --dry-run` (the trailing `--dry-run`
  keeps the command under the rule's `*`); on GitHub `gh pr view --json number`, on GitLab `glab
  mr view`;
- a stack with the extension: `gh stack view`; with `forge-stack`: the stacks API probe of P9;
- a release on its own: `git push <remote> v0.0.0-preflight-trial --dry-run`; `gh release create`
  and the merge have no harmless form: "no trial: P10's rule check only";
- fixes on a grant: no harmless form: "no trial: P10's rule check only".

A trial proves that the host let the command run. The command's own error (no such branch, no PR
for this branch) is a pass: the trial tests the permission, not the command. A denial, a prompt or
a classifier refusal is a refusal. When a trial passes where P10 named a missing rule, say the
limits of the host reference's "Auto mode" (a pass proves nothing for a Driver). A refusal is said
at once, with the command and the host's exact text (rule 7), in the same strong warning as P10's,
with the rules P10 named for that capability in the question of "The project"; it never blocks the
go. Each trial writes nothing: a `--dry-run` push of a branch or tag that does not exist fails on
the refspec before reaching the remote.

Recorded: after `open`, a section "Permission trials" in the batch's `brief.md`, one line per
trial, `<capability>: <command> -> ran | refused: <exact text> | no trial: P10's rule check only`,
with the P10 line of each capability. Before a batch (a first turn), the result is told, not
recorded.

## Starting a batch

Only in the turn where the user gave the go:

1. **Preflight, all or nothing.** In chantier's own checkout, when the session's project is
   chantier (the dev mode), first the sync as your skill's
   `$CHANTIER` paragraph says, in detail `sync-checkout.md` (check, name the
   holders, sync only with none; your own board and watcher are stopped only on the user's yes,
   after 3 minutes); a pending sync never blocks the
   go, and the plan says `sync pending: held by ...`. A sync that fails otherwise is one line to
   the user with uv's text, and you go on. Only you sync, never a Foreman, a Driver or a worker. Then
   `$CHANTIER preflight` with the batch's options (`--mode`,
   `--autonomous-releases`, `--grant-fixes`, as `open` will get them) checks P1 (Claude Desktop or
   a Copilot
   agent session), P4 (the plugin's agents at this version), P5 (`uv` and `git`, versions), P6 (the
   session folder is a main checkout: the repository's, or with a surface the surface's or the project's clone), P7 (not a linked worktree), P8 (project instructions), and P10 (Claude
   Code: whether the commands the agents run are allowed), which warns and never fails: if the
   question of "The project" was not asked yet in this session, ask it, and act on the answer
   before the plan; if it was asked and the user said no, repeat in one line what is still
   missing, with no question; then go on, P10 never blocks the go (it names the capabilities it
   did not check); and P12 (`chantier.yaml`, absent or valid); P14 lists the other batches on this
   surface and their Drivers, informational, never a warning or a failure. You warn the
   user of each skill or tool the playbook names and your session lacks. You check P2 (the
   session tools of your host's reference load), P3 (the go is in the user's own message of this turn), P9 (`gh auth status`
   or `glab auth status` is logged in to the remote's host) and that a person is at the
   keyboard. P9 also covers the forge's rights ([Forge permissions](chief-of-staff-any.md#forge-permissions-p9)): they
   only warn. **Then the trials** ([below](#the-trials-before-the-go)). On a failure start
   nothing, offer no other way, and say which condition failed and what the user can do. The mode is settled before the preflight (step 2). Forced `direct`, or no
   argument under the host's Remote Control notice: run `$CHANTIER preflight --direct`: P1 then
   passes on any Claude Code entry point or a Copilot agent session, and you leave P2 out, since
   no session is started. Otherwise the Foreman-mode preflight runs; with no forced mode, a
   failure of P1 or P2 alone makes the mode direct, and `preflight --direct` then runs and is the
   batch's preflight; with `foreman` forced, that failure is the refusal of step 2. Any other
   failure stops as above.
2. **Show the plan:** the CRs (the `3-ready` ones first) and what each one waits for, with the reason of any queue that is
   no real dependency (for a wait on the same lines: the two CRs, number and slug once `open`
   numbered them, else the slug, the file and the lines both edit, for instance "README.md, the
   Routes table", and in plain words "a rebase with a conflict that would happen anyway"); how many CRs start at once, on how many slots (the `batch slots` of the `limits:` line of `$CHANTIER playbook`: 4 unless a `chantier.yaml` or the board's Configuration page sets it, or you say
   otherwise; `open` takes it when you pass no `--slots`, and refuses a configured 0), and, on a surface, the other batches of P14 (project, batch, steering, Drivers), so
   the user picks the slots knowing the machine's load (no cap is proposed or applied); the mode, asked as a question (below), budget, the floor ([The floor](chief-of-staff-any.md#the-floor)) with its two terms and the critical path, and the delivery time it gives ("not before <time>") or "unknown" with the reason, the team (what `$CHANTIER playbook` printed: each role's agent and model); and who steers
   the batch. **The mode question:** a batch question in the format of "Asking the user: a series" (it carries
   no `<short name>-Q<n>` reference). It offers parallel, series (with the order) and stack, and
   marks your recommendation `(recommended)`, weighing three things: whether the CRs are linked (a
   CR's `depends.json`, or one CR building on another's change); the overlap of the files their
   `03-change-spec.md` names (CRs that edit the same files, or are linked, point to a stack;
   independent CRs with disjoint files point to parallel); and the cost of the project's
   local-gate rule by shape (a parallel or series batch runs it once per covered PR, a stack once
   on its top: the floor's "gates" term shows it). It names the shared files behind the
   recommendation, as the plan names a wait on the same lines. A word the user gave earlier (for
   instance "run the P1s as a stack") answers it, and none is asked. Pass `open --mode` with the
   answer; `order mode --note …` still switches the shape on the user's word during the batch.
   A go given before any CR is ready makes an **empty batch**: its plan asks the shape too, and
   shows the slots, budget, the team and who steers, and says for the floor and the delivery time
   "none yet: no CR"; no cut is proposed. When the user asks for a stack (or the plan proposes one) on GitHub, recommend
   installing the `gh stack` extension (github/gh-stack) and say why: the stack driver then makes
   one native stack the user may merge in one action from its top PR, or one PR at a time from
   the bottom: the user may also merge each PR ready to merge as it comes, before the stack is made, while that CR is the only open PR of the stack, and
   nothing about the merge path is fixed at the go nor recorded in `brief.md`. Say too that the stack
   is made as soon as two PRs are handed back ready, each further CR joins on top as a draft when it has its PR,
   the user may merge the ones ready to merge below at any time, and a new stack of what remains is made
   silently after a merge. On a no, say that the stack
   will be made by `$CHANTIER forge-stack create` over the REST API, and record the choice in
   `brief.md` (step 3) so the Foreman passes it to the stack driver. On GitLab, say that the stack is
   made by `$CHANTIER forge-stack create` (the chain of MRs, each on the one below; no extension to
   install, nothing to record in `brief.md`), at two MRs handed back ready, growing the same way, and that the
   user will merge it one MR at a time from the bottom, a middle MR folding into the one below;
   unproved on GitLab (no real run yet).
   For a stack batch (here or at the go of a plan that proposes one), offer
   the choice "one long gate on the top PR only": the lower PRs are ready to merge once CI is green,
   the Verifier says VERIFIED and they are handed back; on a yes, record it with `$CHANTIER order
   waive stack --note "<the user's words>"`. The user may say it during the run: record it the same
   way, and `--note -` withdraws it. A waiver of one CR, or of every CR of a batch, is recorded
   only one CR at a time with `order waive <cr> --note "<the user's words>" --follow-up <folder>`,
   after filing the CR that runs the long gate on main (`$CHANTIER file`): never a note in a brief.
   Re-read the seat first ([session-start](session-start.md)). The steering mode is
   **direct mode** (you steer the batch yourself, no Foreman session) or **Foreman mode** (a
   separate Foreman session), by these rules:
   - **The argument.** Only the invocation's first word counts, and only when it is exactly
     `foreman` or `direct`. Anything else (`init`, a request) is the user's request and forces
     nothing; `direct Run the campaign …` is `direct` plus a request.
   - **Forced holds for the session.** `foreman` or `direct` holds for every batch of the session
     until the user's word changes it. The user's word ("you are in direct mode", "use a
     Foreman") works with or without an argument, and also holds for the session.
   - **No argument: the mode this surface can run,** read at the plan of each batch, never frozen
     at the invocation (a session started at the desk and later driven from the phone plans its
     next batch as direct). **Direct** when the conversation carries the host's Remote Control
     notice ([claude-code](hosts/claude-code.md), "Surfaces and options"), even if a Foreman could
     be reused; **direct** on a host that cannot start a Foreman (a terminal, VS Code, a Copilot
     session whose session tools do not load): the test is the Foreman-mode preflight's P1 and P2
     (step 1); **Foreman** otherwise. No notice means local: a missing notice fails safe to
     Foreman.
   - **The plan says it, no question.** One line states the mode and why ("direct: this session is
     under Remote Control", "Foreman: at the desktop", "direct: forced by the argument") and, when
     direct, what changes: no Foreman session; you steer the Drivers yourself; no grill while the
     batch runs (backlog work, the spec-writer and the spec critic stay open); new ideas go to the inbox. There is
     no separate yes for the mode: the go is the yes. The user may change the mode before the go
     by saying so.
   - **A forced `foreman` where no Foreman can start** (a terminal, VS Code) is refused at the
     plan, with the reason and what the user can do (say "direct", or start from the desktop app).
     Under Remote Control a forced `foreman` starts a new Foreman in this session's own folder, as
     your host's reference says, or reuses the last one, as at the desk
     ([claude-code](hosts/claude-code.md), "Reusing the last Foreman"); this session must be fit for
     a Foreman (a main checkout). A forced mode is
     never swapped silently.
   - **A batch keeps its steering until the user's word switches it** (see "Switching to Foreman
     mode" and "Switching to direct mode"). Going to the phone or coming back changes no running
     or paused batch.

   **The cut.** When the user has given a time (a night, "by 9 o'clock") and the floor exceeds
   it, the plan proposes a cut: the largest set of CRs whose floor fits the time given, taking
   the short chains first; a CR enters only with every CR it waits for, and a chain may be cut
   after any of its CRs. The rest is named "for later" (it stays where it is: `3-ready` or the
   backlog; nothing is moved before the go). The plan shows both: the whole batch with its
   floor, and the cut with its own floor. The user chooses; the go names the choice, and `open`
   takes only the CRs chosen. When the user gave no time, no cut is proposed: the floor and its
   delivery time are said, nothing else. With the delivery time unknown, no cut can be counted:
   say so in the plan.

   You ask the user for the batch's shape at every opening, in step 2 "Show the plan" with the other
   plan items, and never take parallel by default (the CLI's `open` defaults to parallel, but you
   always pass `--mode`). In a parallel batch a CR starts
   as soon as a slot is free, and every open PR is rebased after each merge. Touching the same file is no reason to wait, and
   two CRs editing the same file do not depend on each other. Write `depends.json` in a CR's folder
   (`{"after": ["<slug>", …]}`, a slug being a folder's name without its number) only when it needs
   the result of another, merged or handed back ready first, and say in the plan what it needs; `open` and
   `order add` read it and exit 2 on an unknown slug, a malformed file or a cycle. A CR without the
   file depends on nothing. Read the specifications of the CRs selected for a parallel batch for the
   same lines: a shared table, a template block, a list each one appends to. For such a pair, propose
   in the plan that the later one waits for the other, and say why: both edit those lines, so each
   merge of one would make the other rebase with a conflict anyway; waiting, it starts on the first
   one's work. Say the cost too: the waiting CR starts only once the other is handed back ready, so it takes
   longer on the clock and a slot may stay free. A shared file alone is no reason. Small work whose
   rebase would cost more than waiting stays a reason too. The plan gives the reason for each CR
   queued this way, the user's go approves each wait, and the user may refuse it per CR: the CR then
   runs side by side as usual. There is no threshold: you judge, and say why.

   The limits are the same in both modes; there is no CR threshold of its own. Then
   the go. While a batch is not closed, whatever its state
   (running or paused), there is no new plan: new work joins it with `order add`.
3. **Open:**

   ```bash
   $CHANTIER open [<prepared-folder>…] [--default-branch <branch>] [--slots N] \
     [--budget USD] [--mode parallel|series|stack] [--release N] [--direct]
   ```

   The batch has no name: `open` numbers it and prints its id, `batch-<n>` (`<batch>` below). It
   makes the mode you name, always passed with `--mode` as the user answered (`parallel` is only
   the CLI's default for `open`, never the Chief of Staff's): `parallel`, independent CRs, each on
   the default branch;
   `series`, one CR after the other, in the order given, each on the previous one's branch; `stack`,
   independent CRs that the stack driver then stacks. It exits 2 while a batch is not closed. With
   no folder it opens an ordinary batch **paused, with no CR**, which waits for its CRs in
   `1-pending` (`--release` is refused then: the release CR joins later with `order add
   --release`); CRs join it with `$CHANTIER order add --note
   <folder> --batch <batch>` as their specs become ready, each one planned as a CR joining a
   paused batch is today, and the first `take` sets it running. It moves
   each folder to `4-batch/1-pending/`, names each CR's branch and worktree, and writes
   `brief.md`: complete it from the grill (the team, autonomous decisions allowed, questions to
   bring back). Right after `open`, before the first `take` (direct mode) or before starting the
   Foreman, record each wait the go approved: `$CHANTIER order after <cr> --note "<cr>"`, then
   `$CHANTIER order note <cr> --note "chain: <reason>"`, as in "A chain" (`chief-of-staff:steering`). `order after`
   replaces the CR's whole `after`: when the CR already waits for a real dependency, list it
   too, comma separated. `order after` carries no `--epoch`.
4. **Foreman mode: start the Foreman. Direct mode: steer it yourself**
   ([Steering a batch yourself](chief-of-staff-direct.md#steering-a-batch-yourself)); `open --direct` refuses when your
   own session id is unknown. Starting the Foreman: `<n>` its number as Foreman of the batch, the value of its `--epoch` (`1`, else `$CHANTIER foreman get` plus one; a new
   batch starts at 0, so claims 1, even in a reused session):

   ```text
   chantier Foreman n°<n> of batch <batch>, for the Chief of Staff <your session id>.
   Your session title: <title>. Set it on yourself first.
   Read <skill>/references/startup-core.md, <skill>/references/role-core.md and the named
   startup sections of <skill>/references/concepts.md and <skill>/references/hosts/<host>.md
   now; defer every other section until its step names it.
   CLI: <$CHANTIER, exactly as your skill gives it> <command> --batch <batch>
   Repository: <this repository's absolute path>
   Team: <the lines of `$CHANTIER playbook`, as printed (its `timing:` lines and any TTL warning too), and the review steps; or "the plugin's agents">
   Needs: <only if a role needs skills or tools: as printed>
   (the Foreman reads `$CHANTIER playbook --batch <batch>` itself to start a Driver)
   ```

   `<skill>` is the common `chantier` skill's absolute folder; `<host>` is `claude-code` or
   `copilot`. `<title>` is `[<code>] ⚙️ Project · Foreman (Batch <nn>)` ([titles](titles.md),
   the Foreman row), `<nn>` the batch's number on two digits, e.g. `[Battle] ⚙️ Chantier · Foreman (Batch 17)`; a later Foreman of the same
   batch has the same title. Start the session as your host's reference says, in a session fit
   for a Foreman (its table of classes); the Foreman claims its epoch itself, after its worktree
   check. Where the
   host refuses to start a session, or the session you are in is not fit, the way is a step of
   the user's: give the "For you" block of the reference, after saying what the choice costs, and
   say "I have not tested this path" for a block it marks unproved. On
   `[foreman→chief-of-staff] ready <batch>`, arm the heartbeat if your host's reference says you
   do. After an empty `open` you may start the Foreman at once: it claims its epoch, sends `ready
   <batch>` and waits for the first order, ready and not done; its wait counts in the batch's
   spend, and it arms no heartbeat while the batch has no CR (see the host's "Heartbeat").

   **Reusing the last Foreman.** When the previous batch's Foreman session still exists, even
   stopped, you may reuse it instead of starting a session, with the new batch and its epoch 1.
   It claims the batch's epoch, which starts at 0 for a new batch, so 1; it does not continue the
   old Foreman's. Its title names the old batch: the prompt's title makes it rename itself. The
   prompt is the full one above, so it reads the cards and the rule files `$CHANTIER rules`
   lists again for this batch. A new session stays the default where the host lets you start
   one: a reused Foreman carries its old context, and the batch pays for it. The host's
   reference says how the prompt reaches an idle session and a closed one, what is proved, and
   what the user types first.

   **An ask from a Foreman in a worktree.** Tell the user the impact (Write is refused in
   the planning folder, so no Driver can leave its work and evidence there) and give the "For
   you" block to start again on the main checkout. Suggest no way around the refusal; the user
   may allow one, for that batch only: pass their words to the Foreman as they wrote them, and
   never turn them into a rule.

5. **Start the watcher.** When `open` ends with `watch: not running: …`, start it now in the
   background, by the host's means, on the session's yes (the first time in the session, ask as
   [session-start-chief-of-staff](session-start-chief-of-staff.md), "The watcher", says): run the printed command as is: no flag added. A batch
   opened paused (`open` with no CR) prints it too, whatever the batch's status.
