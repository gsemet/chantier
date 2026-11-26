# "auto" for a release (part 1 of 2)

While the release runs (from its Driver's start to `release published` or the CR's end) offer "auto" as the "during a release" tip, one line with the exact word; on an approval ask (`blocked <release-cr> approval: <action>`) the question lists "auto" beside approving that one action: part of the question, not a tip, so there with tips off too. On "auto" (the user's own word, any language):
1. `$CHANTIER handoff <release-cr>`; read `<k>`, the releases already published, from its `grant:` line.
2. No budget in the batch: ask for one with a recommended figure (the CLI refuses autonomy without it); send nothing before the answer. Then `$CHANTIER preflight --autonomous-releases 1`, P9's probe 5 and the release trial; ask the release-rules question still missing and act on the answer. The grant never waits for the rules: the user's word is the grant. The same for a later `order grant ... fixes=on` with `--grant-fixes`.
3. `$CHANTIER order grant <release-cr> --note "releases=<k+1>[ budget=<usd>]"`, and record the user's word with the date in the CR's `02-answers.md`.
4. Send the order's line to the Foreman (direct mode: act on it; a CR blocked on an approval goes back to a Driver with `--note "auto: <the grant line>"`).
