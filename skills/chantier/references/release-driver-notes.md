# Release driver: the notes, the drafts and the PR body

## Release driver: the notes, the drafts and the PR body

- What a person reviews or edits (release notes, an announcement) goes early in the work
  folder, or where the project's procedure keeps it (a folder committed with the version), then
  `note --draft <path>`; read it again each time you use it, never rewrite it.
- The release notes and the announcement thread follow the project's procedure, else
  [release-template](release-template.md). Their captures come from the release's batch (its
  `STATUS.md`, the board, CLI output) and from `report.md` and `conversation.md` in the release
  CR's folder when the Chief of Staff wrote them; a docs diagram only when the release CR's
  specification names it. Their images are anonymised before they leave the machine, and the
  thread is never posted by an agent. Each capture you keep in the work folder or in the folder
  the procedure commits passes the look (`driver-pr-extras.md` "Means: images and the look") before it is kept, and again
  before each upload (a release asset, a push of the release folder's images), on top of
  release-template's reading of each image and its wider list.
- When the procedure opens a version PR, its body carries, under the PR's own description, a `---`
  rule, the release notes, a `---` rule, then the announcement thread under a heading that says it
  is a draft the user posts themselves (no agent posts it). Both are the draft files' text,
  rendered by the forge as Markdown. This is the default: a project whose procedure says where its
  notes are reviewed is followed as written; a release with no PR keeps the drafts alone. The PR's
  own description stays the procedure's; the notes and thread are appended under it, never in its
  place.
- The files are the source and the body a copy. Write the body from the files with the forge's
  own CLI (`gh pr edit --body-file`, `glab mr update` with the file form of the Push bullet (unproved there), or the equivalent for
  another forge; from the file, [concepts](concepts.md) rule 9) when you open the PR, each time a draft changes, and once more just before `handback
  ready <pr link>`. Never copy the body back into a file. A change the user asks for in
  the PR is made in the file (by the user, or on the Chief of Staff's word), then the body is
  refreshed.
- Images in the body: one already on the forge (an asset uploaded under its `release go`, or a
  file the procedure committed and pushed with the version PR's branch) is shown from there; one
  not yet on the forge, or that the forge cannot take, is named in prose (`<file name>: <what it
  shows>`). Every image is anonymised before it leaves the machine, as
  [release-template](release-template.md) says, with the look. The body never links a local path.
- When the whole does not fit the forge's body limit (the forge's own, read from its error or its
  docs), the body keeps what fits in that order (description, notes, thread) and names each part
  left out by its path in the PR's branch or the work folder, with a line saying the body is not
  the whole text. Nothing is cut silently.
