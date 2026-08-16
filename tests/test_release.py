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
    Several places say what version this is, and they have to agree.

    This test used to compare the packaging with the command line and stop
    there. Both read the same literal, so both agreed — while
    ``fsme.__version__``, which nothing here looked at, said 0.1.0 and stamped
    that into every journal FSME wrote. A consistency check that does not cover
    every copy is a consistency check that certifies the disagreement.

    There is one copy now, and the rest are derived from it. What is left to
    check is that they are still derived rather than copied back.
    """
    import fsme
    from fsme.cli.main import VERSION

    assert VERSION == fsme.__version__

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


# ----------------------------------------------------------------------
# The workflow that has to fire when a release is cut
# ----------------------------------------------------------------------


def _workflow(*, settings_only: bool = False) -> str:
    """
    The build workflow, optionally with its comments stripped.

    The comments explain what went wrong last time, and quote the very setting
    that was wrong — so a test grepping the whole file finds the trap described
    in the prose and calls it the trap itself.
    """
    told = (ROOT / ".github" / "workflows" / "build.yml").read_text("utf-8")

    if not settings_only:
        return told

    return "\n".join(
        line for line in told.splitlines() if not line.lstrip().startswith("#")
    )


def test_a_tag_that_is_not_v_prefixed_still_builds() -> None:
    """
    `tags: ["v*"]` looks harmless and is a trap.

    The 0.1.0 release was cut as `0.1.0`. It matched nothing, no build ran,
    and the release was published with no binaries on it — which is invisible,
    because a release page with no assets looks exactly like one whose build
    has not finished yet.
    """
    settings = _workflow(settings_only=True)

    assert 'tags: ["v*"]' not in settings, "a tag pattern that excludes 0.1.0"
    assert 'tags: ["*"]' in settings

    assert "startsWith(github.ref, 'refs/tags/v')" not in settings
    assert "startsWith(github.ref, 'refs/tags/')" in settings


def test_a_tagged_build_puts_the_binaries_where_people_can_reach_them() -> None:
    """
    Actions artifacts expire and need a GitHub login to download.

    Somebody who came to a release page wanting a file to run cannot use one.
    The binaries have to be on the release itself.
    """
    settings = _workflow(settings_only=True)

    assert "gh release upload" in settings
    assert "contents: write" in settings

    # Named for the platform, or three files called `fsme` collide.
    for asset in ("fsme-linux", "fsme-windows.exe", "fsme-macos"):
        assert asset in settings, asset


# ----------------------------------------------------------------------
# One version, in one place
# ----------------------------------------------------------------------


def test_the_project_has_exactly_one_version_number() -> None:
    """
    It had two, and they disagreed for three releases.

    ``src/fsme/__init__.py`` said 0.1.0 while the packaging said 0.1.3, and the
    journal stamps whichever the package says — so every journal FSME had ever
    written claimed to come from a version three releases old. The field nobody
    reads until something is incompatible was the one that was wrong.

    So the packaging is not allowed to carry a number of its own any more: it
    reads the attribute, and this checks that it still does.
    """
    import fsme

    written = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    project = written["project"]

    assert "version" not in project, (
        "pyproject.toml carries a version of its own again, so there are two"
    )
    assert "version" in project.get("dynamic", ()), (
        "the packaging no longer derives its version from anywhere"
    )

    derived = written["tool"]["setuptools"]["dynamic"]["version"]

    assert derived == {"attr": "fsme.__version__"}, derived
    assert fsme.__version__, "the one version is empty"


def test_the_command_line_prints_the_version_the_package_has() -> None:
    import fsme
    from fsme.cli.main import VERSION

    assert VERSION == fsme.__version__


def test_a_journal_is_stamped_with_the_version_that_wrote_it() -> None:
    """
    The field the disagreement actually reached.
    """
    import fsme
    from fsme.api import Session, load_content

    session = Session(load_content(ROOT / "content"), players=2, seed=1)

    assert session.journal.engine_version == fsme.__version__


def test_the_card_data_holds_only_card_data() -> None:
    """
    A journal was once committed into ``content/``.

    The desk writes the game a loaded report carries into its work directory,
    and a test passed ``content/`` as that directory — so a two-command journal
    was written among the cards and travelled in a release. Nothing caught it:
    the rule next door checks that nothing under ``content/`` is *ignored*,
    which a tracked stray file passes.
    """
    strays = [
        path.relative_to(ROOT)
        for path in (ROOT / "content").rglob("*.json")
        if path.stem.startswith("loaded-")
        or path.stem.startswith("fsme-journal")
        or path.parent.name == "content"
        and path.name not in ("manifest.json",)
    ]

    assert not strays, f"these are not card data: {strays}"
