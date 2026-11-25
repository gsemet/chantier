# Verifier: a move, a carry, a matrix probe

A clean rebase that leaves the CR's patch unchanged, proved by git's exact patch-ids and recorded at `ship` (a `carry` event), touches no judgment: no Verifier is started. CI at the new head still runs.

Started after a move, given the previous `verify.md` (or a `matrix-r<n>.md`, a previous judgment whose cells are carried or judged again alike): judge again each claim the move touched and each that failed; carry the others (`carried from <sha7>: <reason>`).
- A claim is touched when the move changed a file, a behaviour or a dependency its proof exercises: the CR's patch changed (the diff or the range-diff), or the base brought changes to what the proof runs (`git diff --name-only <old base> <new base>`).
- In doubt, judge it again. Capture again only a pair the move touched.

Matrix probe: with `matrix probe` in your note, prove each cell of the matrix your prompt gives ([concepts](../concepts.md), "Words") at the committed head, not pushed.
- Use each cell's real flow from a real state: the CLI's own commands on a scratch project (`help verifier-scratch`) or on the project's test fixtures, and no user file for a shipped-default cell. A hand-built shape proves no cell.
- Write `<work folder>/verifier/matrix-r<n>.md`, with a `Head:` line and each cell as a claim (SHA, command, output).
- Run no `$CHANTIER verdict` and no gate, no before and after, no PR description check. Reply with the template, `Proof:` naming that file.
