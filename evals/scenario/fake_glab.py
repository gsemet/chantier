"""A fake `glab` for the tests: the GitLab API calls chantier makes, answered from the same
$FAKE_GH_STATE as the fake `gh` (checks become the jobs of the merge request's pipeline)."""
import json
import os
import re
import sys

state_path = os.environ["FAKE_GH_STATE"]
state = json.load(open(state_path))
args = sys.argv[1:]
with open(state_path + ".calls", "a") as f:
    f.write(json.dumps(args) + "\n")

STATUS = {"pass": "success", "fail": "failed", "pending": "running", "cancel": "canceled",
          "skipping": "skipped"}
URL = "https://gitlab.example.com/acme/demo"


def jobs(checks):
    return [{"name": c["name"], "status": STATUS[c["bucket"]], "allow_failure": False,
             "web_url": f"{URL}/-/jobs/{i}"} for i, c in enumerate(checks, 77)]


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
elif re.fullmatch(r"merge_requests/\d+", path) and method == "PUT":
    print("{}")
elif re.fullmatch(r"merge_requests/\d+", path):
    seq = state.get("checks_seq")
    if seq:  # successive answers, the last one repeats; one per poll
        state["current"] = seq.pop(0) if len(seq) > 1 else seq[0]
    else:
        state["current"] = state["checks"]
    json.dump(state, open(state_path, "w"))
    pipeline = {"id": 1, "sha": "head"} if state["current"] else None
    print(json.dumps({"sha": "head", "head_pipeline": pipeline}))
elif path == "pipelines/1/jobs":
    print(json.dumps(jobs(state["current"])))
elif path == "pipelines":
    failed = [{"name": r["name"], "bucket": "fail"} for r in state["runs"]
              if r.get("conclusion") == "failure"]
    print(json.dumps([{"id": 2, "status": "failed"}] if failed else []))
    state["main_failed"] = failed
    json.dump(state, open(state_path, "w"))
elif path == "pipelines/2/jobs":
    print(json.dumps(jobs(state["main_failed"])))
elif re.fullmatch(r"jobs/\d+/trace", path):
    print(state.get("log", ""))
else:
    print(f"fake glab: unsupported {args}", file=sys.stderr)
    sys.exit(1)
