# Finding the planning surface (part 1 of 2)

- Once per session, before `$CHANTIER` runs: read the project's `AGENTS.md` pointer line (`- planning: <url>, projects/<name>`). No pointer and a `.agents/changes/` in the checkout: it plans in itself, no `--project`. With one, the surface is the session folder whose `git remote get-url origin` names that url (without a trailing `.git`, https or ssh alike) and that holds `projects/<name>/`. `$CHANTIER` is then the skill's command plus `--project <absolute surface folder>/projects/<name>`.
- The session keeps it: plan writes through `$CHANTIER` by absolute paths, git reads with `git -C <surface>` for the plan and `git -C <clone>` for the code, never a bare `git`.
- A pointer line and no matching folder: say first "this project plans in the surface at <url>; add its checkout to this session, or start the session there", and plan nothing in the project.
- The session's folder is a main checkout, of the surface (default branch) or of the project (its clone, as `checkout.yml` places it); P6 and P7 refuse a linked worktree of either. The clone hosts the session when it is the cwd; the CRs' worktrees never do.
- The other preflight lines are a batch's, but P5, P9 and P10 go in the first message.
