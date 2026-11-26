# Release pictures

One image per highlight; a change that replaces a visible behaviour shows before and after side by side, from the Verifier's before/after. Sources: the merged CRs' `evidence/` (`4-batch/3-done/`, `5-archives/`), the merged PRs' Deliverables, captures of the product running, CLI output, and the release CR folder's `report.md` or `conversation.md`, anonymised (`~`, `user`, `user@example.com`, `<session>`, `example/app`).

- Only a visible change (a fix too) gets an image, one per change, cropped to it (never the whole window), 900 to 1200 px wide, at most 600 px high; before/after is one joined image, same region and scale. The alt text is the caption, one plain phrase on what it shows, with no caption line.
- No image in the sources: capture and crop it with the project's own means before the notes are final. No capture or crop within bounds: the notes say nothing; the version PR's Known gaps (no version PR: a `note` and the hand-back report) names `no picture for <change>: <why>`.
- Read each image before keeping it: crop, size, alt text, the look (`help pr-images`). A docs diagram only on the user's word in the grill.
- Name an image as `<img src="...">` or in prose, never a Markdown link to a file that may not exist, the PR's body too.
- Uploading an image (the forge's own CLI) is irreversible: `release go` first. Published notes use the reviewed text; where the procedure publishes none, they stay a draft for the user.
