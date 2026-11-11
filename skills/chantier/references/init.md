# Init: a guided tour for a newcomer

The Chief of Staff reads this card when the user asks for `init` ("init", "I am new here",
"chantier, initialise this project"). The tour writes nothing in the project; only the five
empty stage folders, which `$CHANTIER init` creates, and what the user says yes to at the end.
The first-turn introduction is skipped: the tour covers it.

## 1. Run `$CHANTIER init`

It creates the empty stage folders of the planning folder, `.agents/changes/` or, in a planning
surface (`--project`), the named project's `changes/` (it writes neither `project.md` nor
`checkout.yml`, which are the user's), and the folder's `.gitignore` (`1-inbox`, `2-backlog`, `3-ready`,
`4-batch/1-pending`, `4-batch/2-actives`, `4-batch/3-done`, `5-archives`, `6-trash`), and
says which it created and which existed.

On exit 2 for no git repository, explain what chantier needs: a git repository, a remote on
GitHub or GitLab, `gh` or `glab` logged in, `git` and `uv`. Offer `git init`; run it only on the user's
yes, then run `init` again. Nothing else is created on the user's behalf. On exit 2 in a linked
worktree, say init runs in the main checkout and stop.

## 2. Read the project, lightly

`$CHANTIER rules` (the instruction file and what it links), the README, the build files
(`package.json`, `justfile`, `Makefile`, `pyproject.toml` and the like), the CI workflows, the
tree on two levels. No code reading, no gate run.

## 3. Ask once: the chat or an HTML page?

The chat is the default. For a page, copy [tour.html](../assets/tour.html) to
`<system temp>/chantier-tour-<project folder name>/index.html`, fill its named slots, open it
(on Remote Control, send it as a file). Nothing is written in the project. The slots are the
story, the three diagrams (inline SVG you generate), the two previews, money and decisions,
getting started here, phrases to say, the glossary.

## 4. Give the tour, in the user's language

- **The thread is the story of one CR of this project,** from the request to the archive: filed
  in `1-inbox`, grilled with a question and its recommended answer, specified, prioritized into
  `2-backlog/P<n>`, put in `3-ready` for the next batch, run in a batch by the Foreman, taken by a
  Driver in a slot on its branch and worktree, rounds of Coder then Inspector, long gate, PR, CI,
  Verifier, ready, the user's merge, `3-done`, then `5-archives` at `close`. The example CR is a real, small improvement you pick from what you read;
  its paths, branch name and gate commands are this project's.
- **Steering.** A batch is steered either by the **Foreman**, a separate session, or by you in
  **direct mode**: no Foreman session, you start the Drivers and hold no grill
  until the batch completes (filing, triage and the spec-writer stay open), and a CR added while it runs is queued and taken when a slot frees (once it is
  paused, it takes the next grilled CRs before its first `take`). Direct mode is used where
  the host cannot start a Foreman session or for a small batch; the plan names it and the
  user's go approves it. The story follows the Foreman; one or two sentences after step 4 give
  direct mode, and the first diagram notes it. Present it as how chantier works, never as new.
- **Concepts appear when they serve,** in bold. A role is first an image of the building site
  (chief of staff, foreman, team lead, workers), then its exact term.
- **About ten core terms** in the story: CR, specification, batch, Chief of Staff, Foreman,
  Driver, slot, round, Coder, Inspector, Verifier, ready. The others go to the glossary.
- **Three diagrams, generated for this project:** who talks to whom (the user, the Chief of
  Staff, the Foreman, a Driver per CR, its workers; orders down, questions and hand-backs up);
  the five folders and what moves a CR between them; one CR over time (rounds, gate, PR, CI,
  Verifier, the user's merge). In the chat they are text diagrams.
- **Two previews:** the CR's folder tree with this project's real paths, and a `status` table.
  Money in it is shown as `$…`: the tour gives no cost figure.
- **Money and decisions:** the budget, slots (4 by default) and rounds (3 by default) as
  mechanics, with no figure; what only the user does (prioritize, say go, merge, release, raise
  a limit); "what did it cost?" gives the measured detail.
- No comprehension check, no quiz.

## 5. End the tour, in this order

1. **Getting started here:** what you saw of the project's harness and what you propose to
   improve, each with its impact on the team when missing. A rule (a gate, the merge method, the
   commit convention) is proposed as the exact `AGENTS.md` text, written only on the user's yes,
   section by section. Check the two gates in particular: whether the project's rules declare a
   fast gate (run after every round) and a long gate (run once before the PR, which `handback
   ready` requires), or no long gate, or exemptions. When one is missing, propose the exact lines,
   for example "- Fast gate (after each change): `<cmd>`." and "- Long gate (before a pull
   request): `<cmd>`.", one command per item, never chained with `&&` or `;`; the impact when
   missing: a long gate the Driver cannot run is a `--no-gate` the steering session must
   question. Point to the README's "Your gates". Work that needs code (tests, CI) is proposed as a CR filed in the inbox,
   only on the user's yes. For an in-project planning folder, the `.gitignore` line is explained only: keep `.agents/changes/` out
   of git so the main checkout stays clean and the CRs stay local; the user adds it themself. In a
   surface it does not apply: the planning folder is the surface's, and the tour says where it is.
   The example CR is offered for the inbox. The host's configuration comes from preflight's P5
   and P10 and from P9: the missing tools, and your host's "Allow rules to add" block for the
   missing rules, explained only; the user adds them themself, like the `.gitignore` line. The
   tour writes nothing in the user's settings.
2. **Phrases to say:** "file this: …", "make it a P1", "run the P1s", "status?", "drop CR-<n>",
   "I merged #<n>", "what did it cost?". The tour's end is the first-use moment of the Tips rule: these phrases stand for its tip, so add no 💡 line.
3. **Glossary:** one line per term not in the story: stack, fast gate, long gate, Investigator,
   Debugger, Conflict resolver, Griller, release CR, grant, `STATUS.md`, `close`, direct mode if the
   story's sentences need a reminder, and any other the user will read in reports.

## 6. Length

About 90 lines in the chat, glossary included; under 100.

## 7. Run again

On a project that already has the folders the command changes nothing. Assess the improvements
again and say what changed. Offer the tour; do not impose it.
