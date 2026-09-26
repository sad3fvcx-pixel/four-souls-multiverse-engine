"""
Scenarios: the configuration a game starts from.

The first test in this file is the one the other tests exist to protect. A
scenario is a new argument on the one door every game in the project comes
through, and if that argument changes anything when nobody passes it, every
measurement FSME has ever taken stops being comparable with every measurement
it takes next. So: an empty scenario deals the same game, asserted on the whole
journal and not on the winner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fsme.api import load_content
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.journal import JournalKeeper
from fsme.lab.bot import HeuristicBot
from fsme.lab.simulation import ScriptedAgent
from fsme.lab.simulation.runner import NAMES, _whose_move
from fsme.rules import STARTING_COINS, STARTING_HAND_SIZE, SetupError
from fsme.scenario import Content, Scenario, ScenarioError, Seat, Table, parse
from fsme.scenario import load as load_scenario
from fsme.state import GameState

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


def a_game(library: ContentLibrary, seed: int = 7, players: int = 2, **kwargs):
    return Game.from_content(library, list(NAMES[:players]), seed=seed, **kwargs)


def played(game: Game, seed: int, players: int = 2, steps: int = 20000):
    """
    Play a game out and hand back the journal of it.
    """
    keeper = JournalKeeper(game)
    agent = ScriptedAgent(seed)
    bot = HeuristicBot(seed)

    for _ in range(steps):
        if game.is_over:
            break

        speaking = _whose_move(game)
        thought = (bot if speaking in range(players) else agent).choose(
            game, seats=(speaking,)
        )

        if thought is None:
            break

        if not keeper.submit(thought[0], label=thought[1]).accepted:
            break

    return keeper.journal


def scenario_file(tmp_path: Path, data: dict) -> Path:
    where = tmp_path / "scenario.json"
    where.write_text(json.dumps(data), encoding="utf-8")

    return where


EMPTY = {"format": "fsme-scenario", "version": 1}


# ----------------------------------------------------------------------
# 1. Nothing asked for, nothing changed
# ----------------------------------------------------------------------


@pytest.mark.parametrize("seed", (3, 11, 42))
def test_a_game_with_no_scenario_is_the_game_it_always_was(
    everything: ContentLibrary, seed: int
) -> None:
    """
    The guarantee the rest of the engine rests on.

    Compared entry by entry with digests and events, not on the winner: two
    games can end the same way and be different games.
    """
    without = played(a_game(everything, seed=seed), seed)
    empty = played(a_game(everything, seed=seed, scenario=Scenario()), seed)

    assert empty.to_dict() == without.to_dict()


def test_an_empty_scenario_knows_it_is_empty() -> None:
    assert Scenario().is_empty
    assert Scenario(name="named", description="described").is_empty
    assert not Scenario(seed=4).is_empty
    assert not Scenario(table=Table(shop_slots=0)).is_empty


# ----------------------------------------------------------------------
# 2, 3. A named character and a named item
# ----------------------------------------------------------------------

ISAAC = "characters-base_game-isaac"
CAIN = "characters-base_game-cain"
THE_D6 = "starting_items-base_game-the_d6"
THE_CURSE = "starting_items-base_game-the_curse"


def test_a_scenario_deals_the_character_it_names(
    everything: ContentLibrary,
) -> None:
    scenario = Scenario(
        players=(Seat(character=ISAAC), Seat(character=CAIN)),
    )

    game = a_game(everything, scenario=scenario)

    dealt = [player.character.definition.id for player in game.state.players]

    assert dealt == [ISAAC, CAIN]


def test_a_seat_that_asks_for_nothing_is_dealt_as_usual(
    everything: ContentLibrary,
) -> None:
    """
    Pinning one seat must not pin the others.
    """
    game = a_game(
        everything, players=3, scenario=Scenario(players=(Seat(character=ISAAC),))
    )

    dealt = [player.character.definition.id for player in game.state.players]

    assert dealt[0] == ISAAC
    assert ISAAC not in dealt[1:], "the pinned card was not dealt twice"
    assert len(set(dealt)) == 3


def test_a_scenario_deals_the_starting_item_it_names(
    everything: ContentLibrary,
) -> None:
    """
    Instead of the character's printed one, not as well as it.
    """
    printed = a_game(everything, scenario=Scenario(players=(Seat(character=ISAAC),)))
    ordinary = [
        card.definition.id for card in printed.state.player(0).treasures.cards
    ]

    assert ordinary == [THE_D6], "Isaac starts with The D6"

    swapped = a_game(
        everything,
        scenario=Scenario(
            players=(Seat(character=ISAAC, starting_item=THE_CURSE),),
        ),
    )
    held = [card.definition.id for card in swapped.state.player(0).treasures.cards]

    assert held == [THE_CURSE]


def test_a_character_that_is_not_in_the_content_is_refused(
    everything: ContentLibrary,
) -> None:
    with pytest.raises(SetupError) as raised:
        a_game(everything, scenario=Scenario(players=(Seat(character="nope"),)))

    assert "not in the loaded content" in str(raised.value)


def test_an_item_that_is_not_a_starting_item_is_refused(
    everything: ContentLibrary,
) -> None:
    with pytest.raises(SetupError) as raised:
        a_game(
            everything,
            scenario=Scenario(players=(Seat(starting_item="loot_deck-1-base_game-a_penny"),)),
        )

    assert "not a starting item" in str(raised.value)


# ----------------------------------------------------------------------
# 4. Openings
# ----------------------------------------------------------------------


def hands_after_the_deal(game: Game) -> list[int]:
    """
    What each seat holds once the game has opened.

    `start_game` deals the opening hands *and* runs the first turn's loot step,
    so the seat that goes first is holding one more card than it was dealt.
    That is the game working, and a test that forgot it would be measuring the
    loot step and calling it the opening.
    """
    first = game.state.turn.active_player

    return [
        player.hand_size - (1 if player.player_id == first else 0)
        for player in game.state.players
    ]


def test_a_scenario_deals_the_opening_it_asks_for(
    everything: ContentLibrary,
) -> None:
    scenario = Scenario(
        players=(Seat(coins=10, loot=1), Seat(coins=10, loot=1)),
    )

    game = a_game(everything, scenario=scenario)
    game.start()

    assert [player.pennies for player in game.state.players] == [10, 10]
    assert hands_after_the_deal(game) == [1, 1]


def test_an_ordinary_game_still_deals_the_printed_opening(
    everything: ContentLibrary,
) -> None:
    game = a_game(everything)
    game.start()

    for player in game.state.players:
        assert player.pennies == STARTING_COINS

    assert hands_after_the_deal(game) == [STARTING_HAND_SIZE] * 2


def test_the_state_defaults_agree_with_the_rulebook() -> None:
    """
    The numbers are written twice — in `rules.constants` where a reader checks
    them against the rulebook, and on GameState where a game carries its own.
    `state` cannot import `rules`, so nothing but this stops them drifting.
    """
    fresh = GameState()

    assert fresh.starting_coins == STARTING_COINS
    assert fresh.starting_hand == STARTING_HAND_SIZE


def test_each_seat_is_dealt_its_own_opening(everything: ContentLibrary) -> None:
    """
    The seats may disagree, and that is the point of asking per seat.
    """
    game = a_game(
        everything,
        players=3,
        scenario=Scenario(
            players=(
                Seat(coins=3, loot=3),
                Seat(coins=5, loot=1),
                Seat(coins=0, loot=7),
            ),
        ),
    )
    game.start()

    assert [player.pennies for player in game.state.players] == [3, 5, 0]
    assert hands_after_the_deal(game) == [3, 1, 7]


def test_a_seat_that_names_no_opening_takes_the_table_s(
    everything: ContentLibrary,
) -> None:
    """
    Naming one seat's opening must not silently change anybody else's.
    """
    game = a_game(
        everything,
        players=3,
        scenario=Scenario(players=(Seat(), Seat(coins=9), Seat())),
    )
    game.start()

    assert [player.pennies for player in game.state.players] == [
        STARTING_COINS,
        9,
        STARTING_COINS,
    ]
    assert hands_after_the_deal(game) == [STARTING_HAND_SIZE] * 3


# ----------------------------------------------------------------------
# 5. The same scenario and seed name one game
# ----------------------------------------------------------------------


def test_a_scenario_and_a_seed_name_one_game(everything: ContentLibrary) -> None:
    """
    Run three times and compared in full — commands, digests and every field of
    every event.
    """
    scenario = Scenario(
        content=Content(expansions=("base_game",)),
        table=Table(shop_slots=0),
        players=(Seat(character=ISAAC), Seat(character=CAIN)),
    )

    runs = [
        played(a_game(everything, seed=19, scenario=scenario), 19)
        for _ in range(3)
    ]

    assert runs[0].entries, "a game happened"

    for other in runs[1:]:
        assert other.to_dict() == runs[0].to_dict()


def test_pinning_a_character_does_not_move_the_rest_of_the_deal(
    everything: ContentLibrary,
) -> None:
    """
    The character shuffle happens either way, in the same place.

    So a scenario that pins the characters the shuffle would have dealt anyway
    deals exactly the game the seed deals on its own — the RNG stands in the
    same place afterwards, and everything from the board onwards follows.
    """
    ordinary = a_game(everything, seed=23)
    dealt = [player.character.definition.id for player in ordinary.state.players]

    same = a_game(
        everything,
        seed=23,
        scenario=Scenario(players=tuple(Seat(character=cid) for cid in dealt)),
    )

    # The commands and the positions, not the whole journal: the two journals
    # differ in what they say about how the game was set up, which is the
    # point. What must not differ is the game.
    pinned = played(same, 23).to_dict()["entries"]
    dealt_out = played(ordinary, 23).to_dict()["entries"]

    assert pinned == dealt_out


# ----------------------------------------------------------------------
# 6. One process, two scenarios
# ----------------------------------------------------------------------


def test_a_scenario_does_not_leak_into_the_next_game(
    everything: ContentLibrary,
) -> None:
    """
    The test that would have caught writing `rules.constants` instead of state.

    It would have passed everywhere else: a test process plays one game, and a
    study worker plays a thousand.
    """
    rich = a_game(
        everything,
        seed=5,
        scenario=Scenario(players=(Seat(coins=10), Seat(coins=10))),
    )
    rich.start()

    assert rich.state.player(0).pennies == 10

    plain = a_game(everything, seed=5)
    plain.start()

    assert plain.state.player(0).pennies == STARTING_COINS

    modest = a_game(
        everything,
        seed=5,
        scenario=Scenario(players=(Seat(coins=3), Seat(coins=3))),
    )
    modest.start()

    assert modest.state.player(0).pennies == 3


def test_narrowing_the_content_does_not_change_the_library(
    everything: ContentLibrary,
) -> None:
    """
    A scenario rearranges the library it is handed; it must not edit it.
    """
    before = len(everything.definitions())

    game = a_game(
        everything,
        scenario=Scenario(content=Content(expansions=("base_game",))),
    )

    assert len(game.runtime.cards) < before
    assert len(everything.definitions()) == before


# ----------------------------------------------------------------------
# Content selection
# ----------------------------------------------------------------------


def test_a_scenario_deals_only_the_sets_it_names(
    everything: ContentLibrary,
) -> None:
    game = a_game(
        everything,
        scenario=Scenario(content=Content(expansions=("base_game",))),
    )

    expansions = {
        card.definition.expansion for card in game.state.loot_deck.cards
    }

    assert expansions == {"base_game"}


def test_a_scenario_leaves_out_the_cards_it_excludes(
    everything: ContentLibrary,
) -> None:
    penny = "loot_deck-1-base_game-a_penny"

    game = a_game(
        everything,
        scenario=Scenario(
            content=Content(expansions=("base_game",), exclude_cards=(penny,)),
        ),
    )

    dealt = {card.definition.id for card in game.state.loot_deck.cards}

    assert penny not in dealt


def test_a_set_that_is_not_there_is_named(everything: ContentLibrary) -> None:
    from fsme.content import ContentNotFoundError

    with pytest.raises(ContentNotFoundError) as raised:
        a_game(
            everything,
            scenario=Scenario(content=Content(expansions=("no_such_set",))),
        )

    assert "no_such_set" in str(raised.value)


# ----------------------------------------------------------------------
# 7. The file, and every way of being wrong
# ----------------------------------------------------------------------


def test_an_empty_scenario_file_reads(tmp_path: Path) -> None:
    scenario = load_scenario(scenario_file(tmp_path, EMPTY))

    assert scenario.is_empty


def test_a_scenario_round_trips_through_a_file(tmp_path: Path) -> None:
    from fsme.scenario import save

    scenario = Scenario(
        name="A name",
        description="A description",
        seed=8,
        interactive_priority=True,
        content=Content(expansions=("base_game",), exclude_cards=("x",)),
        table=Table(souls_to_win=2, monster_slots=1, shop_slots=0),
        players=(Seat(name="Ann", character=ISAAC, starting_item=THE_D6, coins=1, loot=1),),
    )

    where = save(scenario, tmp_path / "kept.json")

    assert load_scenario(where) == scenario


def test_an_empty_scenario_writes_only_what_it_is() -> None:
    """
    A file meant to be read by a person does not open with a page of nulls.
    """
    assert Scenario().to_dict() == EMPTY


@pytest.mark.parametrize(
    ("data", "expected"),
    (
        ({"version": 1}, "does not say what it is"),
        ({"format": "something-else", "version": 1}, "is written in format"),
        ({"format": "fsme-scenario"}, "does not say which version"),
        ({"format": "fsme-scenario", "version": 99}, "this build reads version"),
        ({"format": "fsme-scenario", "version": "1"}, "must be a whole number"),
        (
            {**EMPTY, "table": {"monster_slots": 0}},
            "the first monster revealed makes a slot for itself",
        ),
        ({**EMPTY, "players": []}, "leaves the key out"),
        ({**EMPTY, "monster_slots": 2}, "does not know"),
        ({**EMPTY, "table": {"shop_slots": -1}}, "the least it can be"),
        ({**EMPTY, "content": {"sets": []}}, "does not know"),
        ({**EMPTY, "players": [{"seat": 1}]}, "does not know"),
        (
            {**EMPTY, "players": [{"character": ISAAC}, {"character": ISAAC}]},
            "cannot sit in two chairs",
        ),
        ({**EMPTY, "interactive_priority": "yes"}, "true or false"),
        ({**EMPTY, "content": {"expansions": [7]}}, "every entry is an identifier"),
        ({**EMPTY, "seed": "soon"}, "must be a whole number"),
        ({**EMPTY, "table": []}, "table must be an object"),
        ([], "a scenario must be an object"),
    ),
)
def test_a_scenario_that_is_wrong_says_how(data: object, expected: str) -> None:
    with pytest.raises(ScenarioError) as raised:
        parse(data)

    assert expected in str(raised.value)


def test_a_file_that_is_not_json_is_refused(tmp_path: Path) -> None:
    where = tmp_path / "broken.json"
    where.write_text("{not json", encoding="utf-8")

    with pytest.raises(ScenarioError) as raised:
        load_scenario(where)

    assert "is not JSON" in str(raised.value)


def test_a_file_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ScenarioError) as raised:
        load_scenario(tmp_path / "absent.json")

    assert "cannot be read" in str(raised.value)


def test_every_problem_is_reported_at_once() -> None:
    """
    Somebody typing a file wants to see everything wrong with it, not the first
    thing — the same courtesy the content pipeline extends.
    """
    with pytest.raises(ScenarioError) as raised:
        parse({"format": "fsme-scenario", "version": 1, "seed": "x", "table": {"monster_slots": 0}})

    said = str(raised.value)

    assert "must be a whole number" in said
    assert "monster" in said
    assert len(said.splitlines()) >= 2


# ----------------------------------------------------------------------
# The table
# ----------------------------------------------------------------------


def test_the_table_numbers_reach_the_game(everything: ContentLibrary) -> None:
    game = a_game(
        everything,
        scenario=Scenario(
            table=Table(souls_to_win=2, monster_slots=1, shop_slots=0),
        ),
    )

    state = game.state

    assert state.souls_to_win == 2
    assert state.monster_slots == 1
    assert state.shop_slots == 0
    assert len(state.active_monsters) == 1
    assert len(state.treasure_shop) == 0


def test_a_game_without_a_shop_still_finishes(everything: ContentLibrary) -> None:
    scenario = Scenario(table=Table(shop_slots=0))

    game = a_game(everything, seed=5, scenario=scenario)
    game.start()
    journal = played(game, 5)

    assert game.is_over
    assert len(game.state.treasure_shop) == 0
    assert journal.entries
