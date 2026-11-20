"""A fake `gh` for the scenario: the scripted Driver opens PRs with it, the scripted Foreman
merges what the user allowed. Answers from $FAKE_GH_STATE; each call is logged next to it."""
import json
import os
import re
import sys

state_path = os.environ["FAKE_GH_STATE"]
state = json.load(open(state_path))
args = sys.argv[1:]
with open(state_path + ".calls", "a") as f:
    f.write(json.dumps(args) + "\n")

if args[:2] == ["extension", "list"]:
    # `extensions` holds `name\towner/repo\tversion` lines (default: none installed)
    for line in state.get("extensions", []):
        print(line)
elif args[:2] == ["pr", "create"]:
    n = state["next_pr"]
    state["next_pr"] = n + 1
    if "--base" in args:  # the PR's base on the forge, as `pr create --base` set it
        state.setdefault("bases", {})[str(n)] = args[args.index("--base") + 1]
    json.dump(state, open(state_path, "w"))
    print("Creating pull request…")
    print(f"https://github.com/acme/demo/pull/{n}")
elif args[:2] == ["pr", "merge"]:
    if state.get("merge_refused"):
        print("fake gh: not allowed to merge", file=sys.stderr)
        sys.exit(1)
    print(f"merged {args[2]}")
elif args[:2] == ["api", "graphql"]:
    # the board's PRs page: one query for many PRs (aliases `p<N>`). `prs` holds, by number, the
    # fields to change from the default (open, not a draft, mergeable, into main, checks green,
    # head abc1234def5678, no `reviewDecision`: GitHub's APPROVED, CHANGES_REQUESTED, REVIEW_REQUIRED)
    query = next(a.split("=", 1)[1] for a in args if a.startswith("query="))
    asked = [int(n) for n in re.findall(r"\bp(\d+): pullRequest", query)]
    held = state.get("prs", {})

    def node(number):
        f = {"state": "OPEN", "isDraft": False, "mergeable": "MERGEABLE", "baseRefName": "main",
             "mergedAt": None, "closedAt": None, "checks": "SUCCESS",
             "headRefOid": "abc1234def5678", **held.get(str(number), {})}
        rollup = ({"state": f["checks"], "contexts": {"totalCount": 1}} if f["checks"] else None)
        return {"state": f["state"], "isDraft": f["isDraft"], "mergeable": f["mergeable"],
                "baseRefName": f["baseRefName"], "mergedAt": f["mergedAt"],
                "closedAt": f["closedAt"], "headRefOid": f["headRefOid"],
                "reviewDecision": f.get("reviewDecision"),
                "commits": {"nodes": [{"commit": {"statusCheckRollup": rollup}}]}}
    repo = {f"p{n}": node(n) for n in asked}
    repo["wf"] = {"entries": [{"name": "ci.yml"}]} if state.get("workflows", True) else None
    print(json.dumps({"data": {"repository": repo}}))
elif args[:1] == ["api"] and any(re.fullmatch(r"repos/[^/]+/[^/]+/pulls/\d+", a) for a in args):

    # a PR's base: read (GET) and changed (PATCH, `-f base=<branch>`); the forge refuses the
    # change while the PR is in an open stack. `bases` holds the changed ones (default: main)
    path = next(a for a in args if re.fullmatch(r"repos/[^/]+/[^/]+/pulls/\d+", a))
    number = int(path.rsplit("/", 1)[1])
    bases = state.setdefault("bases", {})
    if "PATCH" not in args and state.get("pull_read_refused"):  # a read the forge refuses
        print("fake gh: HTTP 403: cannot read the pull request", file=sys.stderr)
        sys.exit(1)
    if "PATCH" in args:
        new = next(a.split("=", 1)[1] for a in args if a.startswith("base="))
        if any(s["open"] and number in s["pull_requests"] for s in state.get("stacks", [])):
            print("fake gh: HTTP 422: the base of a pull request in a stack cannot change",
                  file=sys.stderr)
            sys.exit(1)
        if state.get("patch_refused"):
            print("fake gh: HTTP 403: cannot edit the pull request", file=sys.stderr)
            sys.exit(1)
        bases[str(number)] = new
        json.dump(state, open(state_path, "w"))
    # `drafts` names the PRs the forge holds as drafts (a PR is out of draft unless listed)
    print(json.dumps({"number": number, "base": {"ref": bases.get(str(number), "main")},
                      "draft": number in state.get("drafts", [])}))
