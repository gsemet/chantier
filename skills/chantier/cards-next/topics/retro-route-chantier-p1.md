# The chantier route (part 1 of 2)

A `chantier` point, on the user's word naming the point for this route; all at the pause, before any `close`, in this order:
1. The repository is the `repository` field of the plugin manifest (`.claude-plugin/plugin.json` on Claude Code, `.github/plugin/plugin.json` on Copilot).
2. Already reported? `gh issue list --repo <owner/name> --state open --search "<key words>"`; a match is named with its link and not drafted. `gh` absent or not reaching it: skip and say so.
3. Draft one file per issue with the host's Write tool (UTF-8, no BOM): `4-batch/chantier-issue-<n>.md`, `<n>` the first point's number (one point, or the points of one cause the user groups). First line the title (`Bug:` chantier did wrong, `Feature:` it lacks a means); then what happened, the long-term fix, chantier's version (`$CHANTIER --version`), the host and version when known, one line saying it came from a batch retro, and for a host cause that it may belong upstream. English; no label.
4. Check before showing: the repository is public, so no project name, private path, code or text of the target project, CR number, slug, batch id, or person's name or data; a point that cannot be said without them is said in general terms, else offered as an inbox item.
5. Show the title and body, the repository's link and the tool; ask a yes per issue. The user may edit, regroup, decline, or post it themselves (give the file's absolute path).
