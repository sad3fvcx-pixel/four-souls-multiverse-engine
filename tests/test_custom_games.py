"""
Custom games: set one up, keep it, deal it in Watch, and deal it again.

A custom game is a scenario the desk keeps in the author's own folder, so every
test here goes the way the page goes — over HTTP, to a desk built the way
`fsme desk` builds it — and checks what the game actually dealt rather than
what the server said it would deal.

The desk also reads the author's sets again when they change on disk. Before it
did, a set written in a running desk could not be watched until the desk was
started again; the tests for that are here because a custom game is the first
thing somebody would try it with.
"""

from __future__ import annotations

import argparse
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from fsme.api import Session
from fsme.cli.main import library
from fsme.content import ContentLibrary
from fsme.lab.desk import Workbench, desk
from fsme.scenario import load as read_scenario
from fsme.web.server import GameServer

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"
PAGE = Path(__file__).resolve().parents[1] / "src/fsme/web/static/index.html"

CAIN = "characters-base_game-cain"
EVE = "characters-base_game-eve"
EDEN = "characters-base_game-eden"
INCUBUS = "starting_items-base_game-incubus"
THE_CURSE = "starting_items-base_game-the_curse"

A_PENNY = {
    "name": "Lucky Penny",
    "kind": "loot",
    "text": "Gain 3¢.",
    "ability": {
        "trigger": "on_play",
        "effects": [{"id": "gain_coins", "fields": {"amount": 3}}],
    },
}


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    A workspace of this test's own, so nothing touches a real one.
    """
    where = tmp_path / "FSME"
    monkeypatch.setenv("FSME_HOME", str(where))

    return where


class Desk:
    """
    A running desk, built the way `fsme desk` builds it, and how often it read
    the author's sets again.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.reads = 0

        def read_again() -> ContentLibrary:
            self.reads += 1

            return as_the_desk_does()

        loaded = as_the_desk_does()
        bench = Workbench(loaded, CONTENT_ROOT, tmp_path / "work")

        self.server = desk(
            Session(loaded, players=2, seed=7),
            bench,
            host="127.0.0.1",
            port=0,
            library=loaded,
            reload=read_again,
            interactive_priority=True,
            players=2,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        host, port = self.server.server_address[:2]
        self.address = f"http://{host}:{port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def get(self, path: str) -> Any:
        return call(self.address, path)

    def post(self, path: str, body: Any) -> Any:
        return call(self.address, path, body)

    def status(self, path: str, body: Any = None, method: str = "") -> int:
        return status_of(self.address, path, body, method)


def as_the_desk_does() -> ContentLibrary:
    return library(argparse.Namespace(content=None))


def call(address: str, path: str, body: Any = None) -> Any:
    request = urllib.request.Request(
        f"{address}{path}",
        data=None if body is None else json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            return json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        return json.loads(refused.read())


def status_of(address: str, path: str, body: Any = None, method: str = "") -> int:
    request = urllib.request.Request(
        f"{address}{path}",
        data=None if body is None else json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method=method or ("GET" if body is None else "POST"),
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            return int(answer.status)
    except urllib.error.HTTPError as refused:
        return int(refused.code)


@pytest.fixture
def running(tmp_path: Path, home: Path) -> Iterator[Desk]:
    opened = Desk(tmp_path)

    try:
        yield opened
    finally:
        opened.close()


def a_game(name: str = "Three at the table", **changes: Any) -> dict[str, Any]:
    """
    What the page sends for a custom game: three chairs, two of them pinned.
    """
    game: dict[str, Any] = {
        "name": name,
        "players": [
            {
                "name": "Zed",
                "character": CAIN,
                "starting_item": INCUBUS,
                "coins": "7",
                "loot": 1,
            },
            {"character": EVE, "coins": 0},
            {},
        ],
        "sets": ["base_game"],
        "table": {"souls_to_win": "3", "monster_slots": "", "shop_slots": None},
        "seed": "",
    }
    game.update(changes)

    return game


def saved(running: Desk, game: dict[str, Any] | None = None) -> str:
    answer = running.post("/api/games/save", {"game": game or a_game()})

    assert answer.get("saved"), answer

    return str(answer["id"])


def seats(view: dict[str, Any]) -> list[dict[str, Any]]:
    return list(view["state"]["players"])


def everything_dealt(running: Desk) -> set[str]:
    """
    The set of every card in the game being watched, wherever it lies.
    """
    state = running.server.session.game.state
    found: set[str] = set()

    piles = [
        state.loot_deck,
        state.treasure_deck,
        state.monster_deck,
        state.room_deck,
        state.loot_discard,
        state.treasure_discard,
        state.monster_discard,
        state.room_discard,
        state.treasure_shop,
        state.room_area,
        state.bonus_souls,
    ]
    piles += [slot for slot in state.monster_area]

    for player in state.players:
        piles += [player.hand, player.treasures, player.souls, player.curses]
        found.add(player.character.definition.expansion)

    for pile in piles:
        for card in pile.cards:
            definition = getattr(card, "definition", None)

            if definition is not None:
                found.add(definition.expansion)

    return found


def cards_dealt(running: Desk) -> set[str]:
    state = running.server.session.game.state
    found: set[str] = set()

    for pile in (state.loot_deck, state.loot_discard):
        found.update(card.definition.id for card in pile.cards)

    for player in state.players:
        found.update(card.definition.id for card in player.hand.cards)

    return found


# ----------------------------------------------------------------------
# Keeping a game
# ----------------------------------------------------------------------


def test_a_game_is_kept_as_an_ordinary_scenario(running: Desk, home: Path) -> None:
    identifier = saved(running)

    assert identifier == "three_at_the_table"

    kept = home / "my games" / "three_at_the_table.json"
    scenario = read_scenario(kept)

    assert scenario.name == "Three at the table"
    assert [seat.character for seat in scenario.players] == [CAIN, EVE, ""]
    assert scenario.players[0].coins == 7 and scenario.players[0].loot == 1
    assert scenario.players[1].coins == 0
    assert scenario.content.expansions == ("base_game",)
    assert scenario.table.souls_to_win == 3
    assert scenario.table.monster_slots is None
    assert scenario.seed is None

    listed = running.get("/api/games")

    assert [game["id"] for game in listed["games"]] == ["three_at_the_table"]
    assert listed["games"][0]["ready"] is True
    assert listed["games"][0]["problems"] == []
    assert listed["active"] is None


def test_a_kept_game_is_still_there_for_the_next_desk(
    tmp_path: Path, home: Path
) -> None:
    first = Desk(tmp_path)

    try:
        saved(first)
    finally:
        first.close()

    second = Desk(tmp_path)

    try:
        assert [game["name"] for game in second.get("/api/games")["games"]] == [
            "Three at the table"
        ]
    finally:
        second.close()


def test_a_kept_game_can_be_thrown_away(running: Desk) -> None:
    identifier = saved(running)

    assert running.post("/api/games/delete", {"id": identifier}) == {"deleted": True}
    assert running.get("/api/games")["games"] == []

    gone = running.post("/api/games/delete", {"id": identifier})

    assert "no custom game called" in gone["error"]
    assert running.status("/api/games/delete", {"id": identifier}) == 400


def test_a_name_already_used_is_refused_unless_replacing(running: Desk, home: Path) -> None:
    saved(running)

    again = running.post("/api/games/save", {"game": a_game(seed=4)})

    assert "already have a custom game" in again["error"]
    assert read_scenario(home / "my games" / "three_at_the_table.json").seed is None

    replaced = running.post("/api/games/save", {"game": a_game(seed=4), "replace": True})

    assert replaced["saved"] is True
    assert read_scenario(home / "my games" / "three_at_the_table.json").seed == 4


@pytest.mark.parametrize("name", ["", "   ", "!!!", None, 12])
def test_a_game_needs_a_name_it_can_be_kept_under(running: Desk, name: Any) -> None:
    answer = running.post("/api/games/save", {"game": a_game(name=name)})

    assert answer["error"]
    assert running.get("/api/games")["games"] == []


@pytest.mark.parametrize(
    ("change", "said"),
    [
        ({"players": "everybody"}, "list of seats"),
        ({"players": [{}]}, "between 2 and 4"),
        ({"players": [{}] * 5}, "between 2 and 4"),
        ({"players": [{"coins": "lots"}, {}]}, "whole number"),
        ({"players": [{"coins": -1}, {}]}, "cannot be negative"),
        ({"players": [{"loot": True}, {}]}, "whole number"),
        ({"players": [{"character": 3}, {}]}, "is text"),
        ({"players": ["Ann", {}]}, "described as an object"),
        ({"sets": "base_game"}, "sets are a list"),
        ({"seed": 1.5}, "whole number"),
        ({"table": {"monster_slots": "0"}}, "monster"),
        ({"table": []}, "table settings"),
    ],
)
def test_what_the_page_sends_is_checked_by_the_server(
    running: Desk, change: dict[str, Any], said: str
) -> None:
    answer = running.post("/api/games/save", {"game": a_game(**change)})

    assert answer.get("saved") is not True
    assert any(said in problem for problem in answer["problems"]), answer
    assert running.get("/api/games")["games"] == []


def test_a_game_that_is_not_an_object_is_refused(running: Desk) -> None:
    assert "described as an object" in running.post("/api/games/save", {"game": 3})["error"]
    assert running.status("/api/games/save", {}) == 400


def test_one_character_cannot_sit_in_two_chairs(running: Desk) -> None:
    twice = a_game(players=[{"character": CAIN}, {"character": f"  {CAIN} "}])
    answer = running.post("/api/games/save", {"game": twice})

    assert any("two chairs" in problem for problem in answer["problems"]), answer
    assert running.get("/api/games")["games"] == []


def test_a_file_that_is_not_a_game_is_listed_and_refused_rather_than_fatal(
    running: Desk, home: Path
) -> None:
    folder = home / "my games"
    folder.mkdir(parents=True)
    (folder / "torn.json").write_text("{ this is not json", encoding="utf-8")
    (folder / "twice.json").write_text(
        json.dumps(
            {
                "format": "fsme-scenario",
                "version": 1,
                "name": "Twice",
                "players": [{"character": CAIN}, {"character": CAIN}],
            }
        ),
        encoding="utf-8",
    )

    listed = {game["id"]: game for game in running.get("/api/games")["games"]}

    assert listed["torn"]["ready"] is False
    assert "not JSON" in listed["torn"]["problems"][0]
    assert listed["twice"]["ready"] is False
    assert any("two chairs" in problem for problem in listed["twice"]["problems"])

    before = running.get("/api/view?since=0")

    for broken in ("torn", "twice"):
        assert running.status("/api/games/start", {"id": broken}) == 400

    assert running.get("/api/view?since=0") == before


@pytest.mark.parametrize(
    ("seat", "sets", "said"),
    [
        ({"character": "characters-nowhere-nobody"}, ["base_game"], "not in the chosen sets"),
        ({"starting_item": "starting_items-nowhere-nothing"}, ["base_game"], "starting item"),
        ({}, ["base_game", "no_such_set"], "is not loaded"),
        ({"character": "characters-four_souls-guppy"}, ["base_game"], "not in the chosen sets"),
    ],
)
def test_a_game_the_content_cannot_deal_says_why_before_and_at_start(
    running: Desk, seat: dict[str, Any], sets: list[str], said: str
) -> None:
    identifier = saved(running, a_game(players=[seat, {}], sets=sets))

    listed = running.get("/api/games")["games"][0]

    assert listed["ready"] is False
    assert any(said in problem for problem in listed["problems"]), listed

    before = running.get("/api/view?since=0")
    refused = running.post("/api/games/start", {"id": identifier})

    assert any(said in problem for problem in refused["problems"]), refused
    assert running.get("/api/view?since=0") == before
    assert running.get("/api/games")["active"] is None


def test_the_form_is_offered_what_the_content_holds(running: Desk) -> None:
    offered = running.get("/api/games/catalogue")

    assert (offered["least"], offered["most"]) == (2, 4)

    base = next(one for one in offered["sets"] if one["id"] == "base_game")

    assert CAIN in [one["id"] for one in base["characters"]]
    assert INCUBUS in [one["id"] for one in base["starting_items"]]


# ----------------------------------------------------------------------
# Dealing a game
# ----------------------------------------------------------------------


def test_a_custom_game_is_dealt_as_it_was_set_up(running: Desk) -> None:
    identifier = saved(running)
    started = running.post("/api/games/start", {"id": identifier, "seed": 11})

    assert started["active"] == {"id": identifier, "name": "Three at the table"}

    dealt = seats(started["view"])

    assert len(dealt) == 3
    assert dealt[0]["name"] == "Zed"
    assert dealt[0]["character"]["id"] == CAIN
    assert dealt[0]["pennies"] == 7
    assert len(dealt[0]["hand"]) == 1
    assert [item["id"] for item in dealt[0]["treasures"]] == [INCUBUS]
    assert dealt[1]["character"]["id"] == EVE
    assert dealt[1]["pennies"] == 0
    assert [item["id"] for item in dealt[1]["treasures"]] == [THE_CURSE]
    assert dealt[2]["character"]["id"] not in (CAIN, EVE)

    state = running.server.session.game.state

    assert state.souls_to_win == 3
    assert everything_dealt(running) == {"base_game"}
    assert running.get("/api/games")["active"]["id"] == identifier


def test_the_same_game_from_the_same_seed_is_the_same_deal(running: Desk) -> None:
    identifier = saved(running)

    once = running.post("/api/games/start", {"id": identifier, "seed": 23})["view"]
    running.post("/api/games/start", {"id": identifier, "seed": 99})
    again = running.post("/api/games/start", {"id": identifier, "seed": 23})["view"]

    assert once["state"] == again["state"]


def test_the_seed_from_watch_wins_over_the_one_kept(running: Desk) -> None:
    identifier = saved(running, a_game(seed=5))

    kept = running.post("/api/games/start", {"id": identifier})
    asked = running.post("/api/games/start", {"id": identifier, "seed": "9"})

    assert kept["view"]["state"]["seed"] == 5
    assert asked["view"]["state"]["seed"] == 9

    unseeded = saved(running, a_game(name="No seed kept"))

    assert running.post("/api/games/start", {"id": unseeded})["view"]["state"]["seed"] == 0
    assert "whole number" in running.post(
        "/api/games/start", {"id": identifier, "seed": "nine"}
    )["error"]


def test_dealing_again_keeps_the_custom_game(running: Desk) -> None:
    identifier = saved(running)
    running.post("/api/games/start", {"id": identifier, "seed": 3})

    # What the page sends for chairs and sets belongs to an ordinary game.
    again = running.post(
        "/api/restart", {"seed": 4, "players": 2, "sets": ["base_game", "four_souls"]}
    )

    dealt = seats(again["view"])

    assert again["view"]["state"]["seed"] == 4
    assert len(dealt) == 3
    assert [one["character"]["id"] for one in dealt[:2]] == [CAIN, EVE]
    assert everything_dealt(running) == {"base_game"}
    assert running.get("/api/games")["active"]["id"] == identifier


def test_leaving_a_custom_game_deals_an_ordinary_one(running: Desk) -> None:
    identifier = saved(running)
    running.post("/api/games/start", {"id": identifier, "seed": 3})

    left = running.post("/api/games/leave", {"seed": 8, "players": 2, "sets": []})

    assert left["view"]["state"]["seed"] == 8
    assert len(seats(left["view"])) == 2
    assert running.server.session.scenario is None
    assert running.get("/api/games")["active"] is None

    again = running.post("/api/restart", {"seed": 9, "players": 3, "sets": []})

    assert len(seats(again["view"])) == 3, "the old chairs did not come back"
    assert running.server.session.scenario is None


def test_an_ordinary_restart_still_does_what_it_did(running: Desk) -> None:
    narrowed = running.post(
        "/api/restart", {"seed": 2, "players": 3, "sets": ["base_game"]}
    )

    assert len(seats(narrowed["view"])) == 3
    assert everything_dealt(running) == {"base_game"}
    assert running.get("/api/content")["chosen"] == ["base_game"]

    before = running.get("/api/view?since=0")
    refused = running.post("/api/restart", {"seed": 2, "sets": ["no_such_set"]})

    assert "no set called 'no_such_set'" in refused["error"]
    assert running.get("/api/view?since=0") == before

    assert running.status("/api/restart", {"players": 9}) == 400
    assert running.status("/api/restart", {"players": "many"}) == 400
    assert running.get("/api/view?since=0") == before

    widened = running.post("/api/restart", {"seed": 2, "sets": []})

    assert len(seats(widened["view"])) == 3
    assert running.get("/api/content")["chosen"] == []


# ----------------------------------------------------------------------
# A set written while the desk runs
# ----------------------------------------------------------------------


def test_a_set_written_after_the_desk_started_can_be_watched(running: Desk) -> None:
    """
    The regression: a set made in a running desk was refused by Watch with
    "no set called ... was loaded" until the desk was started again.
    """
    made = running.post("/api/sets/new", {"name": "Late Set"})
    kept = running.post("/api/cards/save", dict(A_PENNY, set=made["id"]))

    assert kept["saved"], kept

    offered = [one["id"] for one in running.get("/api/content")["sets"]]

    assert "late_set" in offered

    dealt = running.post("/api/restart", {"seed": 1, "sets": ["base_game", "late_set"]})

    assert "view" in dealt, dealt
    assert kept["card"]["id"] in cards_dealt(running)
    assert everything_dealt(running) == {"base_game", "late_set"}


def test_a_custom_game_can_use_a_set_written_after_the_desk_started(running: Desk) -> None:
    made = running.post("/api/sets/new", {"name": "Late Set"})
    kept = running.post("/api/cards/save", dict(A_PENNY, set=made["id"]))

    late = [one for one in running.get("/api/games/catalogue")["sets"] if one["id"] == "late_set"]

    assert late, "the form is offered the new set"

    identifier = saved(running, a_game(name="With mine", sets=["base_game", "late_set"]))
    started = running.post("/api/games/start", {"id": identifier, "seed": 6})

    assert "view" in started, started
    assert kept["card"]["id"] in cards_dealt(running)


def test_the_sets_are_read_again_only_when_they_change(running: Desk) -> None:
    for _ in range(3):
        running.get("/api/content")
        running.post("/api/restart", {"seed": 1})

    assert running.reads == 0, "nothing on disk moved"

    made = running.post("/api/sets/new", {"name": "Mine"})
    running.get("/api/content")
    running.get("/api/content")

    assert running.reads == 1

    running.post("/api/cards/save", dict(A_PENNY, set=made["id"]))
    running.post("/api/restart", {"seed": 1, "sets": ["base_game", "mine"]})

    assert running.reads == 2

    changed = dict(A_PENNY, set=made["id"], name="Luckier Penny")
    running.post("/api/cards/save", changed)
    running.get("/api/content")

    assert running.reads == 3


def test_a_set_that_will_not_load_is_reported_and_the_game_kept(
    running: Desk, home: Path
) -> None:
    made = running.post("/api/sets/new", {"name": "Broken"})
    before = running.get("/api/view?since=0")

    (home / "my sets" / made["id"] / "cards" / "bad.json").write_text(
        "{ not json", encoding="utf-8"
    )

    answer = running.post("/api/restart", {"seed": 1})

    assert answer["error"]
    assert running.get("/api/view?since=0") == before
    assert running.status("/api/content") == 400


# ----------------------------------------------------------------------
# Where custom games are not offered
# ----------------------------------------------------------------------


def test_the_plain_game_server_offers_no_custom_games(home: Path) -> None:
    loaded = as_the_desk_does()
    server = GameServer(("127.0.0.1", 0), Session(loaded, players=2, seed=7))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address[:2]
    address = f"http://{host}:{port}"

    try:
        assert status_of(address, "/api/games") == 404
        assert status_of(address, "/api/games/start", {"id": "x"}) == 404
        assert "view" in call(address, "/api/restart", {"seed": 3})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_a_desk_built_without_a_library_offers_no_custom_games(
    tmp_path: Path, home: Path
) -> None:
    loaded = as_the_desk_does()
    bench = Workbench(loaded, CONTENT_ROOT, tmp_path / "work")
    server = desk(Session(loaded, players=2, seed=7), bench, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address[:2]
    address = f"http://{host}:{port}"

    try:
        assert status_of(address, "/api/games", method="HEAD") == 404
        assert status_of(address, "/api/autoplay", method="HEAD") == 200
        assert "view" in call(address, "/api/restart", {"seed": 3, "players": 3})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_the_running_desk_says_it_offers_custom_games(running: Desk) -> None:
    assert running.status("/api/games", method="HEAD") == 200


def test_the_watch_page_asks_before_showing_custom_games() -> None:
    page = PAGE.read_text("utf-8")

    assert '<button id="custom-open" hidden' in page
    assert '<section id="custom-panel" hidden>' in page
    assert 'fetch("/api/games", { method: "HEAD" })' in page
    assert '"/api/games/start"' in page
    assert '"/api/games/save"' in page
    assert '"/api/games/leave"' in page


# ----------------------------------------------------------------------
# The whole path, the way somebody would walk it
# ----------------------------------------------------------------------


def test_the_whole_path_from_a_new_card_to_a_custom_game_played_out(
    running: Desk,
) -> None:
    # A set and a card, made in the running desk.
    made = running.post("/api/sets/new", {"name": "Demo Set"})
    card = running.post("/api/cards/save", dict(A_PENNY, set=made["id"]))

    assert card["saved"], card

    # A custom game that deals from it, set up without starting the desk again.
    offered = running.get("/api/games/catalogue")

    assert "demo_set" in [one["id"] for one in offered["sets"]]

    game = a_game(name="Demo", sets=["base_game", "demo_set"], seed="41")
    identifier = saved(running, game)

    assert running.get("/api/games")["games"][0]["ready"] is True

    # Dealt in Watch, and dealt as it was set up.
    started = running.post("/api/games/start", {"id": identifier})
    dealt = seats(started["view"])

    assert started["view"]["state"]["seed"] == 41
    assert [dealt[0]["character"]["id"], dealt[1]["character"]["id"]] == [CAIN, EVE]
    assert dealt[0]["pennies"] == 7
    assert card["card"]["id"] in cards_dealt(running)

    opening = started["view"]["state"]

    # The bots play it, and the game goes on without a fault.
    played = 0

    for _ in range(6):
        moved = running.post("/api/autoplay", {"moves": 32})

        assert "view" in moved, moved

        played += moved["moved"]

        if moved["over"]:
            break

    assert played > 0
    assert running.get("/api/view?since=0")["history_length"] > 1

    # And the same game from the same seed is the same deal.
    again = running.post("/api/restart", {"seed": 41})

    assert again["view"]["state"] == opening
