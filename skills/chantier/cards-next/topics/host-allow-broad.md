# Claude Code: broad rules, moved paths, what the base set leaves out

- A broad chantier rule, a `*` where the path belongs (`uvx --from * chantier *`,
  `uv run --no-sync --project * chantier *`, `uv sync *`, the older `uv run --script * *`), lets any
  command through. P10 finds each in the user's settings, names it with its file and the
  real-path rule that replaces it, and warns even when every command is allowed. The Chief of Staff
  offers the replacing rules at once; the user removes the broad rule by hand: chantier never
  removes or edits a rule of the user's.
- The plugin's real path changes when the host moves the plugin's folder (an update: **unproved**):
  the old rule stops matching, P10 names the new rule missing and the old one stale with its file,
  and the Chief of Staff asks once per update. In the plugin mode P10 takes any other plugin-form
  path as an old copy (one plugin copy per install: **unproved**); in the dev mode it leaves them
  alone and names a dev rule stale only when its folder no longer exists.
- There is no `gh api` rule (it would allow any API write): the stack on the forge changes only by
  `$CHANTIER forge-stack` or the `gh stack` extension.

The base set and two unchecked rules: `help host-allow-extra`.
