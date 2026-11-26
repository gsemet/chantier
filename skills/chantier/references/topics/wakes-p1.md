# What wakes you (part 1 of 2)

A Driver's line, the host's notice about a Driver, an order, the heartbeat and your watcher wake you.
- The heartbeat: the wake that runs `chantier status --refresh --batch <batch> --epoch <n>` (`timing:` says when, the host row who arms it). With no wake arriving, stop. While the batch is paused with no CR, arm none; the turn that takes the first CR arms it. A new batch arms its own.
- Your watcher (`$CHANTIER watch`, run by your session): start it in the background with the command your `watch: not running: for the Foreman` line prints, as is, in the turn that arms the heartbeat, and again with the command of its last line whenever it ended (a last line that is not `still watching`). It outlives heartbeat and pause. On a switch to direct mode, stop it by its id. Never copy a `watch:` line (printed outside Driver prompt blocks, `take`'s and `order qa`'s included) into a Driver's prompt, nor relay it with the block.
Forge lines, the Chief of Staff's: `help wakes-forge`.
