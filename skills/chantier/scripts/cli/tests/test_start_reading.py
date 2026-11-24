"""A role's start reading (CR-471): what it reads before its first act of work, as the manifest
defines it, in LF bytes, each byte counted once; held at or below the figures the PR reports."""

import re
from pathlib import Path

import pytest
import test_plugin_files
import test_startup_manifest
from conftest import PLUGIN_ROOT, SKILL
from test_startup_manifest import _lf_bytes, _manifest, _sections, _unique_startup_bytes

HOSTS = ("claude", "copilot")
LIMIT = 12_544  # the manifest's limit, never raised
SKILLS = PLUGIN_ROOT / "skills"
DRIVERS = ("cr-driver", "stack-driver", "qa-driver", "release-driver")
# the after figures of CR-471's PR (fix round 1, the Chief of Staff's and the Foreman's raised by
# CR-479 for the Foreman's watcher; the Chief of Staff's include its `-any` piece),
# per role and host; at its base the Claude host read
# 380,314 (Chief of Staff), 292,020 (Foreman), 25,134, 66,302, 36,137 and 47,462 (the Drivers)
AFTER = {
    # CR-478 adds the restart offer to the Chief of Staff cards: +1,776 and +1,814 bytes
    ("chief-of-staff", "claude"): 202_396,
    ("chief-of-staff", "copilot"): 111_492,
    ("foreman", "claude"): 91_019,
    ("foreman", "copilot"): 83_545,
    ("cr-driver", "claude"): 27_180,
    ("cr-driver", "copilot"): 27_246,
    ("stack-driver", "claude"): 34_054,
    ("stack-driver", "copilot"): 34_116,
    ("qa-driver", "claude"): 24_122,
    ("qa-driver", "copilot"): 24_192,
    ("release-driver", "claude"): 25_806,
    ("release-driver", "copilot"): 25_866,
}


def _boot(role: str, host: str) -> tuple[list[Path], list[dict[str, str]]]:
    """The boot reading: the cores, the manifest, the wrapper and the role's startup sections."""
    manifest, path = _manifest()
    folder = path.parent
    files = [folder / manifest[k] for k in ("common", "role_core")]
    files += [folder / manifest["hosts"][host]["core"], path]
    if role == "chief-of-staff":
        files.append(SKILLS / role / "SKILL.md")
    elif role != "foreman":
        claude, copilot = f"agents/{role}.md", f"com.github.copilot/agents/chantier-{role}.agent.md"
        files.append(PLUGIN_ROOT / (claude if host == "claude" else copilot))
    more, sections = _sections(manifest["startup_sections"][role], host)
    return files + more, sections


def _start_reading(role: str, host: str) -> int:
    actions = _manifest()[0]["actions"]
    files, sections = _boot(role, host)
    first = {"chief-of-staff": ["session-start", "chief-of-staff"], "foreman": ["batch"]}
    for action in first.get(role, [role]):
        more, extra = _sections(actions[action], host)
        files, sections = files + more, sections + extra
    total = _unique_startup_bytes(files, sections)
    if role in DRIVERS:  # `driver.md`'s opening, before its first `##`: no section holds it
        card = SKILL / "references" / "driver.md"
        assert card.resolve() not in {f.resolve() for f in files}
        total += re.search(rb"^## ", _lf_bytes(card), re.M).start()  # type: ignore[union-attr]
    return total


@pytest.mark.parametrize(("role", "host"), AFTER)
def test_each_start_reading_stays_at_or_below_its_after_figure(role: str, host: str) -> None:
    total = _start_reading(role, host)
    print(f"start-reading role={role} host={host} bytes={total}")
    assert total <= AFTER[(role, host)], (role, host, total)


def test_the_startup_limit_constants_equal_the_manifest_limit() -> None:
    limit = _manifest()[0]["limit"]
    assert limit == LIMIT
    assert limit == test_startup_manifest.STARTUP_LIMIT
    assert limit == test_plugin_files.STARTUP_LIMIT


def test_the_rules_that_must_not_be_missed_come_first() -> None:
    refs = SKILL / "references"
    paragraphs = _lf_bytes(refs / "startup-core.md").decode("utf-8").split("\n\n")
    assert "report the exact error and stop" in " ".join(paragraphs[1].split())
    assert "never in a shell variable" in " ".join(paragraphs[1].split())
    assert paragraphs[2].startswith("No fallback")
    for skill, needle in {
        "chief-of-staff": "`watch: not running`",
        "chantier": "live Chief of Staff in the seat",
        "status": "You change nothing",
    }.items():
        first = _lf_bytes(SKILLS / skill / "SKILL.md").decode("utf-8").split("## Startup core\n")[1]
        assert needle in next(line for line in first.splitlines() if line.strip()), skill
