# A refused push or rebase

`chantier push <cr> --lease <n>` is a Driver's one way to publish its branch (`--unit stack` for the stack driver). After a refusal never retry it and never run a raw `git push`.

`push <cr>: git refused the push of <branch>; nothing recorded` (exit 4), then git's text: the remote moved or refused.
1. `note <cr> "refused: chantier push <cr> -> <git's exact text>"`.
2. `handback <cr> blocked refused <exact text>`.

The host refuses the command (`chantier push`, or the `git rebase` before it), your work committed:
1. `note <cr> "refused: <the exact command> -> <the host's exact text>"`: the command as it ran, the whole text as it came, the classifier's label included; never a summary.
2. `note <cr> "next after push: <the steps left, in order>"` (`next after rebase:` for a rebase), so a fresh Driver starts from it.
3. `handback <cr> blocked waits: push <branch> <expected remote sha> <local sha>` (the remote head you expect, from `git ls-remote`, and your head); for a rebase, `waits: rebase <branch> <base>`.
4. Send the line `handback` printed and end: no other push, no other way, no wait in your turn.

The steering session runs the plain `git push --force-with-lease`, then the Chief of Staff if the host refuses it there, then the user is asked once; in direct mode: you, the Chief of Staff, the user. The stack driver sends one line per refused branch, `[stack→foreman] push <branch> <expected remote sha> <local sha>`, and waits for each result as a note. The answer: `help refused-push-answer`.
