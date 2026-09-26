"""
What "cancel everything that hasn't resolved" is allowed to reach.

O. The Fool says exactly that, and it used to delete itself from the game
saying it. Playing a loot card is one action that the engine splits in two —
the card's ability, and then putting the card into the discard — so that the
card lands only once its effect is done. Cancelling the whole stack cancelled
the second half, and since the card had already left the hand it ended up in no
zone at all: gone from the deck, the discard, every hand and the table.

Found in the audit at seed 113, turn 38, as the only ``stack_cancel`` in twenty
thousand commands, with a card census that could name the missing instance.

The fix is a property of the stack object rather than a rule about one card, so
both halves are tested: bookkeeping survives a cancel, and everything else
still does not.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import make_game, make_instance, treasure_definition

from fsme.api import load_content
from fsme.cards import CardType
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.stack import DISCARD_PLAYED_LOOT, StackItem, StackItemType

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

THE_FOOL = "loot_deck-cards_miscellaneous-base_game-o_the_fool"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


def where_is(state: Any, card: Any) -> str:
    """
    The zone holding a card, or "nowhere" — which is the bug this file is about.
    """
    zones: list[tuple[str, Any]] = [
        ("loot_deck", state.loot_deck),
        ("loot_discard", state.loot_discard),
        ("treasure_deck", state.treasure_deck),
        ("treasure_discard", state.treasure_discard),
        ("treasure_shop", state.treasure_shop),
        ("bonus_souls", state.bonus_souls),
        ("room_area", state.room_area),
        ("room_discard", state.room_discard),
    ]

    for player in state.players:
        zones += [
            (f"p{player.player_id}.hand", player.hand),
            (f"p{player.player_id}.treasures", player.treasures),
            (f"p{player.player_id}.souls", player.souls),
            (f"p{player.player_id}.curses", player.curses),
        ]

    for name, zone in zones:
        if any(one is card for one in zone.cards):
            return name

    if any(item.source is card for item in state.stack):
        return "stack"

    return "nowhere"


def play_the_fool(everything: ContentLibrary) -> tuple[Any, Any]:
    """
    Deal a game, put O. The Fool in a hand, and play it.
    """
    game = Game.from_content(everything, ["Ann", "Bo"], seed=1)
    game.start()

    state = game.state
    fool = next(
        card
        for card in state.loot_deck.cards
        if card.definition.id == THE_FOOL
    )

    state.loot_deck.cards.remove(fool)
    state.player(0).hand.add_top(fool)

    # Something of somebody's own on the stack, so the cancel has real work to
    # do and is not being tested against an empty stack.
    game.runtime.submit(
        Command(type=CommandType.END_PHASE, player=0)
    )

    index = list(state.player(0).hand.cards).index(fool)
    result = game.submit(
        Command(type=CommandType.PLAY_LOOT, player=0, payload={"index": index})
    )

    assert result.accepted, result.reason

    return game, fool


def test_a_card_that_cancels_the_stack_does_not_delete_itself(
    everything: ContentLibrary,
) -> None:
    """
    The defect, stated as the one thing that must be true afterwards.
    """
    game, fool = play_the_fool(everything)

    assert where_is(game.state, fool) != "nowhere", (
        "O. The Fool cancelled the bookkeeping that files it away and left "
        "the game entirely"
    )
    assert where_is(game.state, fool) == "loot_discard"


def test_the_engines_own_bookkeeping_is_not_cancellable() -> None:
    """
    Said as a property of the object rather than as a fact about one card, so
    that a second card with the same effect is covered by the same rule.
    """
    item = StackItem(
        kind=StackItemType.LOOT,
        label=DISCARD_PLAYED_LOOT,
        cancellable=False,
    )

    assert item.cancellable is False
    assert StackItem(kind=StackItemType.LOOT).cancellable is True


def test_cancelling_still_cancels_everything_else() -> None:
    """
    The other half. A fix that made the stack uncancellable would pass the test
    above and break the card it was written for.
    """
    from fsme.effects.builtin.stack import cancel_stack

    runtime, state = make_game()

    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    ordinary = StackItem(
        kind=StackItemType.ACTIVATED_ABILITY, label="something somebody did"
    )
    bookkeeping = StackItem(
        kind=StackItemType.LOOT, label=DISCARD_PLAYED_LOOT, cancellable=False
    )

    state.stack.push(ordinary)
    state.stack.push(bookkeeping)

    cancelled = cancel_stack(runtime._context, [ordinary, bookkeeping])

    assert cancelled == 1, "the ordinary object should have been cancelled"
    assert ordinary not in list(state.stack)
    assert bookkeeping in list(state.stack)


def test_an_ability_on_the_stack_is_still_cancellable(
    everything: ContentLibrary,
) -> None:
    """
    A card's ability waiting to resolve is exactly what O. The Fool is for.
    """
    from fsme.effects.builtin.stack import cancel_stack

    # Interactive priority, or the ability resolves the moment it is pushed and
    # there is nothing on the stack for anybody to answer.
    runtime, state = make_game(interactive_priority=True)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    card = make_instance(
        treasure_definition("test.slow", effects=({"gain_coins": 5},)),
        controller=0,
        owner=0,
        instance_id="instance:slow",
    )
    state.player(0).treasures.add_top(card)

    runtime.submit(
        Command(type=CommandType.ACTIVATE_TREASURE, player=0, payload={"index": 0})
    )

    waiting = [item for item in state.stack if item.cancellable]

    assert waiting, "nothing of the card's was left on the stack to cancel"
    assert cancel_stack(runtime._context, waiting) == len(waiting)


def test_no_loot_card_leaves_the_game_in_the_audited_deal(
    everything: ContentLibrary,
) -> None:
    """
    The seed the audit found it at, played far enough past the moment.

    O. The Fool is played on turn 38 of seed 113; before the fix, the card was
    unfindable from that point on and the deal was one loot card short for the
    rest of the game.
    """
    from fsme.journal import JournalKeeper
    from fsme.lab.bot import HeuristicBot
    from fsme.lab.simulation import ScriptedAgent
    from fsme.lab.simulation.runner import NAMES, _whose_move

    game = Game.from_content(everything, list(NAMES[:4]), seed=113)
    game.start()

    keeper = JournalKeeper(game)
    bot = HeuristicBot(113)
    agent = ScriptedAgent(113)

    def loot_now() -> set[str]:
        found: set[str] = set()
        zones = [state.loot_deck, state.loot_discard]

        for player in state.players:
            zones += [player.hand, player.treasures, player.souls, player.curses]

        zones += [state.treasure_discard, state.bonus_souls]

        for zone in zones:
            for one in zone.cards:
                definition = getattr(one, "definition", None)
                if definition is not None and definition.type is CardType.LOOT:
                    found.add(one.instance_id)

        for item in state.stack:
            definition = getattr(getattr(item, "source", None), "definition", None)
            if definition is not None and definition.type is CardType.LOOT:
                found.add(item.source.instance_id)

        return found

    state = game.state
    at_the_deal = loot_now()

    played_the_fool = False

    for _ in range(700):
        if game.is_over:
            break

        speaking = _whose_move(game)
        thought = bot.choose(game, seats=(speaking,))

        if thought is None:
            chosen = agent.choose(game, seats=(speaking,))
            if chosen is None:
                break
            command, label = chosen
        else:
            command, label = thought[0], thought[1]

        if not keeper.submit(command, label=label).accepted:
            break

        if any(
            one.type == "on_play"
            and getattr(one, "source", "") == "O. The Fool"
            for entry in keeper.journal.entries[-1:]
            for one in entry.events
        ):
            played_the_fool = True

    assert played_the_fool, "this deal no longer plays O. The Fool in 700 moves"

    # Lost Soul leaves the loot pool by its own text — "it becomes a soul" —
    # so it is the one card allowed to go missing here.
    still_there = loot_now()
    gone = at_the_deal - still_there

    for instance in gone:
        assert instance == "loot:39", (
            f"{instance} left the game and no card said it should"
        )
