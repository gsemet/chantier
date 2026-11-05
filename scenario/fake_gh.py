"""A fake `gh` for the scenario: the scripted Driver opens PRs with it, the scripted Foreman
merges what the user allowed. Answers from $FAKE_GH_STATE; each call is logged next to it."""
import json
import os
import sys

state_path = os.environ["FAKE_GH_STATE"]
state = json.load(open(state_path))
args = sys.argv[1:]
with open(state_path + ".calls", "a") as f:
    f.write(json.dumps(args) + "\n")

if args[:2] == ["pr", "create"]:
    n = state["next_pr"]
    state["next_pr"] = n + 1
    json.dump(state, open(state_path, "w"))
    print("Creating pull request…")
    print(f"https://github.com/acme/demo/pull/{n}")
elif args[:2] == ["pr", "merge"]:
    if state.get("merge_refused"):
        print("fake gh: not allowed to merge", file=sys.stderr)
        sys.exit(1)
    print(f"merged {args[2]}")
else:
    print(f"fake gh: unsupported {args}", file=sys.stderr)
    sys.exit(1)
