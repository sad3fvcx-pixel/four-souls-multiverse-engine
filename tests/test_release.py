"""
What has to be true before this is handed to somebody.

The failures collected here share a shape and it is the nastiest shape a
project can have: everything works perfectly on the machine it was written on,
and the thing that reaches anybody else is missing a piece. No test of the
engine can see it, because the engine is fine.

Two of them were real. ``*.spec`` in a stock Python ``.gitignore`` means
PyInstaller's generated specs, and it ate the hand-written one that is the only
description of how to build the executable. ``target/`` means a Java or Rust
build directory, and it ate ``content/expansions/target`` — the Target
expansion, three cards, gone from every clone while sitting happily on disk
here.

So this does not check for those two files. It checks that nothing in the
directories that must ship is ignored at all, which is the rule the two of them
broke.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

MUST_SHIP = ("content", "spec", "docs", "examples", "packaging", "src", "tests")
"""
Directories whose every file belongs in the repository.

Not "should generally be committed" — every file. Anything under these that git
is ignoring is a file somebody will not receive, and the only way to find out
is to notice a number changing in a clone.
"""


def _git(*arguments: str) -> str:
    done = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    return done.stdout


def test_nothing_that_must_ship_is_being_ignored() -> None:
    present = [name for name in MUST_SHIP if (ROOT / name).is_dir()]

    ignored = [
        line
        for line in _git(
            "ls-files", "--others", "--ignored", "--exclude-standard", *present
        ).splitlines()
        if line and "__pycache__" not in line
    ]

    assert not ignored, (
        "these files exist here and would not reach a clone:\n  "
        + "\n  ".join(ignored)
        + "\n\nA pattern in .gitignore is matching project files. Add an "
        "exception rather than renaming the directory."
    )


def test_the_ignore_rules_do_not_hide_a_whole_directory() -> None:
    """
    The check above finds files; this one finds the patterns that eat them.

    A merely *untracked* file is not tested for: it shows up in `git status`
    every time somebody looks, so it gets noticed. An *ignored* one never does,
    which is why both real losses were ignored rather than forgotten — and why
    the exceptions that rescue them are worth asserting directly.
    """
    rules = (ROOT / ".gitignore").read_text("utf-8")

    for directory in ("content", "spec", "docs", "examples", "packaging"):
        assert f"!{directory}/**" in rules, (
            f"{directory}/ has no blanket exception in .gitignore, so a "
            f"generic pattern can swallow part of it silently"
        )


def test_the_version_is_the_same_everywhere() -> None:
    """
    Three places say what version this is, and they have to agree.

    A wheel that reports one number and a ``--version`` that reports another is
    the kind of thing nobody notices until somebody files a bug against a
    release that does not exist.
    """
    from fsme.cli.main import VERSION

    packaged = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))

    assert packaged["project"]["version"] == VERSION

    changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")

    assert VERSION in changelog, f"CHANGELOG.md does not mention {VERSION}"


def test_the_documents_a_newcomer_is_sent_to_exist() -> None:
    for name in (
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
        "docs/GETTING_STARTED.md",
        "docs/LIMITATIONS.md",
        "docs/NEXT.md",
        "docs/DEMONSTRATION.md",
        "examples/README.md",
    ):
        assert (ROOT / name).is_file(), name


def test_every_link_the_readme_makes_to_this_repository_resolves() -> None:
    """
    A broken link in the first thing anybody reads.
    """
    import re

    readme = (ROOT / "README.md").read_text("utf-8")

    missing = [
        target
        for target in re.findall(r"\]\(([^)#:]+)\)", readme)
        if not (ROOT / target).exists()
    ]

    assert not missing, f"README links to files that are not here: {missing}"


@pytest.mark.parametrize(
    "name", ["bug_report.yml", "feature_request.yml", "config.yml"]
)
def test_there_is_somewhere_to_report_what_goes_wrong(name: str) -> None:
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / name).is_file()
