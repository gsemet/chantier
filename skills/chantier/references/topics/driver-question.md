# A Driver's question, a fix, a refused command, a wait

- `ask ... blocked <cr> question: ...`: record the user's answer in the CR's `02-answers.md`, then `order note <cr> --note "answer: ..."`.
- A `fix:` from a release: under the grant the Foreman starts it alone; else show the user its `fix-<n>.md`, and on their go `order add --note <that file> --fix-for <cr>`, or file and grill a CR when it needs more.
- `refused <cr> <text>`: show the exact text, record it at once with `$CHANTIER note <cr> "refused: <exact command> -> <exact text>"`; the user types one line in the Foreman's session allowing that action.
- `qa <folder> <n> findings`: its inbox folder is an ordinary item; triage it with the user, split into CRs as needed.
- A typed wait (`$CHANTIER wait <cr>` lists a blocked CR's waits; `status` shows `| waits:`): cleared on the user's answer, or on a `wait-cleared@1` line your watcher carries: `wait <cr> clear <id> --epoch <n>`, then the take-back path as for any blocked CR. A parked CR: `wait <cr> clear <id> --epoch <n>`, then `order note <cr> --note "wait cleared: <what>"` (Foreman mode), or in direct mode `take <cr> --note "wait cleared: <what>" --epoch <n>` before any queued CR. On `parked <cr>: ...` tell the user in one line: the CR, what it waits for, its slot is free, the batch goes on; ask nothing.
