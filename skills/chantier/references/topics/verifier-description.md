# Verifier: the PR description

The PR's description, as posted on the forge, is one of the claims. It fails (`NOT VERIFIED`) when:
- it does not render (line breaks, sections, the fold, images that resolve);
- it is inconsistent with the diff at the pushed head: a claimed change missing, or a delivered change unmentioned;
- an image attached to it shows the username or the home folder (`help verifier-images`);
- a proof does not name its SHA: the head, or `carried from <sha7>` with its reason (valid after a clean rebase);
- a claim stated as fact has no proof in `verify.md`, the gates or the evidence (the Driver marks it `UNVERIFIED` or narrows it);
- a `STALE` mark is left at the end;
- Known gaps lacks a bullet for an `**UNVERIFIED:**` claim, an evidence pair `before-after.md` says was not captured, or a failed claim accepted rather than fixed, or says "None" while one exists;
- a role name is the doer of the work outside Internal references. A product term of a change to that role is not a failure ([pr-template](../pr-template.md), "The rules": the bullet on internal references and the one after it).

Given only the description, check only it. A description found `NOT VERIFIED` cancels an earlier `VERIFIED` at that head until a later pass says `VERIFIED`.

The Review box: `help verifier-review-box`.
