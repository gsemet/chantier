"""A fake `glab` for the scenario: the GitLab API calls the scripted Driver (open) and the
scripted Foreman (merge) make, and the chain `forge-stack` reads and retargets, answered from the
same $FAKE_GH_STATE as the fake `gh`. `mrs` maps an iid to `state`, `draft`, `source_branch`,
`target_branch`, `web_url` (the documented merge request fields)."""

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
if args[:1] == ["api"] and "graphql" in args:
    # the hub's read of the merge requests it awaits (aliases `m<N>`). `prs` holds, by iid, the
    # fields to change from the default (opened, not a draft, no conflict, into main, head
    # abc1234def5678, pipeline SUCCESS), in GitLab's GraphQL words
    query = next(a.split("=", 1)[1] for a in args if a.startswith("query="))
    held = state.get("prs", {})
    project = {}
    for n in re.findall(r"\bm(\d+): mergeRequest", query):
        project[f"m{n}"] = {
            "state": "opened", "draft": False, "conflicts": False,
            "detailedMergeStatus": "MERGEABLE", "targetBranch": "main",
            "diffHeadSha": "abc1234def5678", "mergedAt": None, "closedAt": None,
            "createdAt": None, "updatedAt": None, "headPipeline": {"status": "SUCCESS"},
            **held.get(n, {}),
        }
    print(json.dumps({"data": {"project": project}}))
    sys.exit(0)
if not path.startswith("projects/"):
    print(f"fake glab: unsupported {args}", file=sys.stderr)
    sys.exit(1)
path = path.split("/", 2)[2]
mrs = state.setdefault("mrs", {})


def shown(iid):
    return {"iid": int(iid), "sha": "0" * 40, "detailed_merge_status": "mergeable", **mrs[iid]}


fields = dict(a.split("=", 1) for i, a in enumerate(args) if i and args[i - 1] == "-f")
one = re.fullmatch(r"merge_requests/(\d+)", path)
if path == "merge_requests" and method == "POST":
    n = state["next_pr"]
    state["next_pr"] = n + 1
    raw = dict(a.split("=", 1) for i, a in enumerate(args) if i and args[i - 1] == "--raw-field")
    mrs[str(n)] = {"state": "opened", "draft": False, "source_branch": raw.get("source_branch", ""),
                   "target_branch": raw.get("target_branch", "main"), "web_url": f"{URL}/-/merge_requests/{n}"}
    json.dump(state, open(state_path, "w"))
    print(json.dumps({"iid": n, "web_url": f"{URL}/-/merge_requests/{n}"}))
elif re.fullmatch(r"merge_requests/\d+/merge", path) and method == "PUT":
    if state.get("merge_refused"):
        print("fake glab: not allowed to merge", file=sys.stderr)
        sys.exit(1)
    print("{}")
elif path == "merge_requests" and method == "GET":
    target = fields.get("target_branch", "")
    rows = [
        shown(i)
        for i in mrs
        if mrs[i]["state"] == "opened" and (not target or mrs[i]["target_branch"] == target)
    ]
    print(json.dumps(rows if fields.get("page", "1") == "1" else []))
elif one and method == "GET" and state.get("pull_read_refused"):  # a read the forge refuses
    print("fake glab: 403 Forbidden: cannot read the merge request", file=sys.stderr)
    sys.exit(1)
elif one and one.group(1) in mrs and method == "GET":
    print(json.dumps(shown(one.group(1))))
elif one and one.group(1) in mrs and method == "PUT":
    refused = state.get("retarget_refused")
    if refused is True or (refused and int(one.group(1)) in refused):
        print("fake glab: 403 Forbidden: cannot change the target branch", file=sys.stderr)
        sys.exit(1)
    mrs[one.group(1)]["target_branch"] = fields["target_branch"]
    json.dump(state, open(state_path, "w"))
    print(json.dumps(shown(one.group(1))))
else:
    print(f"fake glab: unsupported {args}", file=sys.stderr)
    sys.exit(1)
