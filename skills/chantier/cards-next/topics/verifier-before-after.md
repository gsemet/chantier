# Verifier: before and after

At the end, with the technique of the evidence plan you were given, capture the evidence:
- the before on a detached worktree of the CR's base (`git worktree add --detach <path> <base>`, the one worktree you create; remove it at your end);
- the after at the pushed head, so the two compare. It is still a command run at the pushed head.

The files go to `<work folder>/verifier/evidence/`, with a `before-after.md` that lists each pair, what it shows, how to reproduce it, and the SHA of the before (the base) and of the after. Evidence you cannot capture: `before-after.md` says why.

When the evidence holds screenshots or videos (a project with a UI), open each one and check that it shows what the PR claims of it: the screen, the state and the change the Summary, Deliverables and Impacts say, legible, with nothing that contradicts them. A capture that does not show its claim fails that claim.

On the description pass, check that the images attached are the ones captured at the SHA they name, and give each the look (`help verifier-images`). `verify.md` names an image that fails (which one, what shows), so the Driver replaces it.
