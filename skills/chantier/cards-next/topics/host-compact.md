# Claude Code: compacting and the reload after it

Name a compacting setting to the user only when asked; no role runs `/compact`, the person types
it. Documented (<https://code.claude.com/docs/en/settings-reference>): auto-compact is on;
`autoCompactWindow` is 100000 to 1000000, capped at the model's window; `idleCompaction` (default
true) compacts after about an hour idle; the prompt cache lasts 1 h on a subscription, 5 min on an
API key (`promptCacheTtl`). `/compact` continues the same conversation.

Recommendation, not a proved fact: keep `idleCompaction` on and set `autoCompactWindow` to 300000
in `~/.claude/settings.json` for the Chief of Staff's and the Foreman's sessions (the plugin's
agents carry 200000). Measured compactions at a 300000 window came near 165 to 170k tokens, so
whether 300000 holds is **unproved**; one session with the setting read back by `/autocompact`
and the token count at its first compaction would settle it.

```json
{ "idleCompaction": true, "autoCompactWindow": 300000 }
```

After a compaction the plugin's mod adds a message naming the role (`help reload`): call your
skill again with the argument `reload`, then run the brief again. **Unproved** until seen: the
mod is Claude Code's only; a session without it reloads by hand (`/chantier:chantier reload`,
`/chantier:chief-of-staff reload`, `/chantier:griller reload`).
