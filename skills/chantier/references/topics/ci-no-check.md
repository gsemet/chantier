# When CI lists no check

- The rules do not replace the look: even when they say the project has no CI, the claim comes from the forge's list; the rules only say how to judge it. A list that contradicts them (a check where they say none, none where they say some) is said in a `note`.
- "No CI" needs two looks a minute apart. An empty first look, or a watch that ends at once because no check is reported yet, is no conclusion: a forge registers its checks a few seconds after the push. Say "No CI" only when a second look, a minute or more after the push, still lists no check at the same head. Fill that minute with the work that needs no CI result. A second look that lists checks leads to the normal long wait (`help ci`).
- When that work ends before a minute has passed since the push, run one bounded wait, once (for instance a single `sleep` of the seconds that remain), then take the second look. At most once per pushed head, never a loop.
- The note: `CI: no check listed at abc1234 (gh pr checks 12, two looks, the second a minute after the push)`.
