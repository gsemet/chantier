# Claude Code: the allow rules

What P10 checks and what the Chief of Staff offers. How a rule matches, the broad rules, and what
stays refused: `help host-allow-rules`, `help host-allow-broad`, `help host-refused`.

### Allow rules

The recommended rules, in the order P10 lists them. Each has a `Bash(...)` and a `PowerShell(...)`
form (P10 checks the Bash forms on POSIX, both on Windows). P10 does not compare these strings: it
holds the commands the cards make the agents write and asks whether some allow rule of the user's
lets each through; a narrower or different rule of theirs counts when it matches the same
commands, for instance `PowerShell(git push --force-with-lease=chantier/* origin *chantier/*)`.
`origin` is the project's remote name.

| Rule | chantier's use | Risk accepted | Mark |
| --- | --- | --- | --- |
| `Bash(git push -u origin chantier/*)` and `PowerShell(…)` | a Driver's plain push (`git push -u <remote> <branch>`, branches `chantier/<batch>/…`) | `*` matches any further text, so a flag added after the branch passes too; a remote not named `origin` is not covered | documented |
| `Bash(git -C * push -u origin chantier/*)` and `PowerShell(…)` | the same with `git -C <worktree>` | as above | documented |
| `Bash(git push --force-with-lease -u origin chantier/*)` and `PowerShell(…)` | a Driver's push after a rebase, and the stack driver's restack, one command per branch | a lease-protected force push of any `chantier/` branch; a Driver pushes only its own CR's branch (floor rule 2); the rule's `*` does not enforce that, the card does | documented |
| `Bash(git -C * push --force-with-lease -u origin chantier/*)` and `PowerShell(…)` | the same from outside the worktree | as above, in any repository the `-C` path names; a Driver pushes only its own CR's branch (floor rule 2); the rule's `*` does not enforce that, the card does | documented; refused with the rule set in place: the rule does not prevent the refusal |
| `Bash(git push --force-with-lease=chantier/* origin *chantier/*)` and `PowerShell(…)` | the steering session's route (the Foreman's, then the Chief of Staff's) for a refused force push: `git push --force-with-lease=<branch>:<expected> <remote> <sha>:refs/heads/<branch>` | as above | documented |
| `Bash(git -C * push --force-with-lease=chantier/* origin *chantier/*)` and `PowerShell(…)` | the steering session's route when its directory is not the main checkout, always with a planning surface (the project's clone that `take` names): `git -C <checkout> push --force-with-lease=<branch>:<expected> <remote> <sha>:refs/heads/<branch>` | a lease-protected force push of any `chantier/` branch, in any repository the `-C` path names; the steering session pushes only a branch the check ties to this batch (`help refused-push-judgement`); the rule's `*` does not enforce that, the card does | documented |
| `Bash(git -C * rebase origin/*)` and `PowerShell(…)` | the Driver's rebase onto the base: `git -C <worktree> rebase <remote>/<branch>`, a CR on the default branch, and the GitLab fold onto the remote branch | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented; unproved (a subagent); refused with no rule set |
| `Bash(git -C * rebase chantier/*)` and `PowerShell(…)` | the same onto the bare `chantier/` branch of the CR under it in a series or a stack | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented; unproved (a subagent); refused with no rule set |
| `Bash(git -C * rebase --onto chantier/* *)` and `PowerShell(…)` | a restack onto a `chantier/` base: `git -C <worktree> rebase --onto <chantier/ branch> <sha or branch>` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented; unproved (a subagent); refused with no rule set |
| `Bash(git -C * rebase --onto origin/* *)` and `PowerShell(…)` | the CR at the bottom after a drop: `git -C <worktree> rebase --onto <remote>/<default branch> <branch>` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented; unproved (a subagent); refused with no rule set |
| `Bash(git -C * rebase --continue)` and `PowerShell(…)` | a rebase stopped at a conflict, continued by the conflict-resolver (`conflict-resolver.md`) | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented; unproved (a subagent); refused with no rule set |
| `Bash(git -C * rebase --abort)` and `PowerShell(…)` | a rebase given up | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it); any repository the `-C` path names, and the middle `*` matches any text before ` rebase `, so a command that holds the word `rebase` as a later argument matches too | documented; unproved (a subagent); refused with no rule set |
| `Bash(git rebase origin/*)` and `PowerShell(…)` | the same without `-C`, from the checkout the session stands in (the surface's checkout) | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented; unproved (a subagent); refused with no rule set |
| `Bash(git rebase chantier/*)` and `PowerShell(…)` | the same onto a `chantier/` branch, without `-C` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented; unproved (a subagent); refused with no rule set |
| `Bash(git rebase --onto chantier/* *)` and `PowerShell(…)` | the same restack, without `-C` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented; unproved (a subagent); refused with no rule set |
| `Bash(git rebase --onto origin/* *)` and `PowerShell(…)` | the same, without `-C` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented; unproved (a subagent); refused with no rule set |
| `Bash(git rebase --continue)` and `PowerShell(…)` | the same, without `-C` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented; unproved (a subagent); refused with no rule set |
| `Bash(git rebase --abort)` and `PowerShell(…)` | the same, without `-C` | a local rebase of the branch checked out (nothing is pushed by it) onto a branch of the remote or a `chantier/` branch; the trailing `*` matches any further text, so a flag added after the base passes too (`--exec` / `-x` runs any command: the cards forbid it, the rule does not enforce it) | documented; unproved (a subagent); refused with no rule set |
| `Bash(uv run --no-sync --project "<checkout>" chantier *)` and `PowerShell(…)`, `<checkout>` filled with the checkout's real path as P10 prints it | every `$CHANTIER` command in chantier's own checkout, when the session's project is chantier, the dev mode | every chantier subcommand of the checkout at that path (`gate` runs only the long gates the code repository's `chantier.yaml` names, and `lease hold` runs nothing) | proved (main session); unproved (auto mode, a Driver) |
| `Bash(uv sync --locked --project "<checkout>")` and `PowerShell(…)`, `<checkout>` filled the same way | the steering session's checked sync of chantier's own checkout, which waits for holders, when the session's project is chantier, at a session's or a batch's start and after a merge that changes `uv.lock` (the dev mode) | a sync of the checkout at that path, from its lockfile | proved (main session); unproved (auto mode, a Driver) |
| `Bash(uv sync --locked --check --project "<checkout>")` and `PowerShell(…)`, `<checkout>` filled the same way | the steering session's read-only check before a sync, the dev mode: exit 0 in sync, 1 with "The environment is outdated" (the skills' `$CHANTIER` paragraph) | none: it writes nothing | documented; unproved (rule matching, auto mode, a Driver) |
| `Bash(uvx --from "<plugin root>" chantier *)` and `PowerShell(…)`, `<plugin root>` filled with the plugin's real path as P10 prints it | every `$CHANTIER` command of an installed plugin, or of another project's session run from chantier's checkout, the plugin mode | every chantier subcommand of the plugin at that path (`gate` runs only the long gates the code repository's `chantier.yaml` names, and `lease hold` runs nothing); for another project run from chantier's checkout, the rule names the checkout's path and lets through every chantier subcommand of the build uv caches from it | proved (main session); unproved (auto mode, a Driver) |
| `Bash(gh pr create*)` and `PowerShell(…)` | a Driver opens its PR | any PR on any repository `gh` can reach | documented |
| `Bash(gh pr edit*)` and `PowerShell(…)` | a Driver's body (`--body-file`) and the stack driver's retarget (`--base`) | any edit of any PR `gh` can reach | documented |
| `Bash(gh pr ready*)` and `PowerShell(…)` | a PR turned ready, or back to draft (`--undo`) | a PR turned ready, or back to draft | documented |
| `Bash(gh pr checks*)` and `PowerShell(…)` | a Driver reads its CI | read-only | documented |
| `Bash(gh pr view*)` and `PowerShell(…)` | a Driver or the steering session reads a PR | read-only | documented |
| `Bash(gh pr close*)` and `PowerShell(…)` | the Chief of Staff's drop of a CR to the trash closes its PR (`order drop`, `cancel`) | closing any PR `gh` can reach | documented |
| `Bash(gh pr reopen*)` and `PowerShell(…)` | a restored CR's PR reopens | reopening any PR `gh` can reach | documented |
| `Bash(gh stack*)` and `PowerShell(…)` | the stack on the forge, only when `gh extension list` names `gh-stack` | any operation of the extension | unproved |
| `Bash(glab mr create*)` and `PowerShell(…)` | a Driver opens its MR on GitLab (`glab mr create --draft`) | any MR on any project `glab` can reach | documented |
| `Bash(glab mr update*)` and `PowerShell(…)` | a Driver's description or the stack's retarget on GitLab | any MR edit on any project `glab` can reach | documented |
| `Bash(glab mr view*)` and `PowerShell(…)` | a Driver reads its MR | read-only | documented |
| `Bash(glab mr close*)` and `PowerShell(…)` | the same close, on GitLab | closing any MR `glab` can reach | documented |
| `Bash(glab mr reopen*)` and `PowerShell(…)` | a restored CR's MR reopens | reopening any MR `glab` can reach | documented |
| `Bash(glab ci status*)` and `PowerShell(…)` | a Driver reads its CI on GitLab (`glab ci status --live`) | read-only | documented |
| `SendMessage` | the Foreman and the Drivers message each other | any message between this session's agents and sessions | unproved |

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

