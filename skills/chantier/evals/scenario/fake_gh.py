"""A fake `gh` for the tests: answers from $FAKE_GH_STATE and logs each call next to it."""
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
elif args[:2] == ["pr", "edit"]:
    print(args[2])
elif args[:2] == ["pr", "checks"]:
    seq = state.get("checks_seq")
    if seq:  # successive answers, the last one repeats
        checks = seq.pop(0) if len(seq) > 1 else seq[0]
        json.dump(state, open(state_path, "w"))
    else:
        checks = state["checks"]
    print(json.dumps(checks))
elif args[:2] == ["run", "list"]:
    print(json.dumps(state["runs"]))
elif args[:2] == ["run", "view"]:
    print(state.get("log", ""))
else:
    print(f"fake gh: unsupported {args}", file=sys.stderr)
    sys.exit(1)
