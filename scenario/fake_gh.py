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
elif args[:1] == ["api"] and any(re.fullmatch(r"repos/[^/]+/[^/]+/pulls/\d+", a) for a in args):
    # a PR's base: read (GET) and changed (PATCH, `-f base=<branch>`); the forge refuses the
    # change while the PR is in an open stack. `bases` holds the changed ones (default: main)
    path = next(a for a in args if re.fullmatch(r"repos/[^/]+/[^/]+/pulls/\d+", a))
    number = int(path.rsplit("/", 1)[1])
    bases = state.setdefault("bases", {})
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
    print(json.dumps({"number": number, "base": {"ref": bases.get(str(number), "main")}}))
elif args[:1] == ["api"] and any(re.fullmatch(r"repos/[^/]+/[^/]+/stacks/\d+/unstack", a) for a in args):
    path = next(a for a in args if a.endswith("/unstack"))
    found = [s for s in state.setdefault("stacks", []) if s["number"] == int(path.split("/")[-2])]
    if not found:
        print("fake gh: HTTP 404: Not Found", file=sys.stderr)
        sys.exit(1)
    gone = {int(a.split("=", 1)[1]) for a in args if a.startswith("pull_requests[]=")}
    found[0]["pull_requests"] = [n for n in found[0]["pull_requests"] if n not in gone]
    if not found[0]["pull_requests"]:
        found[0]["open"] = False  # dissolved when none is left
    json.dump(state, open(state_path, "w"))
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
        if state.get("stack_refused") or taken:
            print("fake gh: HTTP 422: pull request already in a stack" if taken
                  else "fake gh: HTTP 403: stacks are not allowed", file=sys.stderr)
            sys.exit(1)
        n = state.get("next_stack", 100)
        state["next_stack"] = n + 1
        stacks.append({"number": n, "open": True, "pull_requests": numbers})
        json.dump(state, open(state_path, "w"))
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
