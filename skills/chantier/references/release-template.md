# Release template

The default release notes and announcement thread, written by the release Driver.

## Scope and precedence

- It is the default form of a release's notes and announcement thread, written by the release
  Driver. The project's own release procedure, and what `$CHANTIER rules` reaches, rank above it.
  Where the project says how its notes or its announcement are written, the Driver follows the
  project as written, and this file only fills where the project is silent.
- The mechanics (version, tag, publication, gates) are always the project's own, and this file
  adds none.

## The notes

Written for the project's users, with no CR, batch or agent-role reference, as in
[pr-template](pr-template.md). The structure, in order:

- a header: the product name, the version, one bold line of verbs naming the headline changes, and
  a `<sub>` line with N changes since the previous version, what it runs on, and the licence;
- a line of links: install, docs, full changes;
- two to four highlights, each with what changes for the reader, a usage or call example, the
  visible evidence, a link to the doc, and why it matters;
- the smaller changes, one bullet each;
- the fixes and the contributor notes, folded.

Every `feat:` and `fix:` commit since the previous version appears once.

## Visible evidence

Each highlight shows what ships. The sources are:

- the Verifier's before/after in the archived CRs' `evidence/` folders;
- the screenshots in the merged PRs' Impacts sections;
- captures of the product running, made by the Driver;
- CLI output.

When the release CR's folder holds `report.md` or `conversation.md`, they are sources too. They
are anonymised: no personal path, user name, email, private repository or session id, replaced by
`~`, `user`, `user@example.com`, `<session>` and `example/app`. The Driver reads each image it
produced before it keeps it. With nothing visible to show, the highlight says so in one line: no
invented image. A diagram of the project's docs is shown only on the user's word in the release
CR's grill.

In the skeleton, name an image in `<img src="...">` form or in prose, never as a Markdown image
link to a file that may not exist.

## The thread

Three posts:

1. the story, which may be long: first person, a concrete moment of work the release improves,
   then what is different now, at most three changes in plain words; it carries the thread's one
   image;
2. the link to the release notes;
3. one sentence (install or update, the price, the licence) and the install link.

The tone is organic: no launch words ("excited to announce", "game changer"), at most two emoji,
no list of hashtags. No agent posts: the thread is a draft for the user.

## Where they go

By default the Driver writes `release-notes.md`, `tweet.md` and the images in `<work folder>/release/`
and runs `note --draft` on each text, as [driver](driver.md) says. Where the procedure publishes
notes (a forge release, a changelog entry), the Driver uses the reviewed text there. The images
are attached with the forge's own CLI, and that is an irreversible action (`release go`). Where
the procedure publishes no notes, they stay a draft for the user.
