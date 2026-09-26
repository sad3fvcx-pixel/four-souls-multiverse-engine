"""
Saving a game and loading it back.

SAVE_SYSTEM.md asks for a save that is lossless: loading one must produce a
game that continues exactly as the saved one would have. That is a claim about
the future, not about the file, so it is tested as one — a saved game and the
game it was saved from are played on side by side, and they must stay the same
game.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

import pytest
from test_soak import play, step

from fsme import __version__
from fsme.api import Session
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.game import Game
from fsme.replay import state_digest
from fsme.rng.rng import RNG
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.serialization import SAVE_FORMAT_VERSION, SaveError, load_game, save_game

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)


def settle(game: Game) -> None:
    """
    Answer whatever the game is waiting on before it is saved.

    A save is taken between actions. A game suspended inside an ability — a
    player choosing which loot card their death costs them — is refused, on
    purpose, and a test about round trips has to get past that first.
    """
    while game.runtime.awaiting_decision is not None:
        decision = game.runtime.awaiting_decision

        # As many as the question asks for, taken from the top: a test about
        # round trips is not about which options were picked.
        count = len(decision.options)
        wanted = max(0, min(decision.minimum, count))

        assert game.submit(
            Command(
                type=CommandType.CHOOSE_TARGET,
                player=decision.player,
                payload={"choices": list(range(wanted))},
            )
        ).accepted


def written(game: Game) -> dict[str, Any]:
    """
    Save a game and read it back through JSON, as a file would.
    """
    settle(game)

    return dict(json.loads(json.dumps(game.save(engine_version="test"))))


def test_a_fresh_game_survives_a_round_trip(everything: ContentLibrary) -> None:
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    back = Game.load(written(game), everything)

    assert state_digest(back.state) == state_digest(game.state)


@pytest.mark.parametrize("seed", (5, 11, 23))
def test_a_game_in_progress_survives_a_round_trip(
    everything: ContentLibrary, seed: int
) -> None:
    game = play(everything, seed, 3, steps=80)

    back = Game.load(written(game), everything)

    assert state_digest(back.state) == state_digest(game.state)


@pytest.mark.parametrize("seed", (5, 11))
def test_a_loaded_game_plays_on_the_same(
    everything: ContentLibrary, seed: int
) -> None:
    """
    The claim a save actually makes: what happens next is the same.
    """
    game = play(everything, seed, 3, steps=80)
    back = Game.load(written(game), everything)

    here, there = random.Random(seed + 1), random.Random(seed + 1)

    for _ in range(80):
        step(game, here)
        step(back, there)

    assert state_digest(back.state) == state_digest(game.state)


def test_the_cards_come_back_as_themselves(everything: ContentLibrary) -> None:
    game = play(everything, 5, 3, steps=60)
    back = Game.load(written(game), everything)

    for before, after in zip(game.state.players, back.state.players, strict=True):
        assert [card.instance_id for card in before.hand.cards] == [
            card.instance_id for card in after.hand.cards
        ]
        assert [card.id for card in before.treasures.cards] == [
            card.id for card in after.treasures.cards
        ]

    # One object per identifier, and the loaded game points at its own cards.
    seen: dict[str, Any] = {}

    for zone in (
        back.state.loot_deck,
        back.state.treasure_deck,
        back.state.active_monsters,
        *(player.hand for player in back.state.players),
        *(player.treasures for player in back.state.players),
    ):
        for card in zone.cards:
            assert card.instance_id not in seen, "one card, two objects"
            seen[card.instance_id] = card

    # Equal by value, and never the same object: a loaded game shares nothing
    # with the one it was saved from.
    for card in back.state.active_monsters.cards:
        assert all(card is not other for other in game.state.active_monsters.cards)


def test_what_a_card_did_to_another_card_is_kept(everything: ContentLibrary) -> None:
    """
    Counters, copies, tapping and the rest are the card's history, not its face.
    """
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    settle(game)

    # Whoever has an item: not every character begins with one, and this test
    # is about what a save keeps, not about who was dealt what.
    owner = next(
        player for player in game.state.players if player.treasures.cards
    )
    item = owner.treasures.cards[0]

    item.tapped = True
    item.counters["gold"] = 2
    item.eternal = True
    item.silenced_while = "poo"
    item.recharge_skipped = True
    item.copy_of = game.runtime.cards.get("treasure_deck-passive_items-base_game-breakfast")
    item.copy_expires = "end_of_turn"

    back = Game.load(written(game), everything)

    restored = back.state.player(owner.player_id).treasures.cards[0]

    assert restored.tapped
    assert restored.counters == {"gold": 2}
    assert restored.eternal
    assert restored.silenced_while == "poo"
    assert restored.recharge_skipped
    assert restored.copy_of is not None
    assert restored.copy_of.id == item.copy_of.id
    assert restored.copy_expires == "end_of_turn"


def test_what_the_game_owes_is_kept(everything: ContentLibrary) -> None:
    """
    Promises, watchers, shields, obligations and bonuses all outlive a save.
    """
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    # A deal may open with a question — a character choosing its starting item
    # — and answering it is not what this test is about. What the game owes is
    # recorded after the table has settled.
    settle(game)

    context = game.runtime.context

    context._set_actor(0)
    context.apply("prevent_next_damage", [game.state.player(0)], amount=1, label="hat")
    context.apply(
        "promise",
        [],
        event="before_loot_draw",
        changes={"count": {"factor": 2}},
    )
    context.apply(
        "watch_for",
        [],
        event="after_roll",
        effects=[{"draw_loot": 1}],
    )
    context.apply("add_modifier", [game.state.player(0)], stat="attack", amount=1)
    context.apply("require_attack", [], times=1)
    game.runtime.run()

    back = Game.load(written(game), everything)

    assert len(back.state.shields) == 1
    assert back.state.shields[0].label == "hat"

    assert len(back.state.promises) == 1
    assert back.state.promises[0].changes == {"count": {"factor": 2}}

    assert len(back.state.watchers) == 1
    assert back.state.watchers[0].event == "after_roll"

    assert [(m.stat, m.amount) for m in back.state.modifiers] == [("attack", 1)]
    assert len(back.state.turn.obligations) == 1


def test_a_game_waiting_inside_an_ability_will_not_be_saved(
    everything: ContentLibrary,
) -> None:
    """
    An ability halfway through is the interpreter's working, not the game's.

    It is rebuilt from the card every time an ability resolves and is written
    down nowhere, so a save taken now could not promise to continue the same
    way. The engine says so instead of pretending.
    """
    game = Game.from_content(everything, ["Ann", "Bo", "Cy"], seed=3)

    assert game.start().accepted

    while game.runtime.awaiting_decision is None:
        # Bomb! asks who to throw it at, which suspends the ability.
        card = game.runtime.cards.get("loot_deck-bombs-base_game-bomb")

        from fsme.cards import CardInstance

        bomb = CardInstance(
            definition=card,
            instance_id=game.state.ids.allocate("loot"),
            controller=0,
            owner=0,
        )

        game.state.player(0).hand.add_top(bomb)
        game.state.player(0).additional_loot_plays += 1

        index = list(game.state.player(0).hand.cards).index(bomb)

        assert game.submit(
            Command(type=CommandType.PLAY_LOOT, player=0, payload={"index": index})
        ).accepted

    with pytest.raises(SaveError, match="waiting inside an ability"):
        game.save()


def test_a_save_from_another_format_is_refused(everything: ContentLibrary) -> None:
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    data = written(game)
    data["format"] = "not-this-one"

    with pytest.raises(SaveError, match="format"):
        Game.load(data, everything)


def test_a_save_naming_a_card_the_content_lacks_is_refused(
    everything: ContentLibrary,
) -> None:
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    data = written(game)
    data["zones"]["loot_deck"]["cards"][0]["id"] = "nothing.like.this"

    with pytest.raises(SaveError, match="does not have"):
        Game.load(data, everything)


def test_a_save_holding_a_copy_of_a_card_the_content_lacks_is_refused(
    everything: ContentLibrary,
) -> None:
    """
    A copy is written down by the name of the card it copies, and that card is
    looked up only once every card is back. Loaded against content without it,
    the save is refused the way a card the content lacks is refused.

    The original is chosen from cards the save does not hold, so that it is the
    copy that goes missing and not a card in a zone.
    """
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    settle(game)

    held: set[str] = set()

    def gather(value: Any) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("id"), str):
                held.add(value["id"])

            for item in value.values():
                gather(item)
        elif isinstance(value, list):
            for item in value:
                gather(item)

    gather(written(game))

    original = next(
        card_id
        for card_id in sorted(everything.registry().ids())
        if card_id not in held
    )

    owner = next(player for player in game.state.players if player.treasures.cards)
    owner.treasures.cards[0].copy_of = game.runtime.cards.get(original)

    data = written(game)

    back = Game.load(data, everything)
    restored = back.state.player(owner.player_id).treasures.cards[0]

    assert restored.copy_of is not None
    assert restored.copy_of.id == original

    with pytest.raises(SaveError, match="does not have"):
        Game.load(data, everything.without([original]))


def test_the_format_is_written_down(everything: ContentLibrary) -> None:
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    data = written(game)

    assert data["format"] == SAVE_FORMAT_VERSION
    assert data["engine"] == "test"
    assert data["seed"] == 3


def test_a_save_is_stamped_with_the_engine_that_wrote_it(
    everything: ContentLibrary,
) -> None:
    """
    Left out, the engine version is this engine's — the same one every journal
    and recording carries. Given, it is written exactly as given, an empty
    string included: nothing decides on the caller's behalf what it meant.
    """
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    settle(game)

    rng = game.runtime.rng.get_state()

    assert game.save()["engine"] == __version__
    assert game.save(engine_version="0.9.0")["engine"] == "0.9.0"
    assert game.save(engine_version="")["engine"] == ""

    assert save_game(game.state, rng_state=rng)["engine"] == __version__
    assert save_game(game.state, engine_version="", rng_state=rng)["engine"] == ""


def test_a_session_save_is_stamped_with_this_engine(
    everything: ContentLibrary,
) -> None:
    session = Session(everything, 2, seed=3)

    settle(session.game)

    assert session.save()["engine"] == __version__


@pytest.mark.parametrize("engine", [None, "", "0.9.0", "99.0.0"])
def test_the_engine_a_save_names_does_not_decide_whether_it_loads(
    everything: ContentLibrary, engine: str | None
) -> None:
    """
    Loading has never read the field, and stamping it did not change that.
    """
    game = play(everything, 7, 2, steps=40)

    data = written(game)

    if engine is None:
        del data["engine"]
    else:
        data["engine"] = engine

    assert state_digest(Game.load(data, everything).state) == state_digest(
        game.state
    )


# Where a yes-or-no lives in a save, at three depths: the game, a player, and
# a card - the character, which every player holds from the deal onwards. Each
# names the object that holds the field in the file, the field, and how to read
# it back off the loaded game.
FLAGS: dict[str, tuple[Any, str, Any]] = {
    "the game is over": (
        lambda data: data,
        "game_over",
        lambda state: state.game_over,
    ),
    "a player is alive": (
        lambda data: data["players"][0],
        "alive",
        lambda state: state.players[0].alive,
    ),
    "a card is tapped": (
        lambda data: data["players"][0]["character"],
        "tapped",
        lambda state: state.players[0].character.tapped,
    ),
}


@pytest.fixture(scope="module")
def a_saved_game(everything: ContentLibrary) -> dict[str, Any]:
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    return written(game)


MISSING = object()


def rewritten(saved: dict[str, Any], where: str, value: Any) -> dict[str, Any]:
    """
    A copy of the save with one yes-or-no set to a value, or taken out.
    """
    data = dict(json.loads(json.dumps(saved)))
    holder, key, _ = FLAGS[where]

    if value is MISSING:
        del holder(data)[key]
    else:
        holder(data)[key] = value

    return data


@pytest.mark.parametrize("where", FLAGS)
@pytest.mark.parametrize(
    "value", ("false", "true", "no", "yes", 0, 1, None, [], {})
)
def test_a_yes_or_no_that_is_not_true_or_false_is_refused(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    where: str,
    value: Any,
) -> None:
    """
    Read as Python reads it, "false" is true and a game written as not over
    reloads over. The writer only ever puts true or false in these places, so
    anything else is a save somebody else wrote, and it is refused rather than
    guessed at.
    """
    data = rewritten(a_saved_game, where, value)

    with pytest.raises(SaveError, match="can only be true or false"):
        Game.load(data, everything)


@pytest.mark.parametrize("where", FLAGS)
@pytest.mark.parametrize("value", (True, False))
def test_a_yes_or_no_that_is_true_or_false_is_read_as_written(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    where: str,
    value: bool,
) -> None:
    state = Game.load(rewritten(a_saved_game, where, value), everything).state

    assert FLAGS[where][2](state) is value


@pytest.mark.parametrize(
    ("where", "default"),
    (
        ("the game is over", False),
        ("a player is alive", True),
        ("a card is tapped", False),
    ),
)
def test_a_yes_or_no_the_save_does_not_hold_keeps_its_default(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    where: str,
    default: bool,
) -> None:
    """
    A save written before a field existed does not hold it, and still loads.
    """
    data = rewritten(a_saved_game, where, MISSING)

    state = Game.load(data, everything).state

    assert FLAGS[where][2](state) is default


def edited(saved: dict[str, Any], path: tuple[Any, ...], value: Any) -> dict[str, Any]:
    """
    A copy of the save with the value at one path replaced, or taken out.
    """
    data = dict(json.loads(json.dumps(saved)))
    holder: Any = data

    for key in path[:-1]:
        holder = holder[key]

    if value is MISSING:
        del holder[path[-1]]
    else:
        holder[path[-1]] = value

    return data


def with_a_modifier(saved: dict[str, Any], amount: Any) -> dict[str, Any]:
    """
    The save with one temporary modifier written into it, taking one away.
    """
    data = dict(json.loads(json.dumps(saved)))

    data["modifiers"] = [{"stat": "attack", "amount": amount, "player_id": 0}]

    return data


# A whole number at three depths: the game, a player, and a modifier inside a
# list - which is also where a number below zero is an ordinary thing to hold.
NUMBERS: dict[str, tuple[tuple[Any, ...], Any]] = {
    "souls to win": (("souls_to_win",), lambda state: state.souls_to_win),
    "a player's pennies": (
        ("players", 0, "pennies"),
        lambda state: state.players[0].pennies,
    ),
    "a modifier's amount": (
        ("modifiers", 0, "amount"),
        lambda state: state.modifiers[0].amount,
    ),
}


def numbered(saved: dict[str, Any], where: str, value: Any) -> dict[str, Any]:
    path, _ = NUMBERS[where]

    return edited(with_a_modifier(saved, -1), path, value)


@pytest.mark.parametrize("where", NUMBERS)
@pytest.mark.parametrize(
    "value", (3.0, 3.7, True, False, "3", "", "abc", None, [], {})
)
def test_a_whole_number_that_is_not_one_is_refused(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    where: str,
    value: Any,
) -> None:
    """
    Read as Python reads it, 3.7 is quietly 3, "3" is 3 and true is 1. The
    writer only ever puts a whole number in these places.
    """
    with pytest.raises(SaveError, match="can only be a whole number"):
        Game.load(numbered(a_saved_game, where, value), everything)


@pytest.mark.parametrize("where", NUMBERS)
@pytest.mark.parametrize("value", (5, 0, -3))
def test_a_whole_number_is_read_as_written_whatever_its_sign(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    where: str,
    value: int,
) -> None:
    """
    Only the type is asked about. Whether a number makes sense for its field is
    a question about the game, and a modifier that takes one away is ordinary.
    """
    state = Game.load(numbered(a_saved_game, where, value), everything).state

    assert NUMBERS[where][1](state) == value


@pytest.mark.parametrize(
    ("path", "default", "read"),
    (
        (("souls_to_win",), 4, lambda state: state.souls_to_win),
        (("players", 0, "pennies"), 0, lambda state: state.players[0].pennies),
        (("turn", "turn_number"), 1, lambda state: state.turn.turn_number),
    ),
)
def test_a_whole_number_the_save_does_not_hold_keeps_its_default(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    path: tuple[Any, ...],
    default: int,
    read: Any,
) -> None:
    state = Game.load(edited(a_saved_game, path, MISSING), everything).state

    assert read(state) == default


@pytest.mark.parametrize(
    ("path", "value", "said"),
    (
        (("seed",), "abc", "whole number"),
        (("players", 0, "player_id"), MISSING, "missing 'player_id'"),
        (("modifiers", 0, "stat"), MISSING, "missing 'stat'"),
        (("zones",), [], "should be an object"),
        (("players",), "abc", "should be a list"),
        (("players", 0, "counters"), [1], "should be an object"),
        (("ids",), -1, "identifiers"),
        (("modifiers", 0, "duration"), "for ever", "unknown duration"),
        (("turn", "phase"), "nonsense", "unknown phase"),
        (("format",), "2", "format"),
    ),
)
def test_a_save_that_cannot_be_read_is_refused_as_one(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    path: tuple[Any, ...],
    value: Any,
    said: str,
) -> None:
    """
    A caller loading a save has one thing to catch. A field missing, a list
    where an object belongs or a number that cannot be one used to come out as
    whatever Python raised first; the refusals that were already SaveError stay
    what they were.
    """
    data = edited(with_a_modifier(a_saved_game, -1), path, value)

    with pytest.raises(SaveError, match=said):
        Game.load(data, everything)


A_MONSTER = ("monster_area", 0, 0, "hp")


def with_shields(saved: dict[str, Any], amount: Any) -> dict[str, Any]:
    """
    The save with a shield on every player, each stopping the same amount.
    """
    data = dict(json.loads(json.dumps(saved)))

    data["shields"] = []

    for player in data["players"]:
        shield: dict[str, Any] = {"player_id": player["player_id"], "label": "t"}

        if amount is not MISSING:
            shield["amount"] = amount

        data["shields"].append(shield)

    return data


NOT_A_WHOLE_NUMBER = (True, False, 1.0, 1.5, "1", [])


@pytest.mark.parametrize("hp", NOT_A_WHOLE_NUMBER)
def test_a_card_whose_health_is_not_a_whole_number_is_refused(
    everything: ContentLibrary, a_saved_game: dict[str, Any], hp: Any
) -> None:
    """
    A monster's health written as text failed on the next move, false or an
    empty list read as a monster already dead, and a fraction left one with
    health no die can take away.
    """
    with pytest.raises(SaveError, match="'hp'"):
        Game.load(edited(a_saved_game, A_MONSTER, hp), everything)


@pytest.mark.parametrize("hp", (5, 0, -2))
def test_a_card_whose_health_is_a_whole_number_loads(
    everything: ContentLibrary, a_saved_game: dict[str, Any], hp: int
) -> None:
    state = Game.load(edited(a_saved_game, A_MONSTER, hp), everything).state

    assert state.monster_area[0].cards[0].hp == hp


@pytest.mark.parametrize("hp", (None, MISSING), ids=("none", "missing"))
def test_a_card_with_no_health_written_down_takes_its_printed_health(
    everything: ContentLibrary, a_saved_game: dict[str, Any], hp: Any
) -> None:
    """
    Nothing written down means the health printed on the card, and a card with
    no health printed on it has none.
    """
    state = Game.load(edited(a_saved_game, A_MONSTER, hp), everything).state

    monster = state.monster_area[0].cards[0]

    assert monster.definition.health is not None
    assert monster.hp == monster.definition.health

    loot = edited(a_saved_game, ("zones", "loot_deck", "cards", 0, "hp"), hp)
    card = Game.load(loot, everything).state.loot_deck.cards[0]

    assert card.definition.health is None
    assert card.hp is None


@pytest.mark.parametrize("amount", NOT_A_WHOLE_NUMBER)
def test_a_shield_that_stops_something_other_than_a_whole_number_is_refused(
    everything: ContentLibrary, a_saved_game: dict[str, Any], amount: Any
) -> None:
    """
    A shield of text failed the first time damage met it, and a fraction would
    have left a player with health no die can take away.
    """
    with pytest.raises(SaveError, match="'amount'"):
        Game.load(with_shields(a_saved_game, amount), everything)


@pytest.mark.parametrize(
    ("amount", "stops"),
    ((3, 3), (0, 0), (-1, -1), (None, None), (MISSING, None)),
    ids=("3", "0", "-1", "none", "missing"),
)
def test_a_shield_that_stops_a_whole_number_or_the_whole_blow_loads(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    amount: Any,
    stops: int | None,
) -> None:
    shields = Game.load(with_shields(a_saved_game, amount), everything).state.shields

    assert [shield.amount for shield in shields] == [stops] * len(shields)


# The seats a card writes down: who owns it, who controls it, and who last hurt
# it. Each is a seat or nobody.
SEATED = ("owner", "controller", "last_damaged_by")


def a_monster_with(saved: dict[str, Any], field: str, value: Any) -> dict[str, Any]:
    """
    The save with one seat on the first monster written as the value given.
    """
    return edited(saved, (*A_MONSTER[:-1], field), value)


@pytest.mark.parametrize("field", SEATED)
@pytest.mark.parametrize("value", (*NOT_A_WHOLE_NUMBER, {}))
def test_a_card_seat_that_is_not_a_seat_number_is_refused(
    everything: ContentLibrary, a_saved_game: dict[str, Any], field: str, value: Any
) -> None:
    """
    A fraction or a text loaded and failed later - a monster killed half way,
    an item's ability with nobody to find - and true was read as seat 1: it
    paid a reward, and the game then wrote a save it would not load.
    """
    with pytest.raises(SaveError, match=f"'{field}'"):
        Game.load(a_monster_with(a_saved_game, field, value), everything)


@pytest.mark.parametrize("field", SEATED)
@pytest.mark.parametrize(
    ("value", "read"),
    ((1, 1), (-1, -1), (99, 99), (None, None), (MISSING, None)),
    ids=("seat", "negative", "far past the end", "none", "missing"),
)
def test_a_card_seat_that_is_a_seat_number_or_nobody_loads(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    field: str,
    value: Any,
    read: int | None,
) -> None:
    """
    Only the type is asked about. A seat nobody sits in is how the rules say
    nobody, and a seat left out is the same as one written down as nothing.
    """
    assert field in a_saved_game["monster_area"][0][0]

    data = a_monster_with(a_saved_game, field, value)
    monster = Game.load(data, everything).state.monster_area[0].cards[0]

    assert getattr(monster, field) == read


@pytest.mark.parametrize("field", SEATED)
def test_a_card_seat_just_past_the_table_loads(
    everything: ContentLibrary, a_saved_game: dict[str, Any], field: str
) -> None:
    seats = len(a_saved_game["players"])

    data = a_monster_with(a_saved_game, field, seats)
    monster = Game.load(data, everything).state.monster_area[0].cards[0]

    assert getattr(monster, field) == seats


AN_ABILITY: dict[str, Any] = {
    "trigger": "activated",
    "conditions": [],
    "targets": [],
    "effects": [{"effect": "gain_cents", "amount": 1}],
}


def with_an_ability(saved: dict[str, Any], ability: dict[str, Any]) -> dict[str, Any]:
    """
    The save with one ability waiting on the stack.
    """
    data = dict(json.loads(json.dumps(saved)))

    data["stack"] = [{"kind": "activated_ability", "ability": ability}]

    return data


def test_an_ability_on_the_stack_comes_back_as_written(
    everything: ContentLibrary, a_saved_game: dict[str, Any]
) -> None:
    state = Game.load(with_an_ability(a_saved_game, AN_ABILITY), everything).state

    ability = next(iter(state.stack)).ability

    assert ability is not None
    assert ability.trigger == "activated"
    assert [dict(effect) for effect in ability.effects] == AN_ABILITY["effects"]


@pytest.mark.parametrize(
    ("key", "value", "said"),
    (
        ("trigger", MISSING, "missing 'trigger'"),
        ("conditions", 7, "should be a list"),
        ("targets", None, "should be a list"),
        ("effects", {"x": 1}, "should be a list"),
        ("effects", "ab", "should be a list"),
    ),
)
def test_a_malformed_ability_on_the_stack_is_refused(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    key: str,
    value: Any,
    said: str,
) -> None:
    """
    The ability is rebuilt from what the save says, and a shape the writer never
    puts down came out as whatever Python raised first - or, for effects written
    as an object, as a game that loaded and failed on its first move.
    """
    ability = dict(AN_ABILITY)

    if value is MISSING:
        del ability[key]
    else:
        ability[key] = value

    with pytest.raises(SaveError, match=said):
        Game.load(with_an_ability(a_saved_game, ability), everything)


# A controller at three places in a save, each read by its own loader: an
# ability waiting on the stack, an event waiting in the queue, and a watcher.
# Each entry says how to write one in, and how to read the controller back.
CONTROLLED: dict[str, tuple[Any, Any]] = {
    "stack": (
        lambda: {"kind": "activated_ability", "ability": dict(AN_ABILITY)},
        lambda state: next(iter(state.stack)).controller,
    ),
    "events": (
        lambda: {"type": "game_start"},
        lambda state: next(iter(state.events)).controller,
    ),
    "watchers": (
        lambda: {"event": "after_roll"},
        lambda state: state.watchers[0].controller,
    ),
}


def controlled(saved: dict[str, Any], where: str, controller: Any) -> dict[str, Any]:
    """
    The save with one entry at the place named, answering to a controller.
    """
    data = dict(json.loads(json.dumps(saved)))
    entry = CONTROLLED[where][0]()

    if controller is not MISSING:
        entry["controller"] = controller

    data[where] = [entry]

    return data


@pytest.mark.parametrize("where", CONTROLLED)
@pytest.mark.parametrize("controller", (True, False, 1.0, 1.5, "1", [], {}))
def test_a_controller_that_is_not_a_seat_number_is_refused(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    where: str,
    controller: Any,
) -> None:
    """
    A fraction or a text got past the checks on seats and failed when the
    ability resolved, and true was quietly read as the second player.
    """
    data = controlled(a_saved_game, where, controller)

    with pytest.raises(SaveError, match="'controller'"):
        Game.load(data, everything)


@pytest.mark.parametrize("where", CONTROLLED)
@pytest.mark.parametrize(
    ("controller", "read"),
    ((1, 1), (-1, -1), (2, 2), (None, None), (MISSING, None)),
    ids=("seat", "negative", "past the end", "none", "missing"),
)
def test_a_controller_that_is_a_seat_number_or_nobody_loads(
    everything: ContentLibrary,
    a_saved_game: dict[str, Any],
    where: str,
    controller: Any,
    read: int | None,
) -> None:
    """
    Only the type is asked about. A seat nobody sits in is how the rules say
    nobody, and they already answer it that way when the entry is played.
    """
    assert len(a_saved_game["players"]) == 2

    state = Game.load(controlled(a_saved_game, where, controller), everything).state

    assert CONTROLLED[where][1](state) == read


@pytest.fixture(scope="module")
def three_seats(everything: ContentLibrary) -> dict[str, Any]:
    game = play(everything, 7, 3, steps=40)

    return written(game)


def reseated(saved: dict[str, Any], seats: list[int]) -> dict[str, Any]:
    """
    A copy of the save with the players' identifiers rewritten, seat by seat.
    """
    data = dict(json.loads(json.dumps(saved)))

    for player, seat in zip(data["players"], seats, strict=True):
        player["player_id"] = seat

    return data


@pytest.mark.parametrize(
    "seats",
    ([1, 1, 2], [-1, 1, 2], [0, 1, 3], [0, 2, 4], [2, 1, 0]),
    ids=("duplicate", "negative", "past the end", "with gaps", "reversed"),
)
def test_a_player_out_of_their_seat_is_refused(
    everything: ContentLibrary, three_seats: dict[str, Any], seats: list[int]
) -> None:
    """
    A player's identifier is where they sit. A save that numbers them otherwise
    used to load, and then the moves offered to a client and the moves the game
    accepted belonged to different people.
    """
    with pytest.raises(SaveError, match="seats player"):
        Game.load(reseated(three_seats, seats), everything)


@pytest.mark.parametrize(
    ("key", "seat", "said"),
    (
        ("active_player", -1, "gives the turn to seat -1"),
        ("active_player", 3, "gives the turn to seat 3"),
        ("extra_turn_for", -1, "promises an extra turn to seat -1"),
        ("extra_turn_for", 3, "promises an extra turn to seat 3"),
    ),
)
def test_a_turn_given_to_a_seat_nobody_sits_in_is_refused(
    everything: ContentLibrary,
    three_seats: dict[str, Any],
    key: str,
    seat: int,
    said: str,
) -> None:
    """
    Seat -1 is the last player to Python and nobody to the rules: a turn given
    to it loaded, and then no one could act in it. A seat past the end loaded
    and failed on the first move.
    """
    data = edited(three_seats, ("turn", key), seat)

    with pytest.raises(SaveError, match=said):
        Game.load(data, everything)


@pytest.mark.parametrize("promised", (1.0, True, "1"))
def test_an_extra_turn_promised_to_something_other_than_a_seat_number_is_refused(
    everything: ContentLibrary, three_seats: dict[str, Any], promised: Any
) -> None:
    """
    Seat 1 as 1.0 or as true is equal to a seat by Python's reckoning, and got
    past the check on seats: 1.0 then failed on the first move, and true was
    quietly read as the second player. A seat is a whole number, as JSON writes
    one.
    """
    data = edited(three_seats, ("turn", "extra_turn_for"), promised)

    with pytest.raises(SaveError, match="'extra_turn_for'"):
        Game.load(data, everything)


@pytest.mark.parametrize(
    "promised", (None, MISSING, 0, 2), ids=("none", "missing", "0", "2")
)
def test_an_extra_turn_promised_to_a_seat_at_the_table_loads(
    everything: ContentLibrary, three_seats: dict[str, Any], promised: Any
) -> None:
    """
    A save that does not hold the field promises no extra turn, exactly as one
    that holds nothing for it.
    """
    data = edited(three_seats, ("turn", "extra_turn_for"), promised)

    if promised is MISSING:
        assert "extra_turn_for" not in data["turn"]

    expected = None if promised is MISSING else promised

    assert Game.load(data, everything).state.turn.extra_turn_for == expected


@pytest.mark.parametrize("players", (2, 3, 4))
def test_every_table_the_writer_sets_loads_back(
    everything: ContentLibrary, players: int
) -> None:
    game = play(everything, 11, players, steps=30)

    back = Game.load(written(game), everything)

    assert [player.player_id for player in back.state.players] == list(
        range(players)
    )
    assert state_digest(back.state) == state_digest(game.state)


def a_generator(saved: dict[str, Any], rng: Any) -> dict[str, Any]:
    return edited(saved, ("rng",), rng)


@pytest.mark.parametrize(
    "rng",
    (
        "x",
        7,
        {},
        [],
        [3],
        "wrong length",
        "negative",
    ),
)
def test_a_random_generator_that_cannot_be_restored_is_refused(
    everything: ContentLibrary, three_seats: dict[str, Any], rng: Any
) -> None:
    """
    The generator's state is handed to Python's own, which refuses a broken one
    in whichever way it likes - a value error, a type error, a missing key, an
    index past the end, a number that does not fit. A caller loading a save has
    one thing to catch.
    """
    version, words, gauss = three_seats["rng"]

    if rng == "wrong length":
        rng = [version, words[:-1], gauss]
    elif rng == "negative":
        rng = [version, [-5, *words[1:]], gauss]

    with pytest.raises(SaveError, match="random generator"):
        Game.load(a_generator(three_seats, rng), everything)


def test_a_session_keeps_its_game_when_the_generator_cannot_be_restored(
    everything: ContentLibrary, three_seats: dict[str, Any]
) -> None:
    session = Session(everything, 2, seed=1)
    before = state_digest(session.game.state)

    with pytest.raises(SaveError, match="random generator"):
        session.load(a_generator(three_seats, "x"))

    assert state_digest(session.game.state) == before


def test_a_saved_generator_rolls_on_as_it_would_have(
    everything: ContentLibrary,
) -> None:
    game = play(everything, 5, 3, steps=25)

    back = Game.load(written(game), everything)

    assert back.runtime.rng.get_state() == game.runtime.rng.get_state()
    assert [back.runtime.rng.randint(1, 6) for _ in range(20)] == [
        game.runtime.rng.randint(1, 6) for _ in range(20)
    ]


def test_a_game_saved_before_it_starts_rolls_from_its_seed(
    everything: ContentLibrary,
) -> None:
    """
    Nothing has rolled yet, so nothing is written down: the generator is where
    the seed puts it, and that is where a reload puts it too.
    """
    game = Game.from_content(everything, ["Ann", "Bo"], seed=4)

    data = json.loads(json.dumps(save_game(game.state)))

    assert data["rng"] is None

    back = Game.load(data, everything)

    assert back.runtime.rng.get_state() == game.runtime.rng.get_state()


@pytest.fixture(scope="module")
def before_the_start(everything: ContentLibrary) -> dict[str, Any]:
    game = Game.from_content(everything, ["Ann", "Bo"], seed=4)

    return dict(json.loads(json.dumps(save_game(game.state))))


@pytest.mark.parametrize("rng", (None, MISSING))
def test_a_game_not_yet_started_needs_no_generator_state(
    everything: ContentLibrary, before_the_start: dict[str, Any], rng: Any
) -> None:
    """
    Nothing has rolled before the start, so the seed says where the generator
    is, and a save that leaves the state out says no less.
    """
    data = edited(before_the_start, ("rng",), rng)

    assert data["started"] is False

    back = Game.load(data, everything)

    assert back.runtime.rng.get_state() == RNG(4).get_state()


@pytest.mark.parametrize("rng", (None, MISSING))
def test_a_game_in_progress_without_its_generator_state_is_refused(
    everything: ContentLibrary, three_seats: dict[str, Any], rng: Any
) -> None:
    """
    Once a game has started, the seed no longer says where the generator is:
    it may have rolled, and nothing else in the save says whether it has. A
    save of a game in progress that does not hold the state would reload into
    another game, so it is refused.
    """
    data = edited(three_seats, ("rng",), rng)

    assert data["started"] is True

    with pytest.raises(SaveError, match="random generator state"):
        Game.load(data, everything)


def test_a_session_keeps_its_game_when_a_started_save_has_no_generator(
    everything: ContentLibrary, three_seats: dict[str, Any]
) -> None:
    session = Session(everything, 2, seed=1)
    before = state_digest(session.game.state)

    with pytest.raises(SaveError, match="random generator state"):
        session.load(edited(three_seats, ("rng",), None))

    assert state_digest(session.game.state) == before


def test_the_writer_holds_back_the_generator_only_before_the_start(
    everything: ContentLibrary,
) -> None:
    game = Game.from_content(everything, ["Ann", "Bo"], seed=4)

    assert save_game(game.state)["rng"] is None

    assert game.start().accepted

    settle(game)

    written_down = written(game)

    assert written_down["started"] is True
    assert written_down["rng"] is not None

    back = Game.load(written_down, everything)

    assert back.runtime.rng.get_state() == game.runtime.rng.get_state()


@pytest.mark.parametrize("steps", (0, 25, 60))
def test_a_started_game_rolls_on_after_a_reload(
    everything: ContentLibrary, steps: int
) -> None:
    game = play(everything, 9, 3, steps=steps)

    back = Game.load(written(game), everything)

    assert back.runtime.rng.get_state() == game.runtime.rng.get_state()

    rolls = random.Random(1)
    again = random.Random(1)

    for _ in range(30):
        if game.is_over:
            break

        step(game, rolls)
        step(back, again)

        assert state_digest(back.state) == state_digest(game.state)


@pytest.fixture(scope="module")
def a_window_open(everything: ContentLibrary) -> dict[str, Any]:
    """
    A three-player game saved while a priority window is open.
    """
    game = Game.from_content(
        everything, ["Ann", "Bo", "Cy"], seed=5, interactive_priority=True
    )

    assert game.start().accepted

    moves = random.Random(0)

    for _ in range(500):
        step(game, moves)

        try:
            data = written(game)
        except SaveError:
            continue

        if data["priority"]["is_open"]:
            return data

    raise AssertionError("no priority window was ever open between moves")


def test_a_window_the_writer_left_open_or_shut_loads(
    everything: ContentLibrary,
    a_window_open: dict[str, Any],
    three_seats: dict[str, Any],
) -> None:
    shut = Game.load(three_seats, everything).state.priority

    assert shut.is_open is False
    assert shut.holder is None

    held = Game.load(a_window_open, everything).state.priority

    assert held.is_open is True
    assert held.holder == a_window_open["priority"]["holder"]


@pytest.mark.parametrize(
    ("holder", "said"),
    (
        (None, "priority window open for seat None"),
        (-1, "priority window open for seat -1"),
        (3, "priority window open for seat 3"),
        (True, "'holder'"),
        (1.0, "'holder'"),
        ("1", "'holder'"),
        ([], "'holder'"),
    ),
)
def test_an_open_window_held_by_nobody_at_the_table_is_refused(
    everything: ContentLibrary,
    a_window_open: dict[str, Any],
    holder: Any,
    said: str,
) -> None:
    """
    Nobody but the holder may pass, so a window open for no seat - or for a
    seat nobody sits in - used to load into a game nobody could move.
    """
    data = edited(a_window_open, ("priority", "holder"), holder)

    with pytest.raises(SaveError, match=re.escape(said)):
        Game.load(data, everything)


@pytest.mark.parametrize("holder", (0, 2))
def test_an_open_window_held_at_the_table_loads(
    everything: ContentLibrary, a_window_open: dict[str, Any], holder: int
) -> None:
    data = edited(a_window_open, ("priority", "holder"), holder)

    assert Game.load(data, everything).state.priority.holder == holder


@pytest.mark.parametrize(
    ("holder", "said"),
    (
        (0, "priority to seat 0 with no window open"),
        (True, "'holder'"),
        (1.0, "'holder'"),
        ("1", "'holder'"),
    ),
)
def test_priority_held_with_no_window_open_is_refused(
    everything: ContentLibrary,
    three_seats: dict[str, Any],
    holder: Any,
    said: str,
) -> None:
    data = edited(three_seats, ("priority", "holder"), holder)

    assert data["priority"]["is_open"] is False

    with pytest.raises(SaveError, match=re.escape(said)):
        Game.load(data, everything)


def test_the_plain_functions_work_without_the_facade(
    everything: ContentLibrary,
) -> None:
    """
    A save is data and a load is a function; the session object is a
    convenience, not the interface.
    """
    game = play(everything, 7, 2, steps=40)

    settle(game)

    data = save_game(
        game.state, engine_version="bare", rng_state=game.runtime.rng.get_state()
    )
    state = load_game(json.loads(json.dumps(data)), everything.registry())

    assert state_digest(state) == state_digest(game.state)
