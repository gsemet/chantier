# Briefing an extra review step

Each review step your `Team:` lists after the `inspector`, in order. The CLI writes no brief for it, and its agent may be the user's own: your prompt is all it knows.

```text
chantier <review name> for <cr> "<title>" of batch <batch>, in the project <root>.
Read <skill>/references/review-step.md;
the project's rules rank above it: run `$CHANTIER rules` first and read what touches your work.
CLI ($CHANTIER): <the `cli:` line>
<the specification, the worktree and its base, the work folder>
Note: <the round's note, with the move when there is one>
Your review: <what it checks>
```

- No `writes:` line: it writes nothing.
- Record its `APPROVE` at once: `r<n> <review step> approved at <head>`. Its `FIX-REQUIRED` is a round (`help cr-rounds`).
- `phase <cr> review <the review step's name>` before it.
