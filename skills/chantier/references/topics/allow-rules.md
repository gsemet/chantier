# The allow rules (P10, Claude Code)

The one write chantier makes in the user's settings, and only on the user's yes, once per session per capability (the host row "Capabilities and their commands").
- The question: one, in the first message after the P5 and P10 lines: "add these rules to `~/.claude/settings.json`?" It lists each rule P10 named (not one marked `present`) with its real path and its risk, from the host row. A first turn covers "every batch" only; the go covers the batch's capabilities with what is still missing; a later grant (`order grant`) its capability. The rules of "a release on its own" and "fixes on a grant" are offered only when the user granted them. Say once that the rebase rules are "rebase and force-with-lease of chantier's own branches, once per machine".
- On the yes: add exactly those rules to `permissions.allow`, merged (never replace, remove or duplicate), creating the file or keys when absent, valid JSON. Run `$CHANTIER preflight` again and say what P10 says. Whether this running session picks it up is unproved: a session or agent started afterwards reads it.
- Nothing else is written in any settings file: not the project's `.claude/settings.json` or `.local.json`, no deny, ask or other key. A Griller reports the P10 line and says the Chief of Staff asks.
- More cases: `help allow-rules-more`.
