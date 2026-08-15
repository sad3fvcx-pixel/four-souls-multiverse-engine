"""
The one thing a release workflow has to do without being helped.

Pushing a tag creates a *tag*. It does not create a *release* — a release is a
separate object, and ``gh release upload`` against a tag that has none fails
with ``release not found``. That happened on v0.1.2 and again on v0.1.3: every
platform built, every smoke test passed, and the last step failed, so the
release was created by hand and the failed jobs re-run by hand. Twice. Neither
time did anything go wrong with the build.

The failure is invisible from inside a build because nothing about the build is
wrong. It is a fact about the *shape* of the workflow: a step that uploads,
sitting in a job with nothing that makes a release first. So that shape is what
is checked here, and it is checked against the file that actually ships.

The workflow is read as YAML rather than grepped, which is why this file adds
the one test-only dependency the project has. The assertions below are about
which job a step belongs to and what runs before it, and a hand-rolled parser
that got that subtly wrong would go green while the bug it exists to catch came
back — which is the exact failure mode this whole file is about.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip(
    "yaml",
    reason=(
        "pyyaml is in the dev extra; without it this file cannot check the "
        "release workflow and must not pretend it did"
    ),
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"

ASSETS = ("fsme-linux", "fsme-windows.exe", "fsme-macos")
"""
What a release has to carry.

