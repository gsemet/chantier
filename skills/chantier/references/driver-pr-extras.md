# Drivers: the archive, images and GitLab forms

## Means: the archive in the PR

- The archive in the PR: when `take` or `handoff` prints `archive: in the PR at <path>`, before
  each `handback <cr> ready` write the cleaned archive in your worktree at that path and commit
  it with the change: `intake/`, `evidence/`, `01-intent.md`, `02-answers.md`,
  `03-change-spec.md`, `delivery.md` (what the PR delivers, from the PR body's summary, with the PR
  link once known) and `STATUS.md` as it stands; no `work/`, no log. Keep it current at each later
  round. The retained prototype goes in too: the version `02-answers.md` (or the specification)
  names as retained, copied as `prototypes/NN-<idea>/`, or zipped as `prototypes/NN-<idea>.zip`
  when it is above 1 MB (up to 10 MB); when `02-answers.md` records a decision on a very big
  folder, follow it. No other version and no `experiments/` go in the PR's archive (they stay in
  the planning folder's `5-archives/`); with no retained prototype named, nothing from
  `prototypes/` goes in. Each image added or changed in the archive passes the look (The
  evidence, above) before the commit; one that fails stays out until it passes. A retained prototype above 10 MB with no recorded decision stays out of
  the archive: say it in a `note`, and name it in the PR's Known gaps ("retained prototype not in
  the archive: too big, no decision recorded"), so the ready line quotes it and the Chief of Staff
  asks the user. The same Known gap names a folder that grew very big during the batch. `ship`
  says `archive missing from the PR at <path>` when it is off. When the project
  ignores `.agents/changes/`, say it in a `note` and hand back with the PR as it is: the Chief of
  Staff asks the user (no `git add -f`). `archive: not in the PR` means no archive in the worktree, no `.agents/changes/` path in the diff,
  and no `delivery.md` to write for the PR; that is the default with a planning surface.

## Means: images and the look

- A taken-back note `evidence: <path>` is an image to attach the same way: remove the matching bullet from
  Known gaps, run the description pass, hand back ready. An image linked into a commit of the CR's branch
  is not an upload; one found after a move (`ship`'s `off: pr-body.md line <n> shows an image from …`) is
  attached by you with the forge's CLI, using the same image file (from `work/`, or from `git show
  <old>:<path>` while the commit is still local), before the PR turns ready; it is captured again only
  when a Verifier is due anyway (a conflict, a refused carry). Every image is given the look before it
  is kept or uploaded, below.
- A Driver never opens an image file (`.png`, `.jpg`, `.gif`, `.webp`): it attaches the images the Verifier
  or the Demo explorer names, by path and caption, and judges them from their reply.
- No image shows the user's username or home folder; every image you keep or upload shows made-up
  paths. Terms: the *user's username* is both the login name of the machine you run on
  (`$env:USERNAME` on Windows, `$USER` on Linux and macOS) and the last part of the home folder's
  path (they can differ; check both). The *home folder* is its full path (`C:\Users\<name>`,
  `/Users/<name>`, `/home/<name>`) in any form on screen (either slash, `~` expanded, inside a
  longer path such as a temporary folder under it). A *made-up path* holds neither, wherever the
  image shows a local path (planning folder, worktree, file, prompt, window title); how you get it
  is yours (a made-up folder name, `~`, `user`; a scratch project under `work/scratch` sits under
  the user's home folder, so rewrite its paths in the capture, or do not keep it). *The
  look*: open the image as an image (not its file name) and look for both; it passes once neither
  shows. *Keeping* an image is writing it anywhere in the planning folder (a CR's `evidence/` or
  `work/`, a QA work folder's `evidence/`), which is pushed with the surface. An *upload* is any
  way an image leaves the machine for the forge: `gh pr edit --attach` or another forge CLI's
  attach, a release asset, a push of a commit that adds or changes an image. Give each image the
  look before you keep it and again before each upload; keep or upload it only once it passes. An
  image of yours that fails is captured again with made-up paths; the Verifier's that fails is
  asked again of the Verifier; none is kept or uploaded meanwhile. The user's own screenshot (the
  taken-back `evidence: <path>`) gets the look before the upload: when it fails, do not upload it
  or copy it into the planning folder, keep its Known gap (the PR's Known gaps still quotes it),
  and say why (it shows the username or the home folder) in a `note` and in your hand-back
  report. A leak found after an upload (your description pass, or the Verifier's `NOT VERIFIED`
  on it): replace the image in the description with a clean capture (made-up paths, given the
  look) and say in a `note` and in your hand-back report that the old one was uploaded (the PR,
  which image, at which SHA); a removed attachment can stay reachable on the forge, so the user
  is told. When the leaked image is the user's own screenshot, remove it from the description,
  put the Known gap back, and say so in the same `note` and report. Nothing about the leak goes
  in the public PR.

## Means: GitLab forms

- For GitLab, use `glab`'s
  option that reads the description from a file (settle the exact form from `glab mr create
  --help`), with no text in the command and no shell substitution such as `"$(cat file)"`;
  unproved; trial: a GitLab MR opened and edited from `pr-body.md` whose body holds backticks,
  `$` and quotes, and whose description on the forge matches the file byte for byte.
- Unproved on GitLab and Copilot: GitLab's `draft` field is unproved on a real
  instance; trial: one `ship` of a draft MR and of a ready MR on a GitLab project, the recorded
  draft state matching the forge; on GitHub Copilot unproved; trial: one Driver on Copilot that
  turns its PR ready and runs `ship`, the CR reading `ready to merge`
