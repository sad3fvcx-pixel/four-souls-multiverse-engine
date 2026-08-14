# src/fsme/rules/setup.py

"""
Laying out a game from loaded content.

Everything here happens before the first command. It builds the position the
players start from — decks shuffled, characters dealt, shop and monster area
filled — and then gets out of the way: the game itself begins when someone
submits ``start_game``.

Setup consumes the engine RNG in a fixed order, so the same seed and the same
content always deal the same opening.
"""

from __future__ import annotations

from collections.abc import Sequence

from fsme.cards import CardDefinition, CardInstance, CardType
from fsme.content import ContentLibrary
from fsme.rng.rng import RNG
from fsme.state import GameState, PlayerState

from .constants import MONSTER_SLOTS, SHOP_SLOTS, SOULS_TO_WIN
from .errors import RuleError
from .slots import open_area, place


class SetupError(RuleError):
    """
    Raised when the content cannot furnish a playable game.
    """


def new_game(
    library: ContentLibrary,
    players: Sequence[str],
    *,
    seed: int = 0,
    souls_to_win: int = SOULS_TO_WIN,
    monster_slots: int = MONSTER_SLOTS,
    shop_slots: int = SHOP_SLOTS,
) -> GameState:
    """
    Build a starting position for the given players.

    The content library decides what is in the decks; the rules decide how many
    of each are face up and what a player begins with.
    """
    if not players:
        raise SetupError("a game needs at least one player")

    state = GameState(
        seed=seed,
        souls_to_win=souls_to_win,
        monster_slots=monster_slots,
        shop_slots=shop_slots,
    )
    rng = RNG(seed)

    index = _index(library)

    _build_decks(state, index, rng)
    _lay_out_bonus_souls(state, index)
    _seat_players(state, index, players, rng)
    _open_the_board(state, monster_slots=monster_slots, shop_slots=shop_slots)

    return state


def _index(library: ContentLibrary) -> dict[CardType, list[CardDefinition]]:
    """
    Group the library by card type.
    """
    grouped: dict[CardType, list[CardDefinition]] = {}

    for definition in library.definitions():
        grouped.setdefault(definition.type, []).append(definition)

    return grouped


def _instances(
    definitions: Sequence[CardDefinition],
    kind: str,
    state: GameState,
) -> list[CardInstance]:
    """
    Turn definitions into cards for this game.
    """
    return [
        CardInstance(
            definition=definition,
            instance_id=state.ids.allocate(kind),
        )
        for definition in definitions
    ]


def _build_decks(
    state: GameState,
    index: dict[CardType, list[CardDefinition]],
    rng: RNG,
) -> None:
    """
    Fill and shuffle the loot, treasure and monster decks.

    The decks are shuffled in a fixed order — loot, then treasure, then
    monsters — because the order of RNG calls is part of what a seed means.
    """
    for card_type, zone, kind in (
        (CardType.LOOT, state.loot_deck, "loot"),
        (CardType.TREASURE, state.treasure_deck, "treasure"),
        (CardType.MONSTER, state.monster_deck, "monster"),
    ):
        definitions = index.get(card_type, [])

        if not definitions:
            raise SetupError(
                f"the loaded content has no {card_type} cards; "
                f"a game cannot be set up without them"
            )

        cards = _instances(definitions, kind, state)
        rng.shuffle(cards)

        zone.cards.extend(cards)


def _lay_out_bonus_souls(
    state: GameState,
    index: dict[CardType, list[CardDefinition]],
) -> None:
    """
    Put the bonus souls on the table.

    They are not in any deck: they sit face up from the start and go to the
    first player who earns them, so they have to be in play to be watching.
    """
    for definition in index.get(CardType.BONUS_SOUL, ()):
        state.bonus_souls.add_top(
            CardInstance(
                definition=definition,
                instance_id=state.ids.allocate("soul"),
            )
        )


def _seat_players(
    state: GameState,
    index: dict[CardType, list[CardDefinition]],
    players: Sequence[str],
    rng: RNG,
) -> None:
    """
    Give every player a character and the item it starts with.
    """
    characters = list(index.get(CardType.CHARACTER, ()))

    if len(characters) < len(players):
        raise SetupError(
            f"{len(players)} players need {len(players)} characters, "
            f"the loaded content has {len(characters)}"
        )

    rng.shuffle(characters)

    starting_items = {
        definition.id: definition
        for definition in index.get(CardType.STARTING_ITEM, ())
    }

    for seat, name in enumerate(players):
        definition = characters[seat]

        character = CardInstance(
            definition=definition,
            instance_id=state.ids.allocate("character"),
            owner=seat,
            controller=seat,
        )

        health = definition.health or 2

        player = PlayerState(
            player_id=seat,
            name=name,
            hp=health,
            max_hp=health,
            character=character,
        )

        state.add_player(player)

        _give_starting_item(state, player, definition, starting_items)


def _give_starting_item(
    state: GameState,
    player: PlayerState,
    character: CardDefinition,
    starting_items: dict[str, CardDefinition],
) -> None:
    """
    Put a character's printed starting item into play.
    """
    reference = character.metadata.get("starting_item")

    if reference is None:
        return

    definition = starting_items.get(str(reference))

    if definition is None:
        raise SetupError(
            f"character '{character.id}' starts with '{reference}', "
            f"which is not in the loaded content"
        )

    player.treasures.add_top(
        CardInstance(
            definition=definition,
            instance_id=state.ids.allocate("item"),
            owner=player.player_id,
            controller=player.player_id,
        )
    )


def _open_the_board(
    state: GameState,
    *,
    monster_slots: int,
    shop_slots: int,
) -> None:
    """
    Turn the first monsters and shop items face up.
    """
    open_area(state, monster_slots)

    for _ in range(monster_slots):
        if not state.monster_deck.cards:
            break

        place(state, _first_monster(state))

    for _ in range(shop_slots):
        if not state.treasure_deck.cards:
            break

        state.treasure_shop.add_top(state.treasure_deck.draw())


def _first_monster(state: GameState) -> CardInstance:
    """
    Draw until a monster turns up, burying anything that is not one.

    The monster deck also holds events and curses. Laying a game out is not a
    turn, so there is nobody for an event to happen to and nobody to curse; the
    card goes to the bottom and the deal continues. A deck of nothing but events
    would loop for ever, so the last card drawn is used whatever it is.
    """
    seen = 0
    total = len(state.monster_deck)

    while state.monster_deck.cards and seen < total:
        card: CardInstance = state.monster_deck.draw()

        if card.definition.type is CardType.MONSTER:
            return card

        state.monster_deck.cards.insert(0, card)
        seen += 1

    last: CardInstance = state.monster_deck.draw()

    return last
