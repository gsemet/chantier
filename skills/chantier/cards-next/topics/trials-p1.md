# The trials before the go (part 1 of 2)

At step 1 of a batch, after the preflight with the batch's options: one harmless trial per used capability, each writing nothing (a `--dry-run` push of a missing branch or tag stops at the refspec, before the remote; keep `--dry-run` last, under the rule's `*`), run by you, each command alone, in this session's permission mode, with the user there (a command the CLI ran would be a child process the host never sees). Forms (host row "Trial before the go"):
- every batch: the `$CHANTIER preflight` you just ran; `git -C <main checkout> push --force-with-lease -u <remote> chantier/preflight-trial --dry-run` (a CR's branches must stay force-pushable: host and forge let a rebase through); on GitHub `gh pr view --json number`, on GitLab `glab mr view`;
- a stack with the extension: `gh stack view`; with `forge-stack`: the stacks API probe of P9;
- a release on its own: `git push <remote> v0.0.0-preflight-trial --dry-run`; `gh release create` and the merge, and fixes on a grant: "no trial: P10's rule check only".
