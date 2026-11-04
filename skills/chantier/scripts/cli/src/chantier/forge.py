"""The forge, through its own CLI: GitHub with `gh`, GitLab with `glab`, wherever they are hosted.

The forge and the project come from the batch's git remote. Its host is github.com or gitlab.com,
or a server of your own that `gh` (GitHub Enterprise) or `glab` (self-managed GitLab) is logged in
to: their own config, nothing here. Every call names that host and project, so neither CLI has to
guess among several remotes. GitLab goes through `glab api`, whose JSON does not change between
glab versions.

`CHANTIER_GH` or `CHANTIER_GLAB` names a fake executable (tests and simulations); it also picks
the forge.
"""
from __future__ import annotations

import functools
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

from .state import ChantierError, EXIT_EXTERNAL, git

CLI = {"github": "gh", "gitlab": "glab"}
FAKE = {"github": "CHANTIER_GH", "gitlab": "CHANTIER_GLAB"}
PUBLIC = {"github.com": "github", "gitlab.com": "gitlab"}
INFRA_HINTS = ("runner", "timed out", "timeout", "network", "econnreset", "rate limit",
               "no space left", "cancelled", "service unavailable", "502", "503")
# GitLab job statuses as `gh pr checks` buckets; any other status is still running.
BUCKETS = {"success": "pass", "failed": "fail", "canceled": "cancel", "skipped": "skipping",
           "manual": "skipping"}


@dataclass(frozen=True)
class Forge:
    kind: str
    host: str | None  # None: a fake forge on a local remote
    project: str | None
    exe: str


def remote_project(url: str) -> tuple[str, str] | None:
    """(host, project path) of a remote URL, in any of Git's forms; None for a local path."""
    if "://" in url:
        u = urlsplit(url)
        if u.scheme == "file" or not u.hostname:
            return None
        host, path = u.hostname, u.path
    else:  # scp-like: [user@]host:group/project; a one-letter host is a Windows drive
        m = re.fullmatch(r"(?:[^@/\\]+@)?([^/:\\]{2,}):(.+)", url)
        if not m:
            return None
        host, path = m[1], m[2]
    path = path.strip("/").removesuffix(".git").strip("/")
    return (host.lower(), path) if path else None


def _env() -> dict:
    return {**os.environ, "GH_PAGER": "cat", "GH_PROMPT_DISABLED": "1", "NO_PROMPT": "1",
            "NO_COLOR": "1"}


def _logged_in(kind: str, host: str) -> bool:
    if not shutil.which(CLI[kind]):
        return False
    try:
        p = subprocess.run([CLI[kind], "auth", "status", "--hostname", host], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=_env(), timeout=60)
    except subprocess.TimeoutExpired:
        return False
    return p.returncode == 0


@functools.lru_cache(maxsize=None)
def detect(cwd: str, remote: str) -> Forge:
    fakes = [kind for kind, var in FAKE.items() if os.environ.get(var)]
    if len(fakes) > 1:
        raise ChantierError("CHANTIER_GH and CHANTIER_GLAB are both set", EXIT_EXTERNAL)
    url = git("remote", "get-url", remote, cwd=cwd)
    where = remote_project(url)
    if fakes:
        return Forge(fakes[0], *(where or (None, None)), os.environ[FAKE[fakes[0]]])
    if where is None:
        raise ChantierError(f"remote {remote!r} is not on a forge: {url}", EXIT_EXTERNAL)
    host, project = where
    kinds = [PUBLIC[host]] if host in PUBLIC else [k for k in CLI if _logged_in(k, host)]
    if len(kinds) > 1:
        raise ChantierError(f"both gh and glab are logged in to {host}: cannot tell its forge",
                            EXIT_EXTERNAL)
    if not kinds:
        raise ChantierError(f"neither glab nor gh is logged in to {host} (remote {remote!r}): "
                            f"`glab auth login --hostname {host}` for GitLab, "
                            f"`gh auth login --hostname {host}` for GitHub Enterprise",
                            EXIT_EXTERNAL)
    if not shutil.which(CLI[kinds[0]]):
        raise ChantierError(f"{CLI[kinds[0]]} not found: install it for {host}", EXIT_EXTERNAL)
    return Forge(kinds[0], host, project, CLI[kinds[0]])


