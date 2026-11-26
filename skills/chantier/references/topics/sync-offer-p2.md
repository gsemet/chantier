# A sync that waits for holders (part 2 of 2)

No offer while another holder is listed or a gate runs (listed, or shown by `$CHANTIER status`).
If the conditions first hold after the 3-minute message, the offer is the **For you** item's new
state, outside a batch the one more chat line; no third line: a gate or holder appearing after the
offer is not told, and the offer stands for a later yes while the conditions hold.

On the yes: stop the watcher and the board by the host's stop of their background shell (never by a
PID), list the holders again, sync only if none, then start the board and the watcher again
(`help board-restart`), whatever the result; the yes covers the restart. A holder still listed is
waited on, never killed (the board's restart then prints `board already running`: pass it on). No
answer: the offer stands. A no: do not ask again; the **For you** item names the holders only,
plus "a later yes still counts".
