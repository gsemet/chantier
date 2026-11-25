# Behaviour measure, chantier 0.15.1

- Window: 2026-11-17T00:00:00Z to 2026-11-25T03:46:05.062Z (first event 2026-11-17T00:00:05.902Z), written 2026-11-25T03:46:33Z
- Version 0.15.1, commit ff042412, cards commit f9804337 (2026-11-25T00:09:33+01:00)
- Files read 4136, skipped 2368, runs of no chantier role 484

## verifier

| figure | value |
| --- | --- |
| runs | 720 |
| tool calls (total, mean per run, median) | 9385, 13.0, 10.0 |
| model calls (total, mean per run) | 7294, 10.1 |
| card bytes (total, mean per run) | 13627776, 18927.5 |
| files read per run (paths, cards) | 2.4, 1.6 |
| chantier calls | 2127 |
| host denials | classifier 5, mode 1 |
| write guard refusals | 94 |
| waits (count, share of tool calls) | 71, 0.8 % |
| tool not in the role's list | Edit 24, Monitor 2, ToolSearch 3 |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 3, 0 |
| help reads by command |  20, board 12, cancel 1, close 1, file 3, foreman 1, handoff 1, init 1, open 11, order 4, order add 2, order mode 1, park 1, phase 2, playbook 1, rules 1, serve 3, take 2, triage 1, triage scratch-probe-request 1, validate 3, verdict 3, watch 3 |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| verifier.md | 10534737 |
| pr-template.md | 1839449 |
| references/ | 559052 |
| chief-of-staff.md | 126719 |
| driver.md | 124248 |
| startup-manifest.json | 70548 |
| concepts.md | 62327 |
| startup-core.md | 56948 |
| SKILL.md:chantier | 41396 |
| hosts/claude-code.md | 33443 |
| foreman.md | 32310 |
| hosts | 29368 |
| session-start.md | 17611 |
| SKILL.md:status | 13975 |
| release-template.md | 12991 |
| hosts/copilot.md | 11174 |
| griller.md | 10767 |
| SKILL.md:chief-of-staff | 10721 |
| inspector.md | 7555 |
| status-layout.md | 6388 |
| foreman-stack.md | 6012 |
| coder.md | 5774 |
| other-card | 4788 |
| init.md | 4738 |
| routing.md | 3326 |
| spec-writer.md | 688 |
| role-core.md | 374 |
| session-start-chief-of-staff.md | 202 |
| host-core-claude-code.md | 147 |

Usage errors:

