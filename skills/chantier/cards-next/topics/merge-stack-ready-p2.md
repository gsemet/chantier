# A stack ready to merge (part 2 of 2)

- Add one clause: heavy CI ran at the top PR's head only; merging below without it is their choice; on their word `order note <cr> "heavy CI: at its head"`, and the Foreman's `heavy-ci <cr> <head7> green|red <checks>` ask is told (red changes nothing by itself).
- A refused `$CHANTIER forge-stack rebuild` (an `anomaly`): the user gets the exact text; on their yes run the command the refusal's last line names (`forge-stack create` after `... is dissolved and no stack replaces it yet`, `forge-stack show` after `... the stack's state is unknown`), else `forge-stack rebuild`; no raw `gh api`.
- A stack waiver: name the CR whose gate validates the lower PRs (`waived -> CR-k`) and whether it passed; merging below before it passes leaves main with the failure if it fails.
