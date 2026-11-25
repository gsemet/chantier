# The trials before the go

At step 1 of a batch, after the preflight with the batch's options: one harmless trial per used capability, run by you, each command alone, in this session's permission mode, with the user there (a command the CLI ran would be a child process the host never sees). Forms (host row "Trial before the go"):
- every batch: the `$CHANTIER preflight` you just ran; `git -C <main checkout> push --force-with-lease -u <remote> chantier/preflight-trial --dry-run`; on GitHub `gh pr view --json number`, on GitLab `glab mr view`;
- a stack with the extension: `gh stack view`; with `forge-stack`: the stacks API probe of P9;
- a release on its own: `git push <remote> v0.0.0-preflight-trial --dry-run`; `gh release create` and the merge, and fixes on a grant: "no trial: P10's rule check only".
- A trial proves the host let the command run; the command's own error (no such branch, no PR) is a pass. A denial, a prompt or a classifier refusal is a refusal, said at once with the command and the host's exact text, in the strong warning, with the rules P10 named; it never blocks the go. A pass where P10 named a missing rule: say the limits of the host row "Auto mode" (a pass proves nothing for a Driver).
- Recorded after `open`: a section "Permission trials" in `brief.md`, one line per trial, `<capability>: <command> -> ran | refused: <exact text> | no trial: P10's rule check only`, with the P10 line. Before a batch, the result is told, not recorded.
