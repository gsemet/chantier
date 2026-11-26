# Status, turn ends and reports (part 2 of 2)

- Before each report, in both modes, `git status --porcelain` on the main checkout (the clone `take` names) and name every path outside the planning folder not named yet; revert nothing, hold no CR back. Give the latest `main checkout:` note of a CR merged since the last report (`status --notes`, `log <cr>`; `status-layout.md`): a fast-forward leaves `git status` clean, so it is no trace.
- Stack batch (direct mode too): before each Progress report read `$CHANTIER forge-stack show`; **Notes** takes `partial stack mergeable below ...`, or while a check fails `stack changing: last mergeable below <sha7>` (or `stack changing`).