Named for the platform because three files called ``fsme`` collide, and a
release page that quietly kept one of them is worse than one that kept none.
"""


@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    loaded = yaml.safe_load(WORKFLOW.read_text("utf-8"))

    assert isinstance(loaded, dict), f"{WORKFLOW} is not a workflow"

    read: dict[str, Any] = dict(loaded)

    # `on:` is a YAML boolean. GitHub's own key for what triggers a workflow
    # parses as True rather than as the word, which is a joke at everybody's
    # expense and is fixed here once instead of at every use.
    triggers = read.pop(True, None)  # type: ignore[call-overload]

    if triggers is not None:
        read["on"] = triggers

    return read


def jobs(workflow: dict[str, Any]) -> dict[str, Any]:
    return dict(workflow["jobs"])


def scripts(job: dict[str, Any]) -> list[str]:
    """
    Every shell script in a job, in the order the job runs them.
    """
    return [str(step["run"]) for step in job.get("steps", ()) if step.get("run")]


def running(job: dict[str, Any], what: str) -> list[int]:
    """
    Which of a job's steps run something, by position.
    """
    return [index for index, script in enumerate(scripts(job)) if what in script]


def publishing(workflow: dict[str, Any]) -> dict[str, Any]:
    """
    Every job that puts a file on a release.
    """
    return {
        name: job
        for name, job in jobs(workflow).items()
        if running(job, "gh release upload")
    }


# ----------------------------------------------------------------------
# The failure this file exists for
# ----------------------------------------------------------------------


def test_something_actually_publishes_the_binaries(workflow: dict[str, Any]) -> None:
    assert publishing(workflow), (
        "nothing puts a binary on a release; artifacts expire and need a login"
    )


def test_nothing_uploads_to_a_release_it_has_not_made_sure_of(
    workflow: dict[str, Any],
) -> None:
    """
    ``release not found``, stated as a rule instead of as an incident.

    A job that uploads must, earlier in the same job, make sure the release is
    there. Not somewhere else in the workflow and not on a good day: in that
    job, before that step, every time it runs.
    """
    for name, job in publishing(workflow).items():
        made = running(job, "gh release create")
        uploaded = running(job, "gh release upload")

        assert made, (
            f"job '{name}' uploads to a release and never creates one — this is "
            "the failure that stopped v0.1.2 and v0.1.3, and it looks like a "
            "working workflow right up to the last step"
        )

        assert min(made) < min(uploaded), (
            f"job '{name}' creates the release after uploading to it"
        )


def test_an_existing_release_is_used_and_not_written_over(
    workflow: dict[str, Any],
) -> None:
    """
    Creating unconditionally would swap one failure for another.

    A re-run, or a tag whose release somebody wrote notes for by hand, must find
    that release and use it. So the create has to be reached only when there is
    nothing there — which means something has to look first.
    """
    for name, job in publishing(workflow).items():
        made = running(job, "gh release create")
        looked = running(job, "gh release view")

        assert looked, (
            f"job '{name}' creates a release without ever asking whether one "
            "exists, so a re-run fails on the release it made last time"
        )

        assert min(looked) <= min(made), (
            f"job '{name}' asks whether the release exists only after creating it"
        )

    edits = [
        name
        for name, job in jobs(workflow).items()
        if running(job, "gh release edit")
    ]

    assert not edits, (
        f"{edits} rewrites a release that already exists; its notes belong to "
        "whoever wrote them"
    )


def test_the_release_is_made_once_and_not_by_three_runners(
    workflow: dict[str, Any],
) -> None:
    """
    The next version of this bug, refused in advance.

    Moving the create into the build matrix is the obvious fix and it is wrong:
    three runners finish within seconds of each other, all three find no
    release, and two of them fail creating one that now exists. Whichever job
    publishes must not be a matrix.
    """
    for name, job in publishing(workflow).items():
        assert "strategy" not in job, (
            f"job '{name}' publishes from a build matrix, so every platform "
            "races to create the same release"
        )


def test_the_release_waits_for_every_platform_to_build(
    workflow: dict[str, Any],
) -> None:
    """
    A release made before the binaries exist is a release page with nothing on
    it, which looks exactly like one whose build has not finished.
    """
    built = {
        name
        for name, job in jobs(workflow).items()
        if any("pyinstaller" in script for script in scripts(job))
    }

    assert built, "nothing builds an executable"

    for name, job in publishing(workflow).items():
        needs = job.get("needs") or []
        needs = [needs] if isinstance(needs, str) else list(needs)

        assert built & set(needs), (
            f"job '{name}' publishes without waiting for {sorted(built)}"
        )


def test_publishing_is_the_only_thing_allowed_to_write(
    workflow: dict[str, Any],
) -> None:
    """
    The token needs ``contents: write`` to make a release, and nothing else here
    needs it at all.
    """
    for name, job in publishing(workflow).items():
        assert (job.get("permissions") or {}).get("contents") == "write", (
            f"job '{name}' publishes without permission to"
        )

    writing = {
        name
        for name, job in jobs(workflow).items()
        if (job.get("permissions") or {}).get("contents") == "write"
    }

    assert writing == set(publishing(workflow)), (
        f"{sorted(writing - set(publishing(workflow)))} can write to the "
        "repository and has no reason to"
    )


# ----------------------------------------------------------------------
# What has to reach the release page
# ----------------------------------------------------------------------


def test_all_three_binaries_are_published(workflow: dict[str, Any]) -> None:
    for name, job in publishing(workflow).items():
        uploads = "\n".join(
            script for script in scripts(job) if "gh release upload" in script
        )

        for asset in ASSETS:
            assert asset in uploads, f"job '{name}' never uploads {asset}"


def test_the_workflow_checks_the_release_really_got_them(
    workflow: dict[str, Any],
) -> None:
    """
    0.1.0 was published with no assets at all and nobody noticed, because a
    release page with nothing on it looks like one that is still building. The
    only way to know is to ask the release what it has.
    """
    for name, job in publishing(workflow).items():
        after = "\n".join(scripts(job))

        assert "gh release view" in after and "--json assets" in after, (
            f"job '{name}' uploads and never checks that anything arrived"
        )


def test_a_tag_is_still_the_thing_that_starts_it(workflow: dict[str, Any]) -> None:
    """
    And any tag, not only ``v``-prefixed ones: 0.1.0 was cut without the ``v``,
    matched ``tags: ["v*"]``, and produced no build at all.
    """
    on = workflow["on"]

    assert on["push"]["tags"] == ["*"]
    assert "workflow_dispatch" in on, "the workflow can no longer be run by hand"

    for name, job in publishing(workflow).items():
        assert job.get("if") == "startsWith(github.ref, 'refs/tags/')", (
            f"job '{name}' publishes on something other than a tag"
        )


def test_the_build_still_covers_the_three_platforms(
    workflow: dict[str, Any],
) -> None:
    """
    Nothing above is worth anything if the change quietly dropped a platform.
    """
    for name, job in jobs(workflow).items():
        if not any("pyinstaller" in script for script in scripts(job)):
            continue

        legs = job["strategy"]["matrix"]["include"]
        assert {str(leg["os"]) for leg in legs} == {
            "ubuntu-latest",
            "windows-latest",
            "macos-latest",
        }, f"job '{name}' no longer builds all three platforms"

        assert {str(leg["asset"]) for leg in legs} == set(ASSETS)

        # The smoke tests are the reason a build is trusted at all.
        ran = "\n".join(scripts(job))

        for asked in ("cards", "play --seed", "study --games"):
            assert asked in ran, f"job '{name}' stopped smoke-testing `{asked}`"
