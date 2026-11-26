# Verifier: images with no username

Every before and after image you capture shows made-up paths and no username (floor rule 8).

Terms:
- The user's username is both the login name of the machine you run on (`$env:USERNAME` on Windows, `$USER` on Linux and macOS) and the last part of the home folder's path. They can differ: check both.
- The home folder is its full path (`C:\Users\<name>`, `/Users/<name>`, `/home/<name>`) in any form on screen: either slash, `~` expanded, inside a longer path such as a temporary folder under it.
- A made-up path holds neither, wherever the image shows a local path (planning folder, worktree, file, prompt, window title). How you get it is yours: a made-up folder name, `~`, `user`.

The scratch project under `work/scratch` sits under the user's home folder, so a capture of it shows the user's paths: rewrite them to made-up paths in the capture, for example in a text output before rendering it.

The look: open the image as an image and look for both; it passes once neither shows. Give each capture the look, as you already open it for what it claims. One that fails is captured again with made-up paths before it is kept in `<work folder>/verifier/evidence/` (pushed with the planning folder). One you cannot capture that way is not kept, and `before-after.md` names it with why.