| template | count | runs |
| --- | --- | --- |
| chantier: error: unrecognized arguments: --lease <v> | 22 | 19 |
| chantier: error: argument cmd: invalid choice: <v> (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, < | 4 | 4 |
| chantier: error: argument cmd: invalid choice: <v>, maybe you meant <v>? (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, | 4 | 4 |
| chantier: error: unrecognized arguments: --lease | 2 | 2 |
| chantier open: error: the following arguments are required: items | 1 | 1 |
| chantier triage: error: one of the arguments --priority --ready --inbox --running-batch is required | 1 | 1 |
| chantier: error: unrecognized arguments: --batch <v> | 1 | 1 |
| chantier: error: unrecognized arguments: --epoch | 1 | 1 |
| chantier: error: unrecognized arguments: --factory | 1 | 1 |
| chantier: error: unrecognized arguments: --no-writer | 1 | 1 |
| chantier: error: unrecognized arguments: --note <v> | 1 | 1 |
| chantier: error: unrecognized arguments: --stream --batch <v> | 1 | 1 |
| chantier: error: unrecognized arguments: <v>...  | 1 | 1 |

Refusals:

| template | count | runs |
| --- | --- | --- |
| no remote <v>: pass --remote <remote> | 8 | 8 |
| prepared CR not found: <path> | 7 | 7 |
| CR-<n>: verdict VERIFIED needs <path> with a line <v> for the head <sha> it records: its Head: line names <sha> | 6 | 6 |
| CR-<n> is held out of the stack (order O-1): `order unhold CR-<n>` first | 3 | 2 |
| Failed to spawn: chantier | 3 | 3 |
| Git does not know the default branch of <v>: read AGENTS.md or ask the user, then pass --default-branch | 3 | 3 |
| no running batch: run `chantier open` first; no batch closed yet | 3 | 3 |
| triage expects a CR folder: <path>, <path> or <path>; got <path> | 3 | 3 |
| --url: at most <n> boards in one screen | 2 | 2 |
| CR folder already exists: <path>; file it again with --slug <other> | 2 | 2 |
| CR-<n> is already held (order O-1) | 2 | 2 |
| CR-<n>: the worktree has uncommitted work: a verdict binds to a head, commit first | 2 | 2 |
| batch-<n> is not closed (a paused batch stays until `close`): `order add` joins new work to it | 2 | 1 |
| no running batch; paused: batch-<n>: pass `--batch batch-<n>` | 2 | 1 |
| only `order merged` and `order add --fix-for` take --epoch: the Foreman's own merge or fix | 2 | 2 |
| this is a linked worktree: init runs in the main checkout (<path>) | 2 | 1 |
| --url: the link holds no key (?k=...): give the link the board printed | 1 | 1 |
| <path> is not a valid batch record: <n> validation errors for BatchRecord | 1 | 1 |
| <path>: expected {<v>: <v>, <v>, "branch | 1 | 1 |
| <path>: formerly.json names CR-<n>, which batch-<n> already holds | 1 | 1 |
| CR-<n> is already dropped: <path> | 1 | 1 |
| CR-<n> is held: lease <n> live until <n>:<n>:<n>; take it again with --reclaim only on the user's word | 1 | 1 |
| CR-<n>: lease <n> not confirmed since <n>:<n> (<sha> min ago); check with the host that its Driver ended, then take it with --reclaim | 1 | 1 |
| CR-<n>: no worktree at <path>; its Driver creates it (`git worktree add -b <path> <path> <base>`) | 1 | 1 |
| O-1 is held: lease <n> live until <n>:<n>:<n>; take it again with --reclaim only on the user's word | 1 | 1 |
| a release CR ends a factory batch: open without --factory, or open the factory and add the release later with `order add --release`, which turns the factory off | 1 | 1 |
| a release CR is in batch-<n>: it ends the factory; open a new factory batch after the close | 1 | 1 |
| access claim <cr>: name the CR | 1 | 1 |
| batch-<n> is not a factory batch | 1 | 1 |
| board not started: a chantier board <n>.<n>.<n> (PID <n>) holds this surface at <n>.<n>.<n>.<n>:<n> and does not answer: stop it (taskkill <path> <n> <path> <pa | 1 | 1 |
| cancel <cr> --epoch <n>: the steering session's command for a CR the user dropped; a Driver stops its own long gate with `gate CR-<n> --stop` | 1 | 1 |
| cannot change what CR-<n> waits for: it is working, not queued; in a stack, its place and base are set by `stack` | 1 | 1 |
| cannot close batch-<n>, something still runs: CR-<n> is queued, not merged or cancelled; order O-1 (add) is open. Nothing was deleted. | 1 | 1 |
| cannot close batch-<n>, something still runs: order O-1 (drop) is open; order O-2 (drop) is open; order O-3 (drop) is open; order O-4 (drop) is open; order O-5  | 1 | 1 |
| cannot close batch-<n>, something still runs: transcript sess1 still runs: its last call stopped on null (<scratch>\proj\x\sess1.jsonl). Nothing was deleted. an | 1 | 1 |
| cannot close batch-<n>: it is running, not paused; `pause --epoch <n>` comes first. Nothing was deleted. | 1 | 1 |
| cannot close batch-<n>: its final cost cannot be priced (no Foreman transcript recorded). Nothing was deleted. | 1 | 1 |
| cannot close batch-<n>: its final cost cannot be priced (no steering transcript recorded). Nothing was deleted. | 1 | 1 |
| cannot drop CR-<n> to <path>: the name <n>-alpha is already used by <path> | 1 | 1 |
| cannot move CR folder <path> to <path> refused for <n> s, the folder is likely held; nothing moved. On Windows a folder cannot move while a process holds it: a  | 1 | 1 |
| chantier.yaml:<n>: board: <v> is network (this machine's local network address, found at each start); a fixed address goes in --host, for one start | 1 | 1 |
| file: the surface's writer is not running: nothing written; for the Chief of Staff: start the surface server ($CHANTIER board --seat <session id>) | 1 | 1 |
| gate CR-<n>: <v> is not a long gate named in chantier.yaml (long_gate.commands); named: a, bad, c | 1 | 1 |
| gate CR-<n>: <v> is not a long gate named in chantier.yaml (long_gate.commands); named: scenario | 1 | 1 |
| journal add: <url> is no CR's issue (chantier interests --kind issue lists them): nothing written | 1 | 1 |
| no batch holds CR-<n> | 1 | 1 |
| no clone of the project at <path> (remote <url> clone it there | 1 | 1 |
| not joined batch-<n>: CR-<n>: depends.json names <v>, which is in neither the batch nor the archives as merged; the CR waits in <n>-ready (`order add --note <pa | 1 | 1 |
| order hold: CR-<n> is the release CR: the release is the top piece of the stack | 1 | 1 |
| order kind: one of add, after, approve, budget, confirm, done, drop, factory, grant, merged, mode, note, qa, rounds, slots, waive | 1 | 1 |
| order merged: CR-<n> not merged or cancelled: the release PR merges last | 1 | 1 |
| order merged: CR-<n>, CR-<n>, CR-<n>, CR-<n>, CR-<n> not merged or cancelled: the release PR merges last | 1 | 1 |
| order mode --note parallel\|series\|stack (any mode to any other) | 1 | 1 |
| park: CR-<n> is queued: only a working or blocked CR is parked | 1 | 1 |
| pause --epoch <n>: the steering session's command; <n> is your number as Foreman of the batch (Foreman n°<n>) | 1 | 1 |
| remote origin already exists. | 1 | 1 |
| take CR-<n> --epoch <n>: the steering session's command; <n> is your number as Foreman of the batch (Foreman n°<n>) | 1 | 1 |
| unknown CR CR-<n> in batch batch-<n> | 1 | 1 |
| watch: --for <v>: one of project, role:<name>, cr:<id>, session:<key>, user | 1 | 1 |
| watch: --stream and --once do not go together | 1 | 1 |
| watch: chantier.yaml:<n>: events: <v> is <whole number><s\|m\|h>, 20s or more, found <v>: fix it, then start the watcher again | 1 | 1 |

## inspector

| figure | value |
| --- | --- |
| runs | 680 |
| tool calls (total, mean per run, median) | 6049, 8.9, 8.0 |
| model calls (total, mean per run) | 4379, 6.4 |
| card bytes (total, mean per run) | 8567216, 12598.8 |
| files read per run (paths, cards) | 2.3, 1.7 |
| chantier calls | 314 |
| host denials | none |
| write guard refusals | 10 |
| waits (count, share of tool calls) | 7, 0.1 % |
| tool not in the role's list | none |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 0, 0 |
| help reads by command | lease 1, order 1, take 1 |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| inspector.md | 4241456 |
| pr-template.md | 2471542 |
| references/ | 766448 |
| chief-of-staff.md | 197404 |
| foreman.md | 195027 |
| driver.md | 160838 |
| startup-manifest.json | 106777 |
| hosts/claude-code.md | 99964 |
| concepts.md | 66803 |
| other-card | 52974 |
| session-start.md | 50152 |
| hosts | 45975 |
| hosts/copilot.md | 36139 |
| SKILL.md:chantier | 28429 |
| startup-core.md | 18703 |
| reload-rules.md | 14014 |
| routing.md | 8463 |
| release-template.md | 4851 |
| chief-of-staff | 862 |
| driver-conflicts.md | 201 |
| role-core.md | 194 |

## cr-driver

| figure | value |
| --- | --- |
| runs | 603 |
| tool calls (total, mean per run, median) | 25535, 42.3, 41 |
| model calls (total, mean per run) | 21627, 35.9 |
| card bytes (total, mean per run) | 39093659, 64831.9 |
| files read per run (paths, cards) | 6.5, 5.7 |
| chantier calls | 8833 |
| host denials | classifier 16, user_rejected 3 |
| write guard refusals | 119 |
| waits (count, share of tool calls) | 4171, 16.3 % |
| tool not in the role's list | TaskStop 4 |
| `chantier push` (calls, refused, rate) | 1, 1, 100.0 % |
| `git push --force-with-lease` (calls, denied) | 130, 9 |
| help reads by command |  9, board 4, file 1, forge-stack 3, gate 21, handback 25, handoff 2, inspector 1, lease 3, note 4, round 5, ship 12, summary 1, summary set 1, take 8, verdict 4 |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| driver.md | 23863497 |
| pr-template.md | 4505951 |
| concepts.md | 3013132 |
| startup-manifest.json | 2930045 |
| references/ | 2411274 |
| startup-core.md | 1090872 |
| hosts/claude-code.md | 868591 |
| verifier.md | 127202 |
| role-core.md | 70214 |
| host-core-claude-code.md | 60368 |
| chief-of-staff.md | 23077 |
| coder.md | 23077 |
| debugger.md | 15664 |
| release-template.md | 13684 |
| session-start | 12256 |
| inspector.md | 10565 |
| SKILL.md:chantier | 10361 |
| investigator.md | 7212 |
| spec-writer.md | 6574 |
| other-card | 5162 |
| SKILL.md:chief-of-staff | 4539 |
| driver-pr-extras.md | 4428 |
| conflict-resolver.md | 3496 |
| hosts/copilot.md | 3212 |
| hosts | 2208 |
| foreman.md | 2094 |
| session-start.md | 1899 |
| chief-of-staff-batch-start.md | 1124 |
| forges/github.md | 910 |
| chief-of-staff-direct.md | 542 |
| review-step.md | 225 |
| driver-retake.md | 117 |
| reload-rules.md | 47 |
| chief-of-staff-merge.md | 40 |

Usage errors:

| template | count | runs |
| --- | --- | --- |
| chantier: error: unrecognized arguments: --lease <v> | 152 | 134 |
| chantier phase: error: argument phase: invalid choice: <v> (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>) | 77 | 77 |
| chantier handback: error: argument result: invalid choice: <v> (choose from <v>, <v>) | 8 | 8 |
| chantier ship: error: the following arguments are required: pr | 7 | 7 |
| chantier: error: unrecognized arguments: <v>...  | 5 | 4 |
| chantier: error: argument cmd: invalid choice: <v>, maybe you meant <v>? (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, | 2 | 2 |
| chantier: error: unrecognized arguments: --note | 2 | 2 |
| chantier agents: error: the following arguments are required: action, cr, agent | 1 | 1 |
| chantier phase: error: argument phase: invalid choice: <v>, maybe you meant <v>? (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>) | 1 | 1 |
| chantier: error: argument cmd: invalid choice: <v> (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, < | 1 | 1 |
| chantier: error: unrecognized arguments: --no-gate <v>...  | 1 | 1 |
| chantier: error: unrecognized arguments: --note <v>...  | 1 | 1 |
| chantier: error: unrecognized arguments: --note <v>... --once; <v>...  | 1 | 1 |
| chantier: error: unrecognized arguments: <v>... --conflict; <v>... --no-gate <v>...  | 1 | 1 |

Refusals:

| template | count | runs |
| --- | --- | --- |
| take CR-<n> --epoch <n>: the steering session's command; <n> is your number as Foreman of the batch (Foreman n°<n>) | 45 | 45 |
| CR-<n>: round limit <n> reached; hand back blocked, only the user grants more (`order rounds`) | 14 | 14 |
| claim lost: CR-<n>'s lease <n> ended at <n>:<n>; stop now: nothing recorded | 12 | 10 |
| handback CR-<n> needs --lease <n> (the number take printed) | 12 | 12 |
| ship CR-<n> needs --lease <n> (the number take printed) | 11 | 11 |
| handback <cr> ready <pr link, release link or tag> | 9 | 9 |
| CR-<n>: branch not based on CR-<n>'s head <sha>: rebase onto <path>, push, ship again; nothing recorded | 7 | 7 |
| could not apply <sha>... | 6 | 6 |
| refused: the worktree's head <sha> is not the head ship recorded (<sha>): ship CR-<n> <url> again, then the long gate and a verdict VERIFIED at the new head | 5 | 5 |
| recipe `scenario` failed on line <n> with exit code <n> | 4 | 4 |
| recipe `test` failed on line <n> with exit code <n> | 4 | 4 |
| round CR-<n> needs --lease <n> (the number take printed) | 4 | 4 |
| ship <cr> <pr link> | 4 | 4 |
| CR-<n>: round <n> was counted and nothing happened since (no note, the worktree unchanged): start that round's coder; to read the facts, `handoff CR-<n>`; if a  | 3 | 3 |
| CR-<n> is blocked: no Driver to run a round | 2 | 2 |
| CR-<n> is ready: no Driver holds it until the steering session takes it back (take CR-<n> --note <v>), then hand back again | 2 | 2 |
| batch batch-<n> is not a stack | 2 | 2 |
| claim lost: CR-<n> was taken again (lease <n>) at <n>:<n>; stop now: nothing recorded | 2 | 2 |
| failed to push some refs to '<url> | 2 | 2 |
| gate <cr> <name> [<name>...]: the long gate's names from chantier.yaml (long_gate.commands), one per argument | 2 | 2 |
| refused: no long gate passed at <sha> (gate CR-<n> <v>..., or --no-gate <v>) | 2 | 2 |
| Project directory `<v>` does not exist | 1 | 1 |
| lease: unexpected <v>; lease <unit> \| lease <unit> renew --lease <n> \| lease <unit> hold --lease <n> [--minutes N] (N from <n> to <n>, <n> by default) | 1 | 1 |
| not inside a git repository: <path> | 1 | 1 |
| phase: the detail is at most <n> characters | 1 | 1 |
| recipe `lint` failed on line <n> with exit code <n> | 1 | 1 |
| recipe `unit` failed on line <n> with exit code <n> | 1 | 1 |
| refused: no long gate passed at <sha> (gate CR-<n> <name>..., or --no-gate <v>) | 1 | 1 |
| refused: no long gate passed at <sha> (the pass at <sha> does not carry: the rebase changed the patch) (gate CR-<n> <v>..., or --no-gate <v>) | 1 | 1 |
| refused: no verdict VERIFIED at <sha> (the verdict VERIFIED at <sha> does not carry: the rebase changed the patch (own commits: <n> at <sha> above <sha>, <n> at | 1 | 1 |
| this is a planning surface with projects <names>: pass --project <name> | 1 | 1 |

## coder

| figure | value |
| --- | --- |
| runs | 536 |
| tool calls (total, mean per run, median) | 26740, 49.9, 32.5 |
| model calls (total, mean per run) | 22594, 42.2 |
| card bytes (total, mean per run) | 6538593, 12198.9 |
| files read per run (paths, cards) | 5.3, 1.9 |
| chantier calls | 392 |
| host denials | classifier 7, user_rejected 1 |
| write guard refusals | 323 |
| waits (count, share of tool calls) | 291, 1.1 % |
| tool not in the role's list | Monitor 14, TaskStop 10, bash 1 |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 29, 0 |
| help reads by command |  1, board 6, live 1, order 1, order add 1 |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| coder.md | 2482354 |
| references/ | 1900111 |
| driver.md | 615371 |
| chief-of-staff.md | 395330 |
| concepts.md | 192121 |
| session-start.md | 159450 |
| hosts/claude-code.md | 145471 |
| foreman.md | 140660 |
| startup-manifest.json | 139401 |
| hosts | 48633 |
| startup-core.md | 41415 |
| hosts/copilot.md | 36121 |
| SKILL.md:chantier | 34421 |
| SKILL.md:chief-of-staff | 33826 |
| session-start-chief-of-staff.md | 21210 |
| griller.md | 20991 |
| release-template.md | 19489 |
| pr-template.md | 18148 |
| verifier.md | 17871 |
| status-layout.md | 15615 |
| SKILL.md:status | 13538 |
| chief-of-staff-steering.md | 9180 |
| chief-of-staff | 8167 |
| driver-retake.md | 8076 |
| other-card | 4686 |
| driver | 3739 |
| routing.md | 3024 |
| SKILL.md:griller | 3007 |
| init.md | 2994 |
| inspector.md | 1278 |
| spec-writer.md | 1031 |
| driver-pr-extras.md | 669 |
| foreman-stack.md | 569 |
| spec-critic.md | 344 |
| role-core.md | 194 |
| chief-of-staff-merge.md | 88 |

Usage errors:

| template | count | runs |
| --- | --- | --- |
| chantier: error: unrecognized arguments: --lease <v> | 1 | 1 |

Refusals:

| template | count | runs |
| --- | --- | --- |
| Distribution `pyyaml==<n>.<n>.<n> @ registry+<url> can't be installed because it is marked as `--no-build` but has no binary distribution | 1 | 1 |
| Failed to spawn: chantier | 1 | 1 |
| Failed to spawn: ruff | 1 | 1 |
| recipe `lint` failed on line <n> with exit code <n> | 1 | 1 |
| recipe `test` failed on line <n> with exit code <n> | 1 | 1 |

## spec-writer

| figure | value |
| --- | --- |
| runs | 515 |
| tool calls (total, mean per run, median) | 18309, 35.6, 32 |
| model calls (total, mean per run) | 15300, 29.7 |
| card bytes (total, mean per run) | 11772577, 22859.4 |
| files read per run (paths, cards) | 6.3, 3.7 |
| chantier calls | 3089 |
| host denials | classifier 3 |
| write guard refusals | 5 |
| waits (count, share of tool calls) | 1, 0.0 % |
| tool not in the role's list | Edit 95 |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 3, 0 |
| help reads by command |  16, abandon 1, cost 6, file 8, run chantier 4, summary 130, summary lint 11, summary set 385 |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| references/ | 3201568 |
| concepts.md | 1742349 |
| spec-writer.md | 1402017 |
| driver.md | 1221233 |
| chief-of-staff.md | 1126278 |
| foreman.md | 700212 |
| hosts/claude-code.md | 683920 |
| startup-manifest.json | 399895 |
| session-start.md | 246887 |
| SKILL.md:chantier | 135961 |
| verifier.md | 92838 |
| hosts/copilot.md | 86434 |
| other-card | 84180 |
| startup-core.md | 82035 |
| griller.md | 60067 |
| SKILL.md:chief-of-staff | 59022 |
| hosts | 53661 |
| pr-template.md | 52458 |
| release-template.md | 40768 |
| coder.md | 33420 |
| routing.md | 29026 |
| inspector.md | 22536 |
| sync-checkout.md | 22396 |
| status-layout.md | 19784 |
| SKILL.md:griller | 18124 |
| foreman-stack.md | 16545 |
| session-start-chief-of-staff.md | 16446 |
| driver-refused.md | 16054 |
| chief-of-staff-batch-start.md | 15257 |
| release-driver.md | 13876 |
| foreman-conflict.md | 11358 |
| role-core.md | 11108 |
| foreman-refused.md | 8058 |
| init.md | 7483 |
| spec-critic.md | 7380 |
| release-driver-merged.md | 5864 |
| SKILL.md:status | 5558 |
| ticket-summary-example.md | 5023 |
| retro-critic.md | 4114 |
| foreman | 4035 |
| host-core-claude-code.md | 3055 |
| chief-of-staff-release.md | 1389 |
| release | 1058 |
| floor.md | 903 |
| host-core-copilot.md | 500 |
| startup-manifest | 232 |
| host-core- | 212 |

Usage errors:

| template | count | runs |
| --- | --- | --- |
| chantier: error: unrecognized arguments: <v> --no-sync <v> | 2 | 2 |
| chantier: error: argument cmd: invalid choice: <v> (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, < | 1 | 1 |
| chantier: error: unrecognized arguments: --title <v>... --summary <v>...  | 1 | 1 |

Refusals:

| template | count | runs |
| --- | --- | --- |
| not a CR folder: <path> | 275 | 261 |
| this is a planning surface with projects <names>: pass --project <name> | 71 | 71 |
| summary is <n> characters: the limit is <n> | 55 | 46 |
| CR folder must be inside the planning folder: <path> | 47 | 38 |
| unknown batch batch-<n> | 6 | 6 |
| no project folder <path> in a planning surface | 3 | 3 |
| CR folder must be inside the planning folder: . | 2 | 2 |
| summary set takes --title, --summary or --unchanged | 2 | 2 |
| title is <n> characters: the limit is <n> | 2 | 2 |
| the issue: line's tracker is not known from its URL: add --tracker github\|gitlab\|jira | 1 | 1 |

## spec-critic

| figure | value |
| --- | --- |
| runs | 241 |
| tool calls (total, mean per run, median) | 7008, 29.1, 27 |
| model calls (total, mean per run) | 5738, 23.8 |
| card bytes (total, mean per run) | 4979791, 20663.0 |
| files read per run (paths, cards) | 6.0, 3.8 |
| chantier calls | 46 |
| host denials | none |
| write guard refusals | 2 |
| waits (count, share of tool calls) | 1, 0.0 % |
| tool not in the role's list | none |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 0, 0 |
| help reads by command |  4, lease 1 |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| references/ | 1580475 |
| spec-critic.md | 796603 |
| driver.md | 527060 |
| chief-of-staff.md | 475237 |
| foreman.md | 370167 |
| hosts/claude-code.md | 307929 |
| concepts.md | 241381 |
| session-start.md | 129064 |
| startup-manifest.json | 126603 |
| startup-core.md | 97816 |
| SKILL.md:chief-of-staff | 80852 |
| SKILL.md:chantier | 46428 |
| hosts | 41843 |
| griller.md | 36512 |
| other-card | 25340 |
| verifier.md | 25246 |
| hosts/copilot.md | 18928 |
| status-layout.md | 15723 |
| release-template.md | 10386 |
| SKILL.md:griller | 6593 |
| host-core- | 4279 |
| coder.md | 3966 |
| role-core.md | 3862 |
| conflict-resolver.md | 3754 |
| pr-template.md | 2426 |
| routing.md | 1318 |

Refusals:

| template | count | runs |
| --- | --- | --- |
| this is a planning surface with projects <names>: pass --project <name> | 1 | 1 |

## conflict-resolver

| figure | value |
| --- | --- |
| runs | 109 |
| tool calls (total, mean per run, median) | 1841, 16.9, 13 |
| model calls (total, mean per run) | 1494, 13.7 |
| card bytes (total, mean per run) | 620471, 5692.4 |
| files read per run (paths, cards) | 2.1, 1.4 |
| chantier calls | 48 |
| host denials | none |
| write guard refusals | 39 |
| waits (count, share of tool calls) | 6, 0.3 % |
| tool not in the role's list | TaskStop 1 |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 3, 0 |
| help reads by command | none |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| conflict-resolver.md | 413304 |
| hosts/claude-code.md | 44001 |
| foreman.md | 36201 |
| chief-of-staff.md | 20455 |
| driver.md | 19023 |
| startup-core.md | 17274 |
| routing.md | 16840 |
| concepts.md | 15788 |
| hosts/copilot.md | 10000 |
| startup-manifest.json | 8669 |
| hosts | 7699 |
| session-start.md | 5406 |
| references/ | 3998 |
| foreman-stack.md | 1813 |

## stack-driver

| figure | value |
| --- | --- |
| runs | 81 |
| tool calls (total, mean per run, median) | 2763, 34.1, 31 |
| model calls (total, mean per run) | 2252, 27.8 |
| card bytes (total, mean per run) | 5260573, 64945.3 |
| files read per run (paths, cards) | 5.2, 4.6 |
| chantier calls | 993 |
| host denials | classifier 6 |
| write guard refusals | 0 |
| waits (count, share of tool calls) | 292, 10.6 % |
| tool not in the role's list | none |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 97, 2 |
| help reads by command |  1, forge-stack 13, forge-stack create 1, forge-stack rebuild 1, forge-stack unstack 1, gate 3, lease 3, ship 5, stack 5, take 1, verdict 2 |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| driver.md | 4180004 |
| startup-manifest.json | 370724 |
| references/ | 216780 |
| concepts.md | 198000 |
| startup-core.md | 148043 |
| verifier.md | 54735 |
| conflict-resolver.md | 52128 |
| inspector.md | 11232 |
| hosts/claude-code.md | 10653 |
| role-core.md | 8828 |
| host-core-claude-code.md | 6900 |
| chief-of-staff.md | 1930 |
| foreman-stack.md | 432 |
| SKILL.md:chief-of-staff | 184 |

Usage errors:

| template | count | runs |
| --- | --- | --- |
| chantier ship: error: the following arguments are required: pr | 4 | 4 |

Refusals:

| template | count | runs |
| --- | --- | --- |
| claim lost: CR-<n> was taken again (lease <n>) at <n>:<n>; stop now: nothing recorded | 6 | 5 |
| CR-<n>: <url> is on main and out of draft, but its head <sha> carries CR-<n> (<url> merging it would merge them too. First put the PR back to draft and ship aga | 3 | 3 |
| gh api -X POST <path> -F pull_requests[]=<n>: gh: Invalid request. | 3 | 3 |
| batch batch-<n> is not a stack | 2 | 1 |
| gh api -X POST <path> -F pull_requests[]=<n> -F pull_requests[]=<n> -F pull_requests[]=<n> -F pull_requests[]=<n> -F pull_requests[]=<n>: not JSON: | 2 | 2 |
| ship <cr> <pr link> | 2 | 2 |
| CR-<n> depends on CR-<n>, which is not named: it cannot sit below it | 1 | 1 |
| CR-<n> is ready: no Driver to record a step | 1 | 1 |
| CR-<n>: <url> is on main and out of draft, but its head <sha> carries CR-<n> (<url> | 1 | 1 |
| CR-<n>: CR-<n>'s branch moved since its last ship (<sha> -> <sha>): it ships first, then ship again; nothing recorded | 1 | 1 |
| CR-<n>: only a CR handed back ready leaves draft | 1 | 1 |
| CR-<n>: under it is a draft: CR-<n> | 1 | 1 |
| a stack driver is recorded (<sha>); one that ended: `agents set stack - --epoch <n>` first (a stack driver reads the stack with `stack`, which changes nothing) | 1 | 1 |
| could not apply <sha>... | 1 | 1 |
| gh api -X PATCH <path> -f base=main: gh: Validation Failed (HTTP <n>) (`forge-stack rebuild` replaces a stack) | 1 | 1 |
| lease: unexpected <v>; lease <unit> \| lease <unit> renew --lease <n> \| lease <unit> hold --lease <n> [--minutes N] (N from <n> to <n>, <n> by default) | 1 | 1 |
| ship CR-<n> needs --lease <n> (the number take printed) | 1 | 1 |
| take CR-<n> --epoch <n>: the steering session's command; <n> is your number as Foreman of the batch (Foreman n°<n>) | 1 | 1 |

## debugger

| figure | value |
| --- | --- |
| runs | 50 |
| tool calls (total, mean per run, median) | 1042, 20.8, 19.0 |
| model calls (total, mean per run) | 869, 17.4 |
| card bytes (total, mean per run) | 187012, 3740.2 |
| files read per run (paths, cards) | 2.7, 1.0 |
| chantier calls | 21 |
| host denials | none |
| write guard refusals | 7 |
| waits (count, share of tool calls) | 1, 0.1 % |
| tool not in the role's list | Edit 1 |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 1, 0 |
| help reads by command | none |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| debugger.md | 186434 |
| references/ | 578 |

Refusals:

| template | count | runs |
| --- | --- | --- |
| init: the surface's writer is not running: nothing written; for the Chief of Staff: start the watcher, which starts the surface server (the <v> line's command), | 1 | 1 |

## investigator

| figure | value |
| --- | --- |
| runs | 45 |
| tool calls (total, mean per run, median) | 1288, 28.6, 24 |
| model calls (total, mean per run) | 997, 22.2 |
| card bytes (total, mean per run) | 337750, 7505.6 |
| files read per run (paths, cards) | 4.9, 1.8 |
| chantier calls | 48 |
| host denials | none |
| write guard refusals | 5 |
| waits (count, share of tool calls) | 0, 0.0 % |
| tool not in the role's list | Edit 2 |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 0, 0 |
| help reads by command | none |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| investigator.md | 167545 |
| references/ | 87259 |
| startup-manifest.json | 20954 |
| driver.md | 16610 |
| chief-of-staff.md | 14425 |
| concepts.md | 11103 |
| foreman.md | 7771 |
| griller.md | 5713 |
| session-start.md | 4012 |
| startup-core.md | 2358 |

Usage errors:

| template | count | runs |
| --- | --- | --- |
| chantier: error: unrecognized arguments: --lease <v> | 2 | 2 |

## release-driver

| figure | value |
| --- | --- |
| runs | 31 |
| tool calls (total, mean per run, median) | 961, 31.0, 30 |
| model calls (total, mean per run) | 771, 24.9 |
| card bytes (total, mean per run) | 1194523, 38533.0 |
| files read per run (paths, cards) | 6.4, 3.4 |
| chantier calls | 224 |
| host denials | classifier 2 |
| write guard refusals | 0 |
| waits (count, share of tool calls) | 106, 11.0 % |
| tool not in the role's list | none |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 2, 0 |
| help reads by command | handback 2, lease 1, open 1, release 2, ship 2, take 1, watch 1 |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| driver.md | 903409 |
| startup-manifest.json | 109551 |
| references/ | 98271 |
| startup-core.md | 48691 |
| release-template.md | 15289 |
| session-start.md | 5436 |
| hosts/claude-code.md | 5109 |
| chief-of-staff.md | 4062 |
| role-core.md | 2110 |
| host-core-claude-code.md | 2005 |
| hosts | 590 |

Usage errors:

| template | count | runs |
| --- | --- | --- |
| chantier: error: unrecognized arguments: --lease <v> | 6 | 5 |
| chantier phase: error: argument phase: invalid choice: <v> (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>) | 1 | 1 |
| chantier ship: error: the following arguments are required: pr | 1 | 1 |

Refusals:

| template | count | runs |
| --- | --- | --- |
| CR-<n> is merged: no Driver to hand it back | 1 | 1 |
| no running batch: run `chantier open` first; no batch closed yet | 1 | 1 |
| refused: no long gate passed at <sha> (gate CR-<n> <v>..., or --no-gate <v>) | 1 | 1 |
| take CR-<n> --epoch <n>: the steering session's command; <n> is your number as Foreman of the batch (Foreman n°<n>) | 1 | 1 |

## retro-critic

| figure | value |
| --- | --- |
| runs | 25 |
| tool calls (total, mean per run, median) | 328, 13.1, 13 |
| model calls (total, mean per run) | 281, 11.2 |
| card bytes (total, mean per run) | 314984, 12599.4 |
| files read per run (paths, cards) | 2.2, 2.5 |
| chantier calls | 16 |
| host denials | none |
| write guard refusals | 0 |
| waits (count, share of tool calls) | 3, 0.9 % |
| tool not in the role's list | none |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 0, 0 |
| help reads by command |  1, status 1 |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| references/ | 133031 |
| driver.md | 66869 |
| retro-critic.md | 65885 |
| startup-manifest.json | 14514 |
| foreman.md | 11725 |
| hosts/claude-code.md | 11393 |
| chief-of-staff.md | 4773 |
| SKILL.md:chief-of-staff | 3061 |
| startup-core.md | 2358 |
| concepts.md | 951 |
| host-core-claude-code.md | 244 |
| role-core.md | 180 |

## griller

| figure | value |
| --- | --- |
| runs | 10 |
| tool calls (total, mean per run, median) | 833, 83.3, 72.5 |
| model calls (total, mean per run) | 810, 81.0 |
| card bytes (total, mean per run) | 630708, 63070.8 |
| files read per run (paths, cards) | 4.8, 5.0 |
| chantier calls | 134 |
| host denials | user_rejected 1 |
| write guard refusals | 0 |
| waits (count, share of tool calls) | 10, 1.2 % |
| tool not in the role's list | none |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 1, 0 |
| help reads by command |  1, file 4, summary 1, summary set 2, triage 3 |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| references/ | 266858 |
| chief-of-staff.md | 135574 |
| hosts/claude-code.md | 74995 |
| griller.md | 45758 |
| startup-manifest.json | 45583 |
| session-start.md | 30743 |
| concepts.md | 11458 |
| sync-checkout.md | 4840 |
| startup-core.md | 4204 |
| SKILL.md:griller | 4066 |
| host-core-claude-code.md | 3066 |
| titles.md | 2777 |
| session-start-griller.md | 592 |
| role-core.md | 194 |

Refusals:

| template | count | runs |
| --- | --- | --- |
| not a CR folder: <path> | 5 | 4 |
| cannot move CR folder <path> to <path> refused for <n> s, the folder is likely held; nothing moved. On Windows a folder cannot move while a process holds it: a  | 2 | 1 |
| cannot move CR folder <path> to <path> [WinError <n>] Accès refusé: <v> -> <v> | 1 | 1 |
| failed to remove file `<path>`: Le processus ne peut pas accéder au fichier car ce fichier est utilisé par un autre processus. (os error <n>) | 1 | 1 |
| title is <n> characters: the limit is <n> | 1 | 1 |
| triage expects a CR folder: <path>, <path> or <path>; got <path> | 1 | 1 |

## chief-of-staff

| figure | value |
| --- | --- |
| runs | 6 |
| tool calls (total, mean per run, median) | 10584, 1764.0, 1254.5 |
| model calls (total, mean per run) | 11925, 1987.5 |
| card bytes (total, mean per run) | 3017281, 502880.2 |
| files read per run (paths, cards) | 61.0, 14.2 |
| chantier calls | 1868 |
| host denials | classifier 10 |
| write guard refusals | 0 |
| waits (count, share of tool calls) | 371, 3.5 % |
| tool not in the role's list | none |
| `chantier push` (calls, refused, rate) | 0, 0, 0.0 % |
| `git push --force-with-lease` (calls, denied) | 59, 0 |
| help reads by command |  25, abandon 5, ask 1, asks 1, board 7, cancel 1, close 2, cost 1, file 36, foreman 2, handback 2, live 1, open 2, order 19, order add 2, order budget 1, order drop 1, order merged 2, order mode 1, order rounds 2, order waive 2, preflight 1, seat take 1, serve 2, stack 3, summary 4, summary set 2, sync 1, triage 19, webui 1 |
| help reads by topic | none |

Card bytes by card:

| card | bytes |
| --- | --- |
| chief-of-staff.md | 1256912 |
| references/ | 551680 |
| hosts/claude-code.md | 362998 |
| session-start.md | 251440 |
| foreman.md | 187439 |
| startup-manifest.json | 164480 |
| concepts.md | 61715 |
| griller.md | 56844 |
| startup-core.md | 35282 |
| hosts | 34095 |
| spec-writer.md | 19980 |
| release-template.md | 10208 |
| driver.md | 5780 |
| release | 5237 |
| retro-critic.md | 3399 |
| role-core.md | 2632 |
| SKILL.md:chief-of-staff | 2225 |
| routing.md | 1434 |
| host-core-claude-code.md | 1223 |
| SKILL.md:griller | 925 |
| session-start-chief-of-staff.md | 658 |
| other-card | 442 |
| spec-critic.md | 222 |
| brief | 31 |

Usage errors:

| template | count | runs |
| --- | --- | --- |
| chantier triage: error: one of the arguments --priority --ready --inbox is required | 2 | 2 |
| chantier: error: argument cmd: invalid choice: <v>, maybe you meant <v>? (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, | 2 | 2 |
| chantier triage: error: one of the arguments --priority --ready --inbox --running-batch is required | 1 | 1 |
| chantier: error: unrecognized arguments: --session | 1 | 1 |
| chantier: error: unrecognized arguments: <v> | 1 | 1 |
| chantier: error: unrecognized arguments: <v>...  | 1 | 1 |

Refusals:

| template | count | runs |
| --- | --- | --- |
| cannot move CR folder <path> to <path> [WinError <n>] Le processus ne peut pas accéder au fichier car ce fichier est utilisé par un autre processus: <v> -> <v> | 19 | 3 |
| no running batch: run `chantier open` first; last closed: batch-<n> | 17 | 5 |
| not a CR folder: <path> | 13 | 4 |
| cannot move CR folder <path> to <path> refused for <n> s, the folder is likely held; nothing moved. On Windows a folder cannot move while a process holds it: a  | 12 | 3 |
| title is <n> characters: the limit is <n> | 12 | 4 |
| no running batch; paused: batch-<n>: pass `--batch batch-<n>`; last closed: batch-<n> | 9 | 3 |
| failed to remove file `<path>`: Le processus ne peut pas accéder au fichier car ce fichier est utilisé par un autre processus. (os error <n>) | 5 | 3 |
| prepared CR not found: <path> | 5 | 2 |
| summary is <n> characters: the limit is <n> | 4 | 3 |
| unknown batch batch-<n> | 4 | 3 |
| cannot move CR folder <path> | 3 | 1 |
| missing Change Specification: <path>; grill the CR first | 3 | 2 |
| seat take <session-id> | 3 | 3 |
| triage expects a CR folder: <path>, <path> or <path>; got <path> | 3 | 1 |
| --title is required: this CR has no title yet | 1 | 1 |
| <slug> is not grilled: grill it first | 1 | 1 |
| <slug> is not in the backlog (inbox, P1…P4, <n>-ready) | 1 | 1 |
| CR folder must be inside the planning folder: . | 1 | 1 |
| CR-<n> is a release CR: it leaves the batch only to the trash (--note trash) | 1 | 1 |
| batch-<n> is not closed (a paused batch stays until `close`): `order add` joins new work to it | 1 | 1 |
| branch <v> not found | 1 | 1 |
| cannot change what CR-<n> waits for: it is ready, not queued; in a stack, its place and base are set by `stack` | 1 | 1 |
| cannot change what CR-<n> waits for: it is working, not queued; in a stack, its place and base are set by `stack` | 1 | 1 |
| cannot close batch-<n>, something still runs: transcript <id> still runs: its last record is a prompt with no answer yet (<path>). Nothing was deleted. an agent | 1 | 1 |
| failed to push some refs to '<url> | 1 | 1 |
| foreman set <session-id> --epoch <n> | 1 | 1 |
| no running batch: run `chantier open` first; no batch closed yet | 1 | 1 |
| only an inbox, backlog, <n>-ready or unclaimed batch CR can be abandoned | 1 | 1 |
| order add --release: CR-<n> is already the release CR of batch-<n>; a batch has one. Put the second release in the next batch, once this one is closed | 1 | 1 |
| order after: unknown CR <v> in batch batch-<n> | 1 | 1 |
| order approve names the batch's release CR (CR-<n>) | 1 | 1 |
| order budget --note <usd>: no value given: a positive amount in dollars | 1 | 1 |
| order merged: the surface's writer is not running: nothing written; for the Chief of Staff: start the watcher, which starts the surface server (the <v> line's c | 1 | 1 |
| order waive CR-<n>: --follow-up <backlog folder> names the CR that runs the long gate on main afterwards (file it first: `file`) | 1 | 1 |
| prepared CR not found: <path> <v> | 1 | 1 |
| src refspec v0.<n>.<n>-preflight-trial does not match any | 1 | 1 |
| the request has no short title (its title is <n> characters; the limit is <n>): give --title <v>, the text goes below it as its description, or start the text w | 1 | 1 |
| title is one line of plain text: no newline or other control character | 1 | 1 |
| triage: the surface's writer is not running: nothing written; for the Chief of Staff: start t | 1 | 1 |

## Driver runs per CR

256 CRs, 591 runs, 2.3 runs per CR; with one run 31.2 %, two 37.1 %, three or more 31.6 %

## Wake shares

| role | compaction | agent_ended | watcher | heartbeat | foreman_turn_ended | skill | typed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chief-of-staff | 2.6 % | 3.6 % | 0.1 % | 0.0 % | 15.0 % | 1.9 % | 76.8 % |

## Detectors

Rate of a role's runs with at least one matching call (runs matched).

| detector | verifier | inspector | cr-driver | coder | spec-writer | spec-critic | conflict-resolver | stack-driver | debugger | investigator | release-driver | retro-critic | griller | chief-of-staff |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| merge-by-agent | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.2 % (1) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | - |
| merge-not-ff | 0.1 % (1) | 0.0 % (0) | 0.0 % (0) | 0.4 % (2) | 0.6 % (3) | 0.0 % (0) | 0.9 % (1) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 33.3 % (2) |
| plain-force-push | 0.0 % (0) | 0.0 % (0) | 0.3 % (2) | 0.2 % (1) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) |
| discard-work | 2.2 % (16) | 0.0 % (0) | 1.3 % (8) | 3.2 % (17) | 0.0 % (0) | 0.0 % (0) | 7.3 % (8) | 2.5 % (2) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 33.3 % (2) |
| git-stash | 0.0 % (0) | 0.0 % (0) | 0.2 % (1) | 1.1 % (6) | 0.0 % (0) | 0.0 % (0) | 0.9 % (1) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 33.3 % (2) |
| stop-by-name | 0.0 % (0) | 0.0 % (0) | 0.5 % (3) | 1.5 % (8) | 0.0 % (0) | 0.0 % (0) | 0.9 % (1) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) |
| add-all | 2.9 % (21) | 0.0 % (0) | 8.5 % (51) | 0.2 % (1) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 1.2 % (1) | 2.0 % (1) | 0.0 % (0) | 3.2 % (1) | 0.0 % (0) | 20.0 % (2) | 50.0 % (3) |
| cd-into-changes | 58.1 % (418) | 27.4 % (186) | 46.1 % (278) | 37.9 % (203) | 58.3 % (300) | 51.0 % (123) | 14.7 % (16) | 27.2 % (22) | 54.0 % (27) | 22.2 % (10) | 16.1 % (5) | 76.0 % (19) | 100.0 % (10) | 83.3 % (5) |
| no-verify | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) | 0.0 % (0) |

## S-list

| role | kind | template | runs | rate |
| --- | --- | --- | --- | --- |
| chief-of-staff | refusal | --title is required: this CR has no title yet | 1 | 16.7 % |
| chief-of-staff | refusal | <slug> is not grilled: grill it first | 1 | 16.7 % |
| chief-of-staff | refusal | <slug> is not in the backlog (inbox, P1…P4, <n>-ready) | 1 | 16.7 % |
| chief-of-staff | refusal | CR folder must be inside the planning folder: . | 1 | 16.7 % |
| chief-of-staff | refusal | CR-<n> is a release CR: it leaves the batch only to the trash (--note trash) | 1 | 16.7 % |
| chief-of-staff | refusal | batch-<n> is not closed (a paused batch stays until `close`): `order add` joins new work to it | 1 | 16.7 % |
| chief-of-staff | refusal | branch <v> not found | 1 | 16.7 % |
| chief-of-staff | refusal | cannot change what CR-<n> waits for: it is ready, not queued; in a stack, its place and base are set by `stack` | 1 | 16.7 % |
| chief-of-staff | refusal | cannot change what CR-<n> waits for: it is working, not queued; in a stack, its place and base are set by `stack` | 1 | 16.7 % |
| chief-of-staff | refusal | cannot close batch-<n>, something still runs: transcript <id> still runs: its last record is a prompt with no answer yet (<path>). Nothing was deleted. an agent | 1 | 16.7 % |
| chief-of-staff | refusal | cannot move CR folder <path> | 1 | 16.7 % |
| chief-of-staff | refusal | cannot move CR folder <path> to <path> [WinError <n>] Le processus ne peut pas accéder au fichier car ce fichier est utilisé par un autre processus: <v> -> <v> | 3 | 50.0 % |
| chief-of-staff | refusal | cannot move CR folder <path> to <path> refused for <n> s, the folder is likely held; nothing moved. On Windows a folder cannot move while a process holds it: a  | 3 | 50.0 % |
| chief-of-staff | refusal | failed to push some refs to '<url> | 1 | 16.7 % |
| chief-of-staff | refusal | failed to remove file `<path>`: Le processus ne peut pas accéder au fichier car ce fichier est utilisé par un autre processus. (os error <n>) | 3 | 50.0 % |
| chief-of-staff | refusal | foreman set <session-id> --epoch <n> | 1 | 16.7 % |
| chief-of-staff | refusal | missing Change Specification: <path>; grill the CR first | 2 | 33.3 % |
| chief-of-staff | refusal | no running batch: run `chantier open` first; last closed: batch-<n> | 5 | 83.3 % |
| chief-of-staff | refusal | no running batch: run `chantier open` first; no batch closed yet | 1 | 16.7 % |
| chief-of-staff | refusal | no running batch; paused: batch-<n>: pass `--batch batch-<n>`; last closed: batch-<n> | 3 | 50.0 % |
| chief-of-staff | refusal | not a CR folder: <path> | 4 | 66.7 % |
| chief-of-staff | refusal | only an inbox, backlog, <n>-ready or unclaimed batch CR can be abandoned | 1 | 16.7 % |
| chief-of-staff | refusal | order add --release: CR-<n> is already the release CR of batch-<n>; a batch has one. Put the second release in the next batch, once this one is closed | 1 | 16.7 % |
| chief-of-staff | refusal | order after: unknown CR <v> in batch batch-<n> | 1 | 16.7 % |
| chief-of-staff | refusal | order approve names the batch's release CR (CR-<n>) | 1 | 16.7 % |
| chief-of-staff | refusal | order budget --note <usd>: no value given: a positive amount in dollars | 1 | 16.7 % |
| chief-of-staff | refusal | order merged: the surface's writer is not running: nothing written; for the Chief of Staff: start the watcher, which starts the surface server (the <v> line's c | 1 | 16.7 % |
| chief-of-staff | refusal | order waive CR-<n>: --follow-up <backlog folder> names the CR that runs the long gate on main afterwards (file it first: `file`) | 1 | 16.7 % |
| chief-of-staff | refusal | prepared CR not found: <path> | 2 | 33.3 % |
| chief-of-staff | refusal | prepared CR not found: <path> <v> | 1 | 16.7 % |
| chief-of-staff | refusal | seat take <session-id> | 3 | 50.0 % |
| chief-of-staff | refusal | src refspec v0.<n>.<n>-preflight-trial does not match any | 1 | 16.7 % |
| chief-of-staff | refusal | summary is <n> characters: the limit is <n> | 3 | 50.0 % |
| chief-of-staff | refusal | the request has no short title (its title is <n> characters; the limit is <n>): give --title <v>, the text goes below it as its description, or start the text w | 1 | 16.7 % |
| chief-of-staff | refusal | title is <n> characters: the limit is <n> | 4 | 66.7 % |
| chief-of-staff | refusal | title is one line of plain text: no newline or other control character | 1 | 16.7 % |
| chief-of-staff | refusal | triage expects a CR folder: <path>, <path> or <path>; got <path> | 1 | 16.7 % |
| chief-of-staff | refusal | triage: the surface's writer is not running: nothing written; for the Chief of Staff: start t | 1 | 16.7 % |
| chief-of-staff | refusal | unknown batch batch-<n> | 3 | 50.0 % |
| chief-of-staff | usage_error | chantier triage: error: one of the arguments --priority --ready --inbox --running-batch is required | 1 | 16.7 % |
| chief-of-staff | usage_error | chantier triage: error: one of the arguments --priority --ready --inbox is required | 2 | 33.3 % |
| chief-of-staff | usage_error | chantier: error: argument cmd: invalid choice: <v>, maybe you meant <v>? (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, | 2 | 33.3 % |
| chief-of-staff | usage_error | chantier: error: unrecognized arguments: --session | 1 | 16.7 % |
| chief-of-staff | usage_error | chantier: error: unrecognized arguments: <v> | 1 | 16.7 % |
| chief-of-staff | usage_error | chantier: error: unrecognized arguments: <v>...  | 1 | 16.7 % |
| cr-driver | refusal | CR-<n>: round limit <n> reached; hand back blocked, only the user grants more (`order rounds`) | 14 | 2.3 % |
| cr-driver | refusal | take CR-<n> --epoch <n>: the steering session's command; <n> is your number as Foreman of the batch (Foreman n°<n>) | 45 | 7.5 % |
| cr-driver | usage_error | chantier phase: error: argument phase: invalid choice: <v> (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>) | 77 | 12.8 % |
| cr-driver | usage_error | chantier: error: unrecognized arguments: --lease <v> | 134 | 22.2 % |
| griller | refusal | cannot move CR folder <path> to <path> [WinError <n>] Accès refusé: <v> -> <v> | 1 | 10.0 % |
| griller | refusal | cannot move CR folder <path> to <path> refused for <n> s, the folder is likely held; nothing moved. On Windows a folder cannot move while a process holds it: a  | 1 | 10.0 % |
| griller | refusal | failed to remove file `<path>`: Le processus ne peut pas accéder au fichier car ce fichier est utilisé par un autre processus. (os error <n>) | 1 | 10.0 % |
| griller | refusal | not a CR folder: <path> | 4 | 40.0 % |
| griller | refusal | title is <n> characters: the limit is <n> | 1 | 10.0 % |
| griller | refusal | triage expects a CR folder: <path>, <path> or <path>; got <path> | 1 | 10.0 % |
| investigator | usage_error | chantier: error: unrecognized arguments: --lease <v> | 2 | 4.4 % |
| release-driver | refusal | CR-<n> is merged: no Driver to hand it back | 1 | 3.2 % |
| release-driver | refusal | no running batch: run `chantier open` first; no batch closed yet | 1 | 3.2 % |
| release-driver | refusal | refused: no long gate passed at <sha> (gate CR-<n> <v>..., or --no-gate <v>) | 1 | 3.2 % |
| release-driver | refusal | take CR-<n> --epoch <n>: the steering session's command; <n> is your number as Foreman of the batch (Foreman n°<n>) | 1 | 3.2 % |
| release-driver | usage_error | chantier phase: error: argument phase: invalid choice: <v> (choose from <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>, <v>) | 1 | 3.2 % |
| release-driver | usage_error | chantier ship: error: the following arguments are required: pr | 1 | 3.2 % |
| release-driver | usage_error | chantier: error: unrecognized arguments: --lease <v> | 5 | 16.1 % |
| spec-writer | refusal | CR folder must be inside the planning folder: <path> | 38 | 7.4 % |
| spec-writer | refusal | not a CR folder: <path> | 261 | 50.7 % |
| spec-writer | refusal | summary is <n> characters: the limit is <n> | 46 | 8.9 % |
| spec-writer | refusal | this is a planning surface with projects <names>: pass --project <name> | 71 | 13.8 % |
| stack-driver | refusal | CR-<n>: <url> is on main and out of draft, but its head <sha> carries CR-<n> (<url> merging it would merge them too. First put the PR back to draft and ship aga | 3 | 3.7 % |
| stack-driver | refusal | claim lost: CR-<n> was taken again (lease <n>) at <n>:<n>; stop now: nothing recorded | 5 | 6.2 % |
| stack-driver | refusal | gh api -X POST <path> -F pull_requests[]=<n> -F pull_requests[]=<n> -F pull_requests[]=<n> -F pull_requests[]=<n> -F pull_requests[]=<n>: not JSON: | 2 | 2.5 % |
| stack-driver | refusal | gh api -X POST <path> -F pull_requests[]=<n>: gh: Invalid request. | 3 | 3.7 % |
| stack-driver | refusal | ship <cr> <pr link> | 2 | 2.5 % |
| stack-driver | usage_error | chantier ship: error: the following arguments are required: pr | 4 | 4.9 % |
| verifier | usage_error | chantier: error: unrecognized arguments: --lease <v> | 19 | 2.6 % |

## Regressions

no earlier measure

Copilot: not measured (no transcript reader)