def check(cwd, remote: str) -> str:
    """The forge a batch would use, logged in; raises what stops it."""
    f = detect(str(cwd), remote)
    if f.host and f.exe == CLI[f.kind] and not _logged_in(f.kind, f.host):
        raise ChantierError(f"{f.exe} is not logged in to {f.host}: "
                            f"`{f.exe} auth login --hostname {f.host}`", EXIT_EXTERNAL)
    return f"{f.kind} {f.host}/{f.project}" if f.host else f"{f.kind} (fake {f.exe})"


def _forge(cwd, config: dict) -> Forge:
    return detect(str(cwd), config["remote"])


def _run(f: Forge, *args: str, cwd=None) -> str:
    try:
        p = subprocess.run([f.exe, *args], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=_env(), timeout=120)
    except FileNotFoundError as e:
        raise ChantierError(f"{f.exe} not found", EXIT_EXTERNAL) from e
    except subprocess.TimeoutExpired as e:
        raise ChantierError(f"{f.exe} {' '.join(args[:3])} timed out", EXIT_EXTERNAL) from e
    if p.returncode != 0:
        raise ChantierError(f"{f.exe} {' '.join(args[:3])}: {p.stderr.strip()[:300]}", EXIT_EXTERNAL)
    return p.stdout.strip()


# ---- GitHub -----------------------------------------------------------------------------------

def _gh(f: Forge, *args: str, cwd=None) -> str:
    repo = ["--repo", f"{f.host}/{f.project}"] if f.host else []
    return _run(f, *args, *repo, cwd=cwd)


# ---- GitLab -----------------------------------------------------------------------------------

def _api(f: Forge, cwd, path: str, method: str = "GET", **fields: str) -> str:
    """One call to the project's API; fields are the query of a GET, else the body."""
    args = ["api", f"projects/{quote(f.project or 'local', safe='')}/{path}", "--method", method]
    if f.host:
        args += ["--hostname", f.host]
    for key, value in fields.items():
        args += ["--raw-field", f"{key}={value}"]
    return _run(f, *args, cwd=cwd)


def _mr(link: str) -> str:
    m = re.search(r"/merge_requests/(\d+)", link)
    if not m:
        raise ChantierError(f"not a merge request link: {link}", EXIT_EXTERNAL)
    return m[1]


def _jobs(f: Forge, cwd, pipeline) -> list[dict]:
    checks = []
    for job in json.loads(_api(f, cwd, f"pipelines/{pipeline}/jobs", per_page="100") or "[]"):
        bucket = BUCKETS.get(job.get("status"), "pending")
        if bucket == "fail" and job.get("allow_failure"):
            bucket = "skipping"
        checks.append({"name": job["name"], "bucket": bucket, "link": job.get("web_url", "")})
    return checks


# ---- what the CLI needs, on either forge --------------------------------------------------------

def pr_create(cwd, config: dict, base: str, head: str, title: str, body_file: str) -> str:
    f = _forge(cwd, config)
    if f.kind == "gitlab":
        body = open(body_file, encoding="utf-8").read()
        mr = json.loads(_api(f, cwd, "merge_requests", "POST", source_branch=head,
                             target_branch=base, title=title, description=body))
        return mr["web_url"]
    out = _gh(f, "pr", "create", "--base", base, "--head", head, "--title", title,
              "--body-file", body_file, cwd=cwd)
    return out.splitlines()[-1].strip()


def pr_edit(cwd, config: dict, pr: str, body_file: str | None = None, base: str | None = None):
    f = _forge(cwd, config)
    if f.kind == "gitlab":
        fields = {"target_branch": base} if base else {}
        if body_file:
            fields["description"] = open(body_file, encoding="utf-8").read()
        _api(f, cwd, f"merge_requests/{_mr(pr)}", "PUT", **fields)
        return
    args = ["pr", "edit", pr]
    if body_file:
        args += ["--body-file", body_file]
    if base:
        args += ["--base", base]
    _gh(f, *args, cwd=cwd)


