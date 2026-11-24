# Release driver: after the merge

## Release driver: after the merge

- A release PR merged (you see it on the forge, `gh pr view <pr>` or the forge's equivalent the
  host card names, and `release go` answers `go` because of the merge) needs no further go from
  chantier.
  - A step after the merge waits for the user's word when the procedure, the release CR's
    specification or the take note holds it for the user's approval.
  - Each such step that an approval names runs without a hand-back. The approvals are in
    `handoff`'s `approvals unused:` line, the `approved:` notes and the take note; under a grant
    they are there too (the merge under the grant spends none).
  - A `wait: <step>: ...` note later than the approval of the same step is stronger: that step is
    held as if never approved (`approvals unused:` still lists it: the CLI keeps no withdrawal).
  - Run the procedure's steps in its order, approved ones included. At the first held step that no
    approval names, `handback blocked approval: <that step>[; <each later held step with no
    approval>]`; name the steps already run in a `note`. A later held step that is already
    approved is not asked again.
  - The main-checkout step (a step of the procedure that runs in the main checkout; for this
    project `CONTRIBUTING.md` "Release" step 4, `just tag`) is never yours: never run it, neither
    in the main checkout nor in your worktree. When the procedure reaches it, the approval rule
    above applies first (a held step with no approval gets `handback blocked approval: <step>`).
    Once it is approved, name in a `note` the steps already run, then `handback blocked waits: the
    steering session runs <the step> in the main checkout`, quoting the step as the procedure
    writes it (for chantier, `just tag`). A take note that starts `tag done:` says the steering
    session ran it: go on from the procedure's next step and never run it again; the steps
    already run include it. Check its result read-only, where you can (for chantier, `git -C
    <worktree> ls-remote --tags origin v<X.Y.Z>`); with the tag missing, `handback blocked
    question:` naming the missing tag.
  - The publication step (for this project, `CONTRIBUTING.md`
    "Release" step 5, `gh release create … --verify-tag --notes-file …`) is yours once `release go`
    answers `go`, when the host lets it through (its rule is offered only under a release grant;
    without it the host asks or its classifier judges). When the host refuses it, report the
    refusal with its exact text (rule 7) as `handback blocked approval: publish: <the exact
    command>` and try nothing else: the steering session gives the user the command ("the
    publication is yours") and never runs it without their word. The command handed back must run
    as written once you have ended: the notes file and the assets it names are not in a folder
    your end removes (keep them in the CR's work folder or the worktree, never in a temporary
    folder you clean up). Before the hand-back, name in a `note` the steps of the procedure
    already run (for chantier, `just tag`), as the held-step bullet above asks.
- The publication done by someone else. A take note (or a message) that starts `publication
  done:` says the publication step was run outside you: by the user, or by the steering session
  on the user's word. It is not a new attempt: no `release start`, and no step already run is run
  again (read the notes: the previous Driver's `note` names them). Never run the publication
  command again, whatever the note says. Check the publication on the forge, read-only: `gh
  release view <tag> --json url,tagName,isDraft` on GitHub, `glab release view <tag>` on GitLab
  (**unproved** there), or the equivalent the host card names.
  - Found and not a draft: the publication step is done; its text may differ from the prepared
    notes, which is accepted (CONTRIBUTING.md "Release" step 5). Run the procedure's later steps
    that are yours, with their holds, by the bullets above (for chantier there is none: step 6,
    the announcement, is the user's). Then run `release-driver-end.md` "Release driver: the end", whose `release
    published <cr> --note "<version> <link>"` takes the link the forge printed.
  - Not found, or a draft: `handback blocked approval: publish: <the exact command>; not on the
    forge: <what the forge printed, first line>`, and nothing else.