elif args[:1] == ["api"] and any(re.fullmatch(r"repos/[^/]+/[^/]+/stacks/\d+/unstack", a) for a in args):
    path = next(a for a in args if a.endswith("/unstack"))
    found = [s for s in state.setdefault("stacks", []) if s["number"] == int(path.split("/")[-2])]
    if not found:
        print("fake gh: HTTP 404: Not Found", file=sys.stderr)
        sys.exit(1)
    if state.get("unstack_ignored"):  # answers 200 and leaves the stack open
        print(json.dumps(found[0]))
        sys.exit(0)
    gone = {int(a.split("=", 1)[1]) for a in args if a.startswith("pull_requests[]=")}
    found[0]["pull_requests"] = [n for n in found[0]["pull_requests"] if n not in gone]
    if not found[0]["pull_requests"]:
        found[0]["open"] = False  # dissolved when none is left
    json.dump(state, open(state_path, "w"))
    if state.get("unstack_empty"):  # dissolves the stack and answers 2xx with an empty body
        sys.exit(0)
    print(json.dumps(found[0]))
elif args[:1] == ["api"] and any(re.fullmatch(r"repos/[^/]+/[^/]+/stacks(/\d+)?", a) for a in args):
    # the stacks endpoint: create (POST, pull_requests[] bottom to top), list and read; the stacks
    # live in the state file, `drafts` names the PRs the forge holds as drafts
    path = next(a for a in args if re.fullmatch(r"repos/[^/]+/[^/]+/stacks(/\d+)?", a))
    stacks = state.setdefault("stacks", [])
    drafts = set(state.get("drafts", []))

    def shown(s):
        return {**s, "pull_requests": [{"number": n, "state": "open", "draft": n in drafts}
                                       for n in s["pull_requests"]]}
    if "POST" in args:
        numbers = [int(a.split("=", 1)[1]) for a in args if a.startswith("pull_requests[]=")]
        taken = [n for s in stacks if s["open"] for n in s["pull_requests"] if n in numbers]
        heads = state.get("heads", {})  # PR number -> its head branch, when the world names them
        bases = state.get("bases", {})
        broken = any(
            str(n) in heads
            and (i == 0 or str(numbers[i - 1]) in heads)
            and bases.get(str(n), "main") != (heads.get(str(numbers[i - 1])) if i else "main")
            for i, n in enumerate(numbers)
        )
        if broken:  # as GitHub did: a PR's base must be the previous PR's head
            print("fake gh: HTTP 422: Pull requests must form a stack, where each PR's base ref is "
                  "the previous PR's head ref", file=sys.stderr)
            sys.exit(1)
        if state.get("stack_refused") or taken:
            print("fake gh: HTTP 422: pull request already in a stack" if taken
                  else "fake gh: HTTP 403: stacks are not allowed", file=sys.stderr)
            sys.exit(1)
        n = state.get("next_stack", 100)
        state["next_stack"] = n + 1
        stacks.append({"number": n, "open": True, "pull_requests": numbers})
        json.dump(state, open(state_path, "w"))
        if state.get("create_unreadable"):  # creates the stack, answers a reply that is no JSON
            print("<html>")
            sys.exit(0)
        print(json.dumps(shown(stacks[-1])))
    elif path.endswith("/stacks"):
        print(json.dumps([shown(s) for s in stacks]))
    else:
        found = [s for s in stacks if s["number"] == int(path.rsplit("/", 1)[1])]
        if not found:
            print("fake gh: HTTP 404: Not Found", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(shown(found[0])))
else:
    print(f"fake gh: unsupported {args}", file=sys.stderr)
    sys.exit(1)
