# Session titles

Read by the Chief of Staff and the Griller at the start of a session, and by the Chief of Staff when
it builds the Foreman's prompt (the Foreman's row below).

As soon as the role is set and whenever it changes, the session renames itself by the host's
means (its reference); a host that cannot rename: nothing, no workaround.

A title tells first whether the user talks to the session, then the project and the role, with the
machine's code in front: a phone shows about 25 characters of a title. Its parts:

- **Machine code:** `[<code>]` first. The machine's name (the first label of `hostname`) as it is
  when it has 6 letters or fewer (`Mac`), else its first 6 letters (`Battlestation` gives
  `Battle`), its first letter uppercase. A user's word renames the machine for the session only. In
  a cloud session (the host's reference says how to tell) the code is `Remote`.
- **Icon**, after a space: `💬` for a session the user talks to (the Chief of Staff, a Griller),
  `⚙️` for one they do not (the Foreman).
- **Project**, after a space: the repository's folder name, or, in a surface, the project's folder
  in it, capitalised (`Chantier`).
- **Batch number:** only for a session that steers a batch (the Foreman, the Chief of Staff in
  direct mode), last, in parentheses after a space as `(Batch <nn>)`, on two digits as in the batch's id (`(Batch 17)`).
- **Role:** `CoS` for the Chief of Staff, `Griller`, `Foreman`. A Griller adds its subject once
  known, after the role: a few of the user's words, not a slug.
- **Separator:** ` · ` (space, U+00B7, space) between the project, the role
  and a Griller's subject.

| Session | Title |
| --- | --- |
| Chief of Staff | `[<code>] 💬 Project · CoS` |
| Chief of Staff steering a direct batch, from `open --direct`, the hand-over or a switch to direct mode until the batch is closed, then back to the line above | `[<code>] 💬 Project · CoS (Batch <nn>)` |
| Griller | `[<code>] 💬 Project · Griller` |
| Griller, once its subject is known | `[<code>] 💬 Project · Griller · <subject>` |
| Foreman, given in its prompt ([chief-of-staff-batch-start](chief-of-staff-batch-start.md)) | `[<code>] ⚙️ Project · Foreman (Batch <nn>)` |

Examples: `[Battle] 💬 Chantier · CoS`, `[Battle] 💬 Chantier · CoS (Batch 17)`,
`[Battle] 💬 Chantier · Griller`, `[Battle] 💬 Chantier · Griller · landing page`,
`[Battle] ⚙️ Chantier · Foreman (Batch 17)`, `[Mac] ⚙️ Chantier · Foreman (Batch 06)`,
`[Remote] 💬 Chantier · CoS`.

- The title given to `seat take --title` is the session's current title; take the seat again
  (same session, no `--over`) when it changes.
