# What a Release driver does

A Release driver runs a release as a CR, by the project's release procedure, and the owner stays out of the way. The night before, the CR drivers open the stack's pull requests as drafts. At time zero the owner starts merging the stack, six pull requests over about three hours, and the project's heavy CI runs on the default branch's head, about 22 minutes. Once the stack is merged, the Foreman (or the Chief of Staff in direct mode) starts the Release driver, which creates the release CR folder. The Chief of Staff proposes the version from what was merged, a patch for seven user-visible fixes, writes its latest Progress report as a source for the notes' captures, and the owner answers whether a release is worth it, yes, now; the Chief of Staff confirms the version. The Release driver checks that the heavy run is green on that exact commit before any version commit exists, writes the release notes and the announcement thread from the changelog or the commits, makes the version commit and opens the version pull request, whose body shows the rendered notes and thread separated by rules. The owner reviews the notes and the thread there and says publish, or auto; from that review to the publication the owner asks nothing. After release go, the steering session merges the version pull request. The version push run fans out into parallel jobs: static, static on Windows, visual, integration and stress, the last taking 22 minutes; then the tag, the package and its publication, and the pages are built. The Release driver watches the CI, checks the deploys, the tag, the forge release with its images, the package registry's version and the pages, then records release published, writes retro.md and hands back ready, and the CR is archived. The owner posts the announcement thread; an agent never does. If a heavy job turns red, which did not happen in the example, the Release driver writes fix-n.md and hands back, the Foreman starts a fix CR (at most three per release, under the user's fix grant, else the user's go), a CR driver codes it, the Foreman merges it under the grant, else the owner, and the Release driver starts a new attempt on the fresh base, from the first step, the heavy run again. A loop arrow goes from the archive back to the intake: the retro and the owner's remarks become process CRs, in the example two process pull requests the same day. In the example the Chief of Staff did the Release driver's work itself, in direct mode; the target is that the steering session starts a Release driver once the other CRs are merged and the owner has confirmed the version. In numbers: the first stack merge to published, about 4 h 20; the heavy run to published, 1 h 16; the version pull request open to merge, 14 minutes; the version push to the registry, 23 minutes; the owner, 4 messages; no fix CR, no red job, no retry; notes of 13 changes with three highlights.

## Header

```md
🚚 What a Release driver does
From the owner's “release” to the archive, on a real patch release.
```

## Legend

```md
👤 owner
🤵 Chief of Staff
👷 Foreman
🚚 Release driver · 🚜 CR driver
CI · forge
owner touchpoint
CI run
not needed in the example
```

## Lanes

```md
👤 Owner
🤵 Chief of Staff
(👷 Foreman, with one)
🚚 Release driver
🚜 CR drivers
(fix CRs)
CI
(the project's heavy CI)
Forge and registry
(tag, release, package
registry, pages)
```

## Time axis

```md
Time since the owner's first merge
of the stack (relative)
0
+30 min
+1 h
+1 h 30
+2 h
+2 h 30
+3 h
+3 h 30
+4 h
+4 h 30
break
← the night before: the
stack's PRs opened as drafts
(compressed break)
```

## Owner touchpoints

```md
merges the stack
six PRs, over about 3 h
“is a release worth it?” → “yes, now”
7 user-visible fixes → a patch
reviews the notes and the thread
in the version PR, says “publish”
posts the announcement thread
never an agent
owner asked nothing
```

## Gates

```md
about 22 min
heavy run on the default branch's head, green before the version commit
static (3 min)
static on Windows (4 min)
visual (13 min)
integration (12 min)
stress (22 min)
tag, package and publish, pages
```

## Outputs

```md
tag
forge release + images
registry version
pages
```

## Release driver

```md
👷 starts the
Release driver
🤵 proposes the version,
order confirm
🤵 report.md: latest Progress
report, source of captures
👷 merges the version PR
after release go
release CR folder
notes + thread
from the changelog or commits
version commit
version PR
watch CI
check deploys
release published
retro.md
handback ready
archive
```

## Fix path

```md
red heavy job
writes fix-<n>.md,
hands back
👷 starts a fix CR,
≤ 3 per release, fix grant,
else your go
🚜 codes
the fix CR
👷 merges it under the
grant, else the owner
new attempt, from the
first step (heavy run)
fix path (dashed):
not needed in the example
```

## Loop

```md
📨 intake
retro and owner remarks
become process CRs
(in the example: two
process PRs the same day)
```

## Footnote

```md
In the example the Chief of Staff did the Release driver's work itself, in direct mode.
The target: once the other CRs are merged and the owner has confirmed the version, the steering session (the Foreman, or the Chief of Staff in direct mode) starts a Release driver.
```

## Annotations

```md
In numbers
first stack merge to published: about 4 h 20
heavy run on the default branch to published: 1 h 16
version PR open to merge: 14 min
version push to registry: 23 min
owner: 4 messages
fix CRs 0 · red jobs 0 · retries 0
notes: 13 changes, three highlights
```

