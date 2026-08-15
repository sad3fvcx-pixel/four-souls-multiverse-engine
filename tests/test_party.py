"""
One game, one report.

The report measures nothing of its own — it arranges what summary, moments and
risk already found — so the tests are about the arrangement being honest: that
it never claims more of a count is better, that a section missing its input
says so instead of leaving a gap, and that it cannot disagree with the reports
it is built from.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fsme.api import load_content
from fsme.content import ContentLibrary
from fsme.journal import Journal
from fsme.lab.analysis import Review, review, reviewed
from fsme.lab.simulation import play_one

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture(scope="module")
def a_journal(everything: ContentLibrary) -> Journal:
    journal, _ = play_one(everything, seed=7, players=3, thinking_seats=(0,))

    return journal


@pytest.fixture(scope="module")
def a_report(a_journal: Journal, everything: ContentLibrary) -> Review:
    return review(a_journal, everything)


def test_the_report_holds_every_section(a_report: Review) -> None:
    told = reviewed(a_report)

    for heading in (
        "FSME GAME REPORT",
        "The table",
        "Key moments",
        "Why the others did not",
        "The decisions",
        "What did the work",
    ):
        assert heading in told, heading

    assert f"Why {a_report.summary.seats[a_report.summary.winner or 0].name} won" in told


def test_the_report_never_says_more_of_a_count_is_better(
    a_report: Review,
) -> None:
    """
    The winner of this game died more often than the table did.

    A report that marked every difference with a plus would be claiming that
    dying more helped, which it has no way of knowing and which is not true.
    """
    told = reviewed(a_report)

    assert "has no opinion" in told
    assert "went with winning rather than causing it" in told


def test_the_report_agrees_with_the_reports_it_is_made_of(
    a_journal: Journal, a_report: Review
) -> None:
    from fsme.lab.analysis import summarise, turning_points

    assert a_report.summary.to_dict() == summarise(a_journal).to_dict()

    assert [moment.index for moment in a_report.turning.moments] == [
        moment.index for moment in turning_points(a_journal, top=3).moments
    ]


def test_without_content_the_decisions_are_missing_and_said_to_be(
    a_journal: Journal,
) -> None:
    told = reviewed(review(a_journal))

    assert "The decisions" not in told
    assert "decisions were not weighed" in told


def test_the_decisions_can_be_skipped_for_speed(
    a_journal: Journal, everything: ContentLibrary
) -> None:
    told = review(a_journal, everything, decisions=0)

    assert told.dangers is None
    assert told.names, "the card names survive even without the replay"


def test_a_card_that_helped_the_other_side_scores_below_zero(
    a_report: Review,
) -> None:
    cards = a_report.turning.cards

    assert cards
    assert any(card.swing < 0 for card in cards), (
        "monsters that hurt the winner should count against, not for"
    )

    assert "signed towards" in reviewed(a_report)


def test_the_report_is_plain_data(a_report: Review) -> None:
    written = a_report.to_dict()

    assert json.loads(json.dumps(written)) == written
    assert set(written) == {"summary", "turning", "dangers"}


def test_a_game_nobody_won_is_reported_as_one(
    everything: ContentLibrary,
) -> None:
    told = reviewed(
        review(Journal(seed=1, players=("Ann", "Bo")), everything)
    )

    assert "Nobody won" in told


def test_a_good_decision_needs_a_worse_one_to_have_been_available(
    a_report: Review,
) -> None:
    dangers = a_report.dangers

    assert dangers is not None

    for risk in dangers.best:
        # The margin over the runner-up is the whole claim: taking the best
        # move when everything scored the same is not a decision.
        assert risk.margin > 0
        assert risk.regret == 0
        assert risk.considered > 1
