# Claude Code: what the user configures

Marks: **documented** (the docs say so, link given), **unproved** (nobody saw it: say it is not
known, and what would settle it); any other mark means seen.

- Who reads it: the Chief of Staff at a session's first turn and each batch's preflight (P5 tools,
  P9 forge rights, P10 allow rules). On missing rules it asks the user's yes and adds them
  (`help allow-rules`); it gives the command line of `help host-allow-add` only when the host
  refused the edit or the file is not JSON. Chantier writes no other setting of the user's.
- P10 counts commands, not rule strings: `<n>` is that capability's samples that apply to the
  project (any forge, the remote's, `gh stack` for a stack when `gh extension list` names it, plus
  `SendMessage` for every batch), `<k>` those the settings do not let through; on Windows a command
  is allowed only when its Bash and PowerShell forms both are.
- Prerequisites: `git` and `uv` (P5, preflight fails without); `gh` or `glab` logged in (P9). Not
  checked: `python` (`uv` supplies it; on Windows the Store alias fails: the user's fix), `bash`
  (unproved whether Windows needs it), `claude` (no card calls it).
- Windows PowerShell 5.1: a `gh` or `glab` argument with spaces or double quotes (a `--jq`
  expression) can arrive split (`accepts 1 arg(s), received 3`): print `--json <fields>` alone and
  read it, or write the expression with no space and no double quote.

[Trials](../../../../docs/proofs/claude-code.md#other-configuration)