### Capabilities and their commands

The one table of what chantier's agents run, by capability. P10's `SAMPLES` follow its order and a
test compares them. P10 checks only the capabilities the batch will use (`$CHANTIER preflight
--mode stack --autonomous-releases N --grant-fixes`, as `open` takes them) and names those it did
not check. Each rule is written `Bash(<rule>)` and, on Windows, `PowerShell(<rule>)`. A missing rule
is a strong warning, never a failure: the host's classifier judges each command at run time, and in
a remote session nobody may be there to answer its prompt.

| Capability | Used when | Commands its agents run | Rules | Trial before the go | Mark |
| --- | --- | --- | --- | --- | --- |
| Every batch | always | `$CHANTIER ...` (dev, chantier's own checkout, when the session's project is chantier: `uv run --no-sync --project "<checkout>" chantier ...`, after the steering session's checked sync, which waits for holders (the skill's `$CHANTIER` paragraph); plugin: `uvx --from "<plugin root>" chantier ...`; the two placeholders filled with the real path P10 prints); a Driver's push `git push -u <remote> chantier/...` and `git -C <worktree> push -u <remote> chantier/...`; the rebase `git [-C <worktree>] rebase <base>` (and `--onto`, `--continue`, `--abort`; never `--exec`) and the force push after it `git [-C <worktree>] push --force-with-lease -u <remote> chantier/...`; the steering session's route `git [-C <checkout>] push --force-with-lease=<branch>:<sha> <remote> <sha>:refs/heads/<branch>`; on GitHub `gh pr create`, `edit` (with `--base`), `ready` (with `--undo`), `checks`, `view`, `close`, `reopen`; on GitLab `glab mr create`, `update`, `view`, `close`, `reopen`, `glab ci status`; `SendMessage` | `git push -u origin chantier/*`<br>`git -C * push -u origin chantier/*`<br>`git push --force-with-lease -u origin chantier/*`<br>`git -C * push --force-with-lease -u origin chantier/*`<br>`git push --force-with-lease=chantier/* origin *chantier/*`<br>`git -C * push --force-with-lease=chantier/* origin *chantier/*`<br>`git -C * rebase origin/*`<br>`git -C * rebase chantier/*`<br>`git -C * rebase --onto chantier/* *`<br>`git -C * rebase --onto origin/* *`<br>`git -C * rebase --continue`<br>`git -C * rebase --abort`<br>`git rebase origin/*`<br>`git rebase chantier/*`<br>`git rebase --onto chantier/* *`<br>`git rebase --onto origin/* *`<br>`git rebase --continue`<br>`git rebase --abort`<br>`uv run --no-sync --project "<checkout>" chantier *`<br>`uv sync --locked --project "<checkout>"`<br>`uv sync --locked --check --project "<checkout>"`<br>`uvx --from "<plugin root>" chantier *`<br>`gh pr create*`<br>`gh pr edit*`<br>`gh pr ready*`<br>`gh pr checks*`<br>`gh pr view*`<br>`gh pr close*`<br>`gh pr reopen*`<br>`glab mr create*`<br>`glab mr update*`<br>`glab mr view*`<br>`glab mr close*`<br>`glab mr reopen*`<br>`glab ci status*`<br>and the bare tool rule SendMessage | `$CHANTIER preflight`; `git -C <main checkout> push --force-with-lease -u <remote> chantier/preflight-trial --dry-run`; `gh pr view --json number` (GitHub) or `glab mr view` (GitLab) | documented; unproved (the `chantier` and `SendMessage` rules); refused: a Driver's `git -C` force push with its rule set in place, the stack driver's rebase and force push with no rebase rule set; the ladder is `help refused-push` and `help refused-rebase` |
| A stack | `--mode stack` (or `order mode --note stack`, from any mode) | the above, plus the native stack: `gh stack ...` when the user took the `gh stack` extension, else `$CHANTIER forge-stack create\|rebuild\|show\|unstack` (covered by the `chantier` rule; it calls the stacks API itself) | `gh stack*` | `gh stack view`; with `forge-stack`, the stacks API probe of P9 | unproved (the rule form of an extension command) |
| A release on its own | `--autonomous-releases N` at `open`, or `order grant <release-cr> --note "releases=<n>..."` | the merge of the release PR by the steering session (`gh pr merge <pr> --<the project's method>`, or on GitHub for a PR in a native stack `gh api -X PUT repos/<owner>/<repo>/pulls/<pr>/merge-async ...` and its result `gh api -X GET .../merge-async/<uuid>`, after the stack read `gh api -X GET repos/<owner>/<repo>/stacks ...`; `glab mr merge ...`), the tag push (`git push <remote> v1.2.3`), the publication (`gh release create v1.2.3 ...`, `glab release create v1.2.3 ...`), and what the project's procedure names (for chantier: `just tag`, `uv run --script scripts/release_notes.py ...`: the project's own, no rule offered) | `gh pr merge*`<br>`gh api -X GET repos/*/stacks*`<br>`gh api -X PUT repos/*/pulls/*/merge-async*`<br>`gh api -X GET repos/*/pulls/*/merge-async/*`<br>`glab mr merge*`<br>`git push origin v*`<br>`gh release create*`<br>`glab release create*` | `git push <remote> v0.0.0-preflight-trial --dry-run`; `gh release create`, the merge and the asynchronous merge: no trial, P10's rule check only | documented; unproved (a merge in a native stack, by an agent). Risk: any merge of any PR `gh` can reach, any asynchronous merge of any PR `gh` can reach (it merges every open PR below it in its stack), a push of any `v*` tag, any release on any repository `gh` can reach |
| Fixes on a grant | `--grant-fixes` at `open`, or `order grant ... fixes=on` | the merge of a fix PR by the steering session (`gh pr merge ...`, or for a PR in a native stack the stack read and the asynchronous merge of the release row, `glab mr merge ...`) | `gh pr merge*`<br>`gh api -X GET repos/*/stacks*`<br>`gh api -X PUT repos/*/pulls/*/merge-async*`<br>`gh api -X GET repos/*/pulls/*/merge-async/*`<br>`glab mr merge*` | no harmless form: no trial, P10's rule check only | documented; unproved (a merge in a native stack, by an agent). Risk: any merge of any PR `gh` can reach, any asynchronous merge of any PR `gh` can reach (it merges every open PR below it in its stack) |

The rows "A release on its own" and "Fixes on a grant" are offered only when the user grants them;
they are not in the block above. A tag whose name does not start with `v` is not covered by the tag
rule and gets the strong warning.