def pr_merge(cwd, config: dict, pr: str, method: str) -> None:
    """Merge a PR now, by `rebase`, `squash` or `merge`; the forge's own rules (branch protection,
    rights, required checks) decide, and a refusal is an error. On GitLab the merge method is the
    project's setting: `squash` asks for a squash, the others take the project's method."""
    f = _forge(cwd, config)
    if f.kind == "gitlab":
        fields = {"squash": "true"} if method == "squash" else {}
        _api(f, cwd, f"merge_requests/{_mr(pr)}/merge", "PUT", **fields)
        return
    _gh(f, "pr", "merge", pr, f"--{method}", cwd=cwd)


def pr_merged(cwd, config: dict, pr: str) -> bool:
    """Whether the forge says the PR is merged."""
    f = _forge(cwd, config)
    if f.kind == "gitlab":
        return json.loads(_api(f, cwd, f"merge_requests/{_mr(pr)}")).get("state") == "merged"
    return json.loads(_gh(f, "pr", "view", pr, "--json", "state", cwd=cwd)).get("state") == "MERGED"


def pr_checks(cwd, config: dict, pr: str) -> list[dict]:
    """Checks of a PR: name, bucket (pass, fail, pending, skipping, cancel) and link. On GitLab,
    the jobs of the merge request's pipeline for its current head."""
    f = _forge(cwd, config)
    if f.kind == "gitlab":
        mr = json.loads(_api(f, cwd, f"merge_requests/{_mr(pr)}"))
        pipeline = mr.get("head_pipeline")
        if not pipeline:
            return []
        if pipeline.get("sha") != mr.get("sha"):  # the new head's pipeline is not there yet
            return [{"name": "pipeline", "bucket": "pending", "link": pipeline.get("web_url", "")}]
        return _jobs(f, cwd, pipeline["id"])
    out = _gh(f, "pr", "checks", pr, "--json", "name,bucket,link", cwd=cwd)
    return json.loads(out or "[]")


def main_failures(cwd, config: dict, branch: str) -> set[str]:
    """Names of failed checks in the latest completed run on the default branch."""
    f = _forge(cwd, config)
    if f.kind == "gitlab":
        pipelines = json.loads(_api(f, cwd, "pipelines", ref=branch, per_page="20") or "[]")
        done = next((p for p in pipelines if p.get("status") in {"success", "failed", "canceled"}),
                    None)
        return {c["name"] for c in _jobs(f, cwd, done["id"]) if c["bucket"] == "fail"} \
            if done else set()
    out = _gh(f, "run", "list", "--branch", branch, "--limit", "20", "--json",
              "name,conclusion,status", cwd=cwd)
    runs = json.loads(out or "[]")
    return {r["name"] for r in runs if r.get("conclusion") == "failure"}


def failed_log(cwd, config: dict, link: str) -> str:
    """Tail of a failed check's log, when the forge gives it; empty otherwise."""
    f = _forge(cwd, config)
    if f.kind == "gitlab":
        m = re.search(r"/-/jobs/(\d+)", link)
        path = f"jobs/{m[1]}/trace" if m else ""
    else:
        run_id = link.rstrip("/").split("/runs/")[-1].split("/")[0] if "/runs/" in link else ""
        path = run_id if run_id.isdigit() else ""
    if not path:
        return ""
    try:
        if f.kind == "gitlab":
            return _api(f, cwd, path)[-4000:]
        return _gh(f, "run", "view", path, "--log-failed", cwd=cwd)[-4000:]
    except ChantierError:
        return ""


def classify(checks: list[dict], red_on_main: set[str], logs: dict[str, str]) -> str:
    failed = [c for c in checks if c.get("bucket") in {"fail", "cancel"}]
    if not failed:
        return "none"
    if all(c["name"] in red_on_main for c in failed):
        return "known-red-on-main"
    if all(c.get("bucket") == "cancel"
           or any(h in logs.get(c["name"], "").lower() for h in INFRA_HINTS) for c in failed):
        return "infra"
    return "product"
