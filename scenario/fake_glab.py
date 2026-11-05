"""A fake `glab` for the scenario: the GitLab API calls the scripted Driver (open) and the
scripted Foreman (merge) make, answered from the same $FAKE_GH_STATE as the fake `gh`."""
import json
import os
import re
import sys

state_path = os.environ["FAKE_GH_STATE"]
state = json.load(open(state_path))
args = sys.argv[1:]
with open(state_path + ".calls", "a") as f:
    f.write(json.dumps(args) + "\n")

URL = "https://gitlab.example.com/acme/demo"
method = args[args.index("--method") + 1] if "--method" in args else "GET"
path = args[1] if args[:1] == ["api"] else ""
if not path.startswith("projects/"):
    print(f"fake glab: unsupported {args}", file=sys.stderr)
    sys.exit(1)
path = path.split("/", 2)[2]
if path == "merge_requests" and method == "POST":
    n = state["next_pr"]
    state["next_pr"] = n + 1
    json.dump(state, open(state_path, "w"))
    print(json.dumps({"iid": n, "web_url": f"{URL}/-/merge_requests/{n}"}))
elif re.fullmatch(r"merge_requests/\d+/merge", path) and method == "PUT":
    if state.get("merge_refused"):
        print("fake glab: not allowed to merge", file=sys.stderr)
        sys.exit(1)
    print("{}")
else:
    print(f"fake glab: unsupported {args}", file=sys.stderr)
    sys.exit(1)
