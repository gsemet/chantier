# real

chantier on its own repository: real CRs, real `git`, `gh` and CI, in the main checkout, with no
workspace to stage. It proves the path a user takes. It does not exercise the failures the
scripted campaigns plant, and `evals/kit/audit.py` does not apply: it reads a staged workspace.

| | |
| --- | --- |
| CRs | 1 to 5 real defects or small features, picked by the Chief of Staff, with the user's go |
| Open | `$CHANTIER open <batch> <A> <B> … --default-branch main --slots 3 --budget 20` |
| Team | the plugin's agents |

The plugin is read live from the checkout: the main checkout stays on `main` during the run, and
any other work goes in another worktree.

## Nothing merges

Each specification and the brief say so: the PR is a draft, the first line of its body is
`**Eval run: do not merge.** The maintainer decides what happens to this PR.`, and nobody merges
it, marks it ready or enables auto-merge. The batch stops at `ready` for each CR. Whatever comes
next is the user's word: a merged PR is `order merged`, a closed one `order drop`.

## Starting

One new Foreman session per batch: `cost` counts a session's calls from the batch's creation, but
the session's context still costs each turn. Under Remote Control the user starts that session,
as the [README](../README.md) says. It may open outside the repository: the prompt then adds
`CHANTIER_ROOT=<this checkout>`.

## Check

- Each PR on the forge: draft, open, no auto-merge, its first line, CI green at its head.
- `$CHANTIER log <cr>`: the rounds, the gates, the verifier's proof.
- `$CHANTIER cost --by cr` before `close`: the batch's folder goes with it.
- A sample of the diffs, read by hand, against each specification.

Report in `results/real-<date>.md`, as the [README](../README.md) describes, without the audit
checks.
