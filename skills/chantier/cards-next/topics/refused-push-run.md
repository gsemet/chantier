# A refused force push: run it

- Rule present: `$CHANTIER note <cr> "push judged legitimate at <local sha7> for <branch>: <what was checked>"`, then the command. Accepted: take the CR back with `push: pushed <branch>` (the stack driver: `[foreman→driver stack] note push <branch>: pushed <branch>`) and send `[foreman→chief-of-staff] pushed <branch>`.
- The host refuses you: `$CHANTIER note <cr> "refused: <the exact command> -> <the host's exact text>"`, then `[foreman→chief-of-staff] push <branch> <expected remote sha> <local sha>`, not through `asks`: a named exception to the `refused` ask, and you ask the user nothing. Retry nothing, try no other form, change no permission setting; wait for `pushed <branch>`, `push failed <branch> <text>` or `push refused <branch>: <text>`.
- A failed lease (the remote moved) or a forge-protected push: never retried. Take the CR back with `push: push failed <branch> <git's text>` and send `[foreman→chief-of-staff] push failed <branch> <git's text>`; nobody waits for a word.
- The way back: `help refused-answer`. Record each refusal once, whoever sees it, before the next step's line.
