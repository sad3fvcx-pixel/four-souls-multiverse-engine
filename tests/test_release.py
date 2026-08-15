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

MUST_SHIP = ("content", "spec", "docs", "examples", "packaging")
"""
Directories whose every file belongs in the repository.

Not "should generally be committed" — every file. Anything under these that git
is ignoring is a file somebody will not receive, and the only way to find out
is to notice a number changing in a clone.

``src`` and ``tests`` are deliberately absent, and the first version of this
test had them and went red in CI for it: ``pip install -e .`` writes
``src/*.egg-info`` and ``.gitignore`` rightly hides it. They belong out for a
better reason than that, though — they are the directories somebody works in
every day, so a file that fails to arrive there is noticed within an hour. The
danger is content nobody looks at directly.
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


# ----------------------------------------------------------------------
# Windows
# ----------------------------------------------------------------------


def test_the_reports_survive_a_console_that_cannot_spell_them() -> None:
    """
    Windows hands a Python process a cp1252 console.

    cp1252 cannot encode a box-drawing rule, so `fsme demo` — the first thing
    anybody is told to run — died on its own first line with a
    UnicodeEncodeError from inside `print`. Only on Windows, and only in CI,
    which is where it was found.

    This reproduces it anywhere: wrap stdout in a cp1252 writer that raises the
    way the real one does, and print what the tour prints.
    """
    import io
    import sys

    from fsme.cli.main import _speak_utf8

    box = "─" * 78
    everything = f"{box}\n· × ¢ ± σ → … —\n"

    raw = io.BytesIO()
    narrow = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")

    was = sys.stdout
    sys.stdout = narrow

    try:
        # Without the fix this raises, which is the bug.
        _speak_utf8()

        print(everything, end="")

        sys.stdout.flush()
    finally:
        sys.stdout = was

    written = raw.getvalue()

    assert written, "nothing reached the stream"
    assert b"?" not in written or box.encode("utf-8") in written


def test_reconfiguring_a_stream_that_cannot_be_reconfigured_is_survivable() -> None:
    """
    Something may have replaced stdout with an object that is not a stream.

    Replacing it back would be ruder than leaving it alone, and crashing over
    it would be absurd — the whole point of the call is to stop a crash.
    """
    import io
    import sys

    from fsme.cli.main import _speak_utf8

    was = sys.stdout
    sys.stdout = io.StringIO()  # no reconfigure at all

    try:
        _speak_utf8()
    finally:
        sys.stdout = was


# ----------------------------------------------------------------------
# The documents saying what is true
# ----------------------------------------------------------------------


def test_the_card_counts_in_the_documents_are_the_engine_s_counts() -> None:
    """
    Four documents quote how much of the content works.

    A number in a README is a claim, and this one moves every time somebody
    implements a card. Left alone it becomes a lie slowly and silently, which
    is the worst way for a document to become wrong: nobody re-reads a sentence
    they have already read.
    """
    import re

    from fsme.api import load_content

    library = load_content(ROOT / "content")

    cards = list(library.definitions())

    working = sum(1 for card in cards if card.abilities or card.statics)
    total = len(cards)
    missing = total - working

    said = {
        "README.md": (working, total),
        "docs/LIMITATIONS.md": (working, total),
        "CHANGELOG.md": (working, total),
        "CONTRIBUTING.md": (missing, total),
        ".github/ISSUE_TEMPLATE/config.yml": (missing, total),
    }

    wrong: list[str] = []

    for name, (count, whole) in said.items():
        text = (ROOT / name).read_text("utf-8")

        # "352 of 1045", possibly wrapped across a line.
        pattern = re.compile(rf"\b{count}\b[^.]{{0,40}}?\b{whole}\b", re.S)

        if not pattern.search(text):
            wrong.append(f"{name} does not say {count} of {whole}")

    assert not wrong, (
        "the engine implements "
        f"{working} of {total} cards ({missing} without rules), and:\n  "
        + "\n  ".join(wrong)
    )


def test_the_coverage_document_the_issue_template_points_at_exists() -> None:
    assert (ROOT / "docs" / "OFFICIAL_CARD_COVERAGE.md").is_file()
