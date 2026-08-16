"""
A journal as a file, and back again.

The whole promise of Save is that what comes back is what went in. Not "looks
similar", not "has the same number of lines" — the same data, because the file
is read by the same page that read the live game, and a technical log that
quietly lost a field would look exactly like one that had not.

So the equivalence is asserted on the serialised journal itself rather than on
anything rendered from it, and then again field by field on the things a reader
would notice missing only much later: the order events came in, who each one
was about, and what the payload carried.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from fsme.api import Session, load_content
from fsme.content import ContentLibrary
from fsme.journal import (
    FILE_VERSION,
    JOURNAL_FORMAT_VERSION,
    MARKER,
    Journal,
    JournalFormatError,
    suggested_name,
    unwrap,
    wrap,
)

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture(scope="module")
def played(everything: ContentLibrary) -> Journal:
    """
    A whole game, played the way Watch plays one.

    Seed 4 is chosen for what happens in it rather than at random: it is dealt,
    fought, bought in, died in, revived from, rewarded and won, so a round trip
    over it is a round trip over every kind of event a reader would notice
    missing. A seed where nobody ever bought anything would let this file pass
    while purchases were being dropped.
    """
    from fsme.lab.bot import HeuristicBot
    from fsme.lab.simulation import ScriptedAgent
    from fsme.lab.simulation.runner import _whose_move

    session = Session(everything, players=2, seed=4)
    game = session.game

    bot = HeuristicBot(4)
    agent = ScriptedAgent(4)

    for _ in range(4000):
        if game.is_over:
            break

        if game.runtime.awaiting_decision is not None:
            answered = agent.choose(game)

            if answered is None:
                break

            command, label = answered
        else:
            thought = bot.choose(game, seats=(_whose_move(game),))

            if thought is None:
                break

            command, label = thought[0], thought[1]

        if not session.submit(
            {
                "type": str(command.type),
                "player": command.player,
                "payload": dict(command.payload),
                "label": label,
            }
        )["accepted"]:
            break

    return session.journal


# ----------------------------------------------------------------------
# Save, then load
# ----------------------------------------------------------------------


def test_a_saved_journal_comes_back_the_same(played: Journal) -> None:
    """
    The claim the whole feature rests on, stated once and bluntly.
    """
    before = played.to_dict()

    through_a_file = json.loads(json.dumps(wrap(played)))
    after = unwrap(through_a_file).to_dict()

    assert after == before


def test_nothing_about_a_game_is_dropped_on_the_way(played: Journal) -> None:
    """
    The same equivalence, said in the terms somebody would miss it in.

    A log that lost ``controller`` or an ``actor`` would still print, still
    scroll, and still look like a record of the game — which is exactly why
    the round trip is checked field by field and not by eye.
    """
    back = unwrap(json.loads(json.dumps(wrap(played))))

    assert back.seed == played.seed
    assert back.players == played.players
    assert back.characters == played.characters
    assert back.outcome == played.outcome
    assert len(back.entries) == len(played.entries)

    for was, now in zip(played.entries, back.entries, strict=True):
        assert now.index == was.index
        assert now.command == was.command
        assert now.player == was.player
        assert now.payload == was.payload
        assert now.label == was.label
        assert now.digest == was.digest
        assert now.before.to_dict() == was.before.to_dict()

        # Order, not just membership: a log is a sequence.
        assert [one.type for one in now.events] == [
            one.type for one in was.events
        ]

        for old, new in zip(was.events, now.events, strict=True):
            assert new.type == old.type
            assert new.source == old.source
            assert new.source_id == old.source_id
            assert new.controller == old.controller
            assert new.targets == old.targets
            assert new.payload == old.payload


def test_the_technical_events_survive(played: Journal) -> None:
    """
    The bookkeeping is the half a report would throw away, and the half the
    step log exists to show.
    """
    back = unwrap(wrap(played))

    kinds = {one.type for entry in back.entries for one in entry.events}

    for expected in (
        "game_start",
        "loot_drawn",
        "coins_gained",
        "stack_push",
        "stack_resolve",
        "before_attack_roll",
        "after_attack_roll",
        "damage_dealt",
    ):
        assert expected in kinds, expected


def test_the_deal_and_the_starting_cents_survive(played: Journal) -> None:
    back = unwrap(wrap(played))

    opening = back.entries[0]

    assert opening.command == "start_game"
    assert any(one.type == "loot_drawn" for one in opening.events)

    dealt = [
        one.payload.get("amount")
        for one in opening.events
        if one.type == "coins_gained"
    ]

    assert dealt and all(amount == 3 for amount in dealt), dealt


def test_every_kind_of_thing_that_happened_survives(played: Journal) -> None:
    """
    Not a sample: the list a reader would go looking for.

    Asserted without a guard, because a guarded version of this passes on a
    game where none of it happened — which is the failure it is meant to catch
    dressed as a success.
    """
    assert played.outcome, "the fixture did not finish, so this proves nothing"

    back = unwrap(wrap(played))

    assert back.outcome == played.outcome

    kinds = {one.type for entry in back.entries for one in entry.events}

    for expected in (
        "treasure_bought",
        "monster_killed",
        "before_rewards",
        "soul_gained",
        "player_died",
        "player_revived",
        "winner_declared",
        "game_end",
    ):
        assert expected in kinds, expected


def test_the_actor_a_blow_was_struck_for_survives(played: Journal) -> None:
    back = unwrap(wrap(played))

    blows = [
        one
        for entry in back.entries
        for one in entry.events
        if one.type == "damage_dealt" and one.payload.get("combat")
    ]

    assert blows, "this game had no combat damage in it"
    assert all("actor" in one.payload for one in blows)


# ----------------------------------------------------------------------
# What is not a journal
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "complaint"),
    [
        ("just a string", "does not hold anything"),
        ([], "does not hold anything"),
        ({}, "does not say what it is"),
        ({"format": "something-else", "version": 1}, "not an FSME journal"),
        ({"format": MARKER, "version": "one"}, "no readable version"),
        ({"format": MARKER, "version": FILE_VERSION + 1}, "newer version"),
        ({"format": MARKER, "version": FILE_VERSION}, "no game in it"),
        ({"format": MARKER, "version": FILE_VERSION, "journal": []}, "no game in it"),
    ],
)
def test_a_file_that_is_not_a_journal_says_which_way(
    given: Any, complaint: str
) -> None:
    """
    Each way of being wrong gets its own sentence.

    "Invalid file" would be true of all of them and would help with none: a
    user who picked the wrong file, a user on an old build, and a user with a
    truncated download need three different next steps.
    """
    with pytest.raises(JournalFormatError) as raised:
        unwrap(given)

    assert complaint in str(raised.value)


def test_a_journal_from_another_engine_format_is_refused() -> None:
    """
    The envelope's version and the journal's version are different questions
    and get different answers.
    """
    with pytest.raises(JournalFormatError) as raised:
        unwrap(
            {
                "format": MARKER,
                "version": FILE_VERSION,
                "journal": {"format": "0", "entries": []},
            }
        )

    assert "format 0" in str(raised.value)
    assert JOURNAL_FORMAT_VERSION in str(raised.value)


def test_a_saved_report_is_recognised_as_a_report(everything: ContentLibrary) -> None:
    """
    The two files look alike from a file manager and are not interchangeable.
    """
    with pytest.raises(JournalFormatError) as raised:
        unwrap({"fsme_report": 1, "journal": {}, "text": "a report"})

    assert "Load report" in str(raised.value)


# ----------------------------------------------------------------------
# What the file is called
# ----------------------------------------------------------------------


def test_a_file_is_named_after_the_game_it_holds() -> None:
    assert suggested_name(Journal(seed=32)) == "fsme-journal-seed-32.json"


def test_a_game_with_no_seed_still_gets_a_name() -> None:
    named = suggested_name(Journal(seed=0))

    assert named.startswith("fsme-journal-")
    assert named.endswith(".json")
    assert "seed" not in named, "there is no seed, so it must not claim one"


# ----------------------------------------------------------------------
# Over HTTP, which is how the page does it
# ----------------------------------------------------------------------


def fetch(address: str, path: str) -> tuple[dict[str, str], bytes]:
    with urllib.request.urlopen(f"{address}{path}", timeout=10) as answer:
        return dict(answer.headers), answer.read()


def send(address: str, path: str, body: Any) -> Any:
    request = urllib.request.Request(
        f"{address}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=10) as answer:
        return json.loads(answer.read())


def test_the_page_can_save_and_open_a_journal(everything: ContentLibrary) -> None:
    """
    The round trip as the browser makes it: download the file, hand it back.
    """
    import threading

    from fsme.web import serve

    session = Session(everything, players=2, seed=32)

    session.submit(
        {"type": "pass_priority", "player": 0, "label": "Pass"}
    )

    server = serve(session, port=0)
    address = f"http://127.0.0.1:{server.server_address[1]}"

    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        headers, body = fetch(address, "/api/journal/file")

        assert "fsme-journal-seed-32.json" in headers["Content-Disposition"]

        saved = json.loads(body)

        assert saved["format"] == MARKER
        assert saved["version"] == FILE_VERSION

        opened = send(address, "/api/journal/open", {"file": saved})

        assert opened["journal"] == session.journal.to_dict()
        assert opened["account"], "a saved game came back with nothing said about it"
        assert any("turn begins" in said for said in opened["account"])
    finally:
        server.shutdown()


def test_opening_a_journal_does_not_touch_the_game(
    everything: ContentLibrary,
) -> None:
    """
    Reading a saved game is reading. The game being watched must be exactly
    where it was left, or "Back to the live game" is a lie.
    """
    import threading

    from fsme.web import serve

    session = Session(everything, players=2, seed=5)
    server = serve(session, port=0)
    address = f"http://127.0.0.1:{server.server_address[1]}"

    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        before = session.save()
        entries = len(session.journal)

        other = Session(everything, players=2, seed=99)
        other.submit({"type": "pass_priority", "player": 0, "label": "Pass"})

        opened = send(
            address, "/api/journal/open", {"file": wrap(other.journal)}
        )

        assert opened["journal"]["seed"] == 99, "the wrong game came back"

        assert session.save() == before, "opening a file moved the live game"
        assert len(session.journal) == entries
        assert session.game.state.seed == 5
    finally:
        server.shutdown()


def test_a_bad_file_is_refused_over_http_with_a_reason(
    everything: ContentLibrary,
) -> None:
    import threading

    from fsme.web import serve

    session = Session(everything, players=2, seed=5)
    server = serve(session, port=0)
    address = f"http://127.0.0.1:{server.server_address[1]}"

    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        with pytest.raises(urllib.error.HTTPError) as raised:
            send(address, "/api/journal/open", {"file": {"nothing": "much"}})

        assert raised.value.code == 400

        said = json.loads(raised.value.read())

        assert "not an FSME journal" in said["error"]
    finally:
        server.shutdown()


# ----------------------------------------------------------------------
# The other file this project writes
# ----------------------------------------------------------------------


def test_the_two_kinds_of_file_do_not_take_each_other(
    everything: ContentLibrary, tmp_path: Path
) -> None:
    """
    Save report and Save journal write different things for different reasons,
    and both end in ``.json`` in the same downloads folder.

    A report carries a game *and* an analysis of it, and loading one re-runs
    the analysis. A journal carries the game and nothing else, and loading one
    reads it. Handing either to the other's loader has to fail by name rather
    than by traceback — and, in particular, the report loader must not start a
    job over a file that is not a report.
    """
    from fsme.lab.desk.bench import Workbench

    session = Session(everything, players=2, seed=7)
    session.submit({"type": "pass_priority", "player": 0, "label": "Pass"})

    saved_journal = wrap(session.journal)
    a_report = {
        "fsme_report": 1,
        "fsme_version": "0.1.3",
        "kind": "play",
        "title": "a game",
        "text": "the report",
        "journal": session.journal.to_dict(),
    }

    # A report handed to the journal reader.
    with pytest.raises(JournalFormatError) as refused:
        unwrap(a_report)

    assert "Load report" in str(refused.value)

    # A journal handed to the report reader. The work directory is a scratch
    # one: loading a report writes the game it carries to disk, and an
    # earlier version of this test pointed that at `content/` and committed
    # a journal into the card data.
    bench = Workbench(everything, CONTENT_ROOT, tmp_path)

    with pytest.raises(ValueError) as declined:
        bench.take_bundle(saved_journal)

    assert "not an FSME report" in str(declined.value)

    # And the report loader still takes a report, unchanged by any of this.
    assert bench.take_bundle(a_report) is not None
