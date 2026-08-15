"""
The events, read out.

An event is a fact about the machine — ``after_attack_roll`` with ``value 5``,
``required 4``, ``hit true``. Whoever built the engine can read that and nobody
else can, which is why somebody opening the watch page could see FSME working
and not see what was happening.

What is tested is mostly restraint. A sentence may only say what the event
already carried, most events are not worth a line, and a live game and a saved
journal have to be told in the same words.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsme.api import Session, load_content
from fsme.content import ContentLibrary
from fsme.narration import SAID, told

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

NAMES = {0: "Ann", 1: "Bo"}


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


def event(kind: str, **rest: object) -> dict[str, object]:
    return {
        "type": kind,
        "source": rest.pop("source", None),
        "controller": rest.pop("controller", None),
        "targets": rest.pop("targets", []),
        "payload": dict(rest),
    }


def test_an_attack_is_told_as_an_attack() -> None:
    assert (
        told(event("attack_start", source="Polycephalus", controller=0), names=NAMES)
        == "Ann attacks Polycephalus."
    )


def test_a_roll_says_what_it_needed() -> None:
    said = told(
        event("after_attack_roll", controller=0, value=5, required=4, hit=True),
        names=NAMES,
    )

    assert said == "Ann rolls a 5 — a hit, 4 was needed."

    missed = told(
        event("after_attack_roll", controller=1, value=2, required=4, hit=False),
        names=NAMES,
    )

    assert missed == "Bo rolls a 2 — a miss, 4 was needed."


def test_a_roll_with_nothing_to_beat_does_not_invent_a_number() -> None:
    # The engine did not say what was needed, so neither does the sentence.
    said = told(event("after_attack_roll", controller=0, value=5), names=NAMES)

    assert said == "Ann rolls a 5 — a miss."
    assert "needed" not in said


def test_the_whole_of_a_kill_reads_as_a_sequence() -> None:
    lines = [
        told(one, names=NAMES)
        for one in (
            event("attack_start", source="Polycephalus", controller=0),
            event("after_attack_roll", controller=0, value=5, required=4, hit=True),
            event(
                "damage_dealt",
                controller=0,
                targets=["Polycephalus"],
                amount=1,
                remaining_hp=0,
            ),
            event("monster_killed", source="Polycephalus", controller=0, souls=1),
            event("soul_gained", source="Polycephalus", controller=0),
        )
    ]

    assert lines == [
        "Ann attacks Polycephalus.",
        "Ann rolls a 5 — a hit, 4 was needed.",
        "Polycephalus takes 1 damage, 0 left.",
        "Polycephalus is defeated — worth 1 soul.",
        "Ann gains a soul from Polycephalus.",
    ]


def test_damage_says_what_dealt_it_when_the_engine_said() -> None:
    """
    A missed attack roll means the monster hits back, and the account did not
    say so.

    "Bo rolls a 3 — a miss, 4 was needed." then "Bo takes 1 damage, 1 left."
    left the reader to infer the monster from the line above. The engine had
    carried it the whole time, as the event's source.
    """
    said = told(
        event(
            "damage_dealt",
            source="Pin",
            controller=1,
            targets=["Bo"],
            target_kind="player",
            amount=1,
            remaining_hp=1,
            combat=True,
        ),
        names=NAMES,
    )

    assert said == "Bo takes 1 damage from Pin, 1 left."


def test_damage_with_nobody_behind_it_invents_nobody() -> None:
    """
    A player's own attack roll damages a monster with no source on the event,
    because the rules do not name one. "from Ann" would be the sentence saying
    more than the engine knows.
    """
    said = told(
        event(
            "damage_dealt",
            controller=0,
            targets=["Pin"],
            target_kind="monster",
            amount=1,
            remaining_hp=1,
            combat=True,
        ),
        names=NAMES,
    )

    assert said == "Pin takes 1 damage, 1 left."
    assert "from" not in said


def test_a_killing_blow_still_names_what_struck_it() -> None:
    with_source = told(
        event("damage_dealt", source="Pin", targets=["Bo"], amount=2, lethal=True),
        names=NAMES,
    )
    without = told(
        event("damage_dealt", targets=["Pin"], amount=2, lethal=True), names=NAMES
    )

    assert with_source == "Bo takes 2 damage from Pin — enough to finish it."
    assert without == "Pin takes 2 damage — enough to finish it."


def test_a_whole_missed_attack_reads_as_one_thing(
    everything: ContentLibrary,
) -> None:
    """
    The sequence the audit was about, end to end.

    Bo attacks, misses, and is hurt by the monster he attacked — and every line
    of it names Bo and names Pin, so nothing has to be inferred from position.
    """
    lines = [
        told(one, names=NAMES)
        for one in (
            event("attack_start", source="Pin", controller=1, targets=["Pin"]),
            event("after_attack_roll", source="Pin", controller=1, value=3,
                  required=4, hit=False),
            event("damage_dealt", source="Pin", controller=1, targets=["Bo"],
                  target_kind="player", amount=1, remaining_hp=1, combat=True),
        )
    ]

    assert lines == [
        "Bo attacks Pin.",
        "Bo rolls a 3 — a miss, 4 was needed.",
        "Bo takes 1 damage from Pin, 1 left.",
    ]


def test_bookkeeping_gets_no_sentence() -> None:
    """
    Most events are true and are not news.

    Narrating them would bury the four lines that say what the turn was about,
    which is the problem this module exists to solve.
    """
    for kind in ("stack_push", "phase_changed", "stat_modified", "before_damage"):
        assert told(event(kind, controller=0), names=NAMES) == ""


def test_an_amount_of_nothing_is_not_worth_saying() -> None:
    assert told(event("coins_gained", controller=0, amount=0), names=NAMES) == ""
    assert told(event("damage_dealt", controller=0, amount=0), names=NAMES) == ""


def test_a_seat_with_no_name_is_still_named_something() -> None:
    assert told(event("turn_start", controller=3)) == "seat 3's turn begins."


def test_a_live_game_is_told_in_sentences(everything: ContentLibrary) -> None:
    session = Session(everything, players=3, seed=7, interactive_priority=False)

    session.submit({"type": "start_game", "player": 0})

    for _ in range(80):
        moves = session.view(0)["moves"]

        if not moves:
            break

        move = moves[0]

        session.submit(
            {
                "type": move["type"],
                "player": move["player"],
                "payload": move["payload"],
            }
        )

    events = session.view(0)["events"]
    lines = [one["said"] for one in events if one["said"]]

    assert lines, "a game happened and nothing was said about it"

    # Silence is the common case, and that is the design rather than a gap.
    assert len(lines) < len(events)

    # Names, not seat numbers, when the game knows them.
    assert any(line.startswith("Ann") for line in lines)


def test_a_journal_entry_is_told_the_same_way(everything: ContentLibrary) -> None:
    """
    One vocabulary for a live game and a saved one.

    A ``Happening`` is not a dictionary, and reading it differently would let
    the two accounts of one game drift apart.
    """
    from fsme.journal import Happening

    live = event("soul_gained", source="Lust", controller=0)

    kept = Happening(type="soul_gained", source="Lust", controller=0)

    assert told(live, names=NAMES) == told(kept, names=NAMES)


def test_every_narrated_kind_produces_something_or_nothing_safely() -> None:
    # Called with an empty event, no reading may raise: the page shows whatever
    # the engine sent, and half a game is not a reason to stop drawing.
    for kind in SAID:
        told(event(kind))
