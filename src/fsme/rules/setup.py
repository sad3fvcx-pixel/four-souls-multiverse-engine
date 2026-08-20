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
from fsme.scenario import Scenario, Seat
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
    scenario: Scenario | None = None,
) -> GameState:
    """
    Build a starting position for the given players.

    The content library decides what is in the decks; the rules decide how many
    of each are face up and what a player begins with.

    ``scenario`` asks for some of that to be decided instead of dealt — a named
    character in a seat, a different item, other numbers on the table. It is
    read here and nowhere else, and it changes *what* is laid out, never *how*:
    the order the RNG is consumed in is the same with a scenario and without
    one, because that order is what a seed means.

    A scenario that asks for nothing deals the game FSME deals today. That is
    not a happy accident but the property everything else rests on.
    """
    if not players:
        raise SetupError("a game needs at least one player")

    wanted = scenario if scenario is not None else Scenario()

    state = GameState(
        seed=seed,
        souls_to_win=_number(wanted.table.souls_to_win, souls_to_win),
        monster_slots=_number(wanted.table.monster_slots, monster_slots),
        shop_slots=_number(wanted.table.shop_slots, shop_slots),
    )

    _deal_resources(state, wanted)

    rng = RNG(seed)

    index = _index(library)

    _build_decks(state, index, rng)
    _lay_out_bonus_souls(state, index)
    _seat_players(state, index, players, rng, seats=wanted.players)
    _open_the_board(
        state,
        monster_slots=state.monster_slots,
        shop_slots=state.shop_slots,
    )

    return state


def _number(asked: int | None, otherwise: int) -> int:
    """
    What a scenario asked for, or what the caller wanted.
    """
    return otherwise if asked is None else int(asked)


def _deal_resources(state: GameState, scenario: Scenario) -> None:
    """
    Set the opening hand and cents this game will deal.

    The scenario format asks for these per seat, because "what if one player
    starts rich" is a question somebody will want. This build deals one opening
    to the whole table — `start_game` reads two numbers off the game — so a
    scenario whose seats disagree is refused rather than half-honoured. The
    format keeps the shape; the engine will grow into it.

    Refused in two places on purpose: the scenario loader says it in a sentence
    somebody reading a file can act on, and this says it again for a scenario
    built in code, which never went through the loader.
    """
    state.starting_coins = _one_number(
        [seat.coins for seat in scenario.players],
        state.starting_coins,
        "coins",
    )
    state.starting_hand = _one_number(
        [seat.loot for seat in scenario.players],
        state.starting_hand,
        "loot",
    )


def _one_number(asked: list[int | None], otherwise: int, what: str) -> int:
    """
    The one number every seat asked for, or the one the game already had.
    """
    named = {value for value in asked if value is not None}

    if not named:
        return otherwise

    if len(named) > 1:
        raise SetupError(
            f"this scenario deals {what} of "
            f"{', '.join(str(value) for value in sorted(named))} to different "
            f"seats, and this build deals the same opening to the whole table"
        )

    if len(asked) != len(named) and any(value is None for value in asked):
        raise SetupError(
            f"this scenario names the opening {what} for some seats and not "
            f"others, and this build deals the same opening to the whole table"
        )

    return named.pop()


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

    # Rooms are optional content, added once the table knows the basic rules
    # (COMPREHENSIVE_RULES.md §12). Content without them is not a broken game;
    # it is a game without rooms, so the deck is built only if there is one and
    # shuffled last, after the decks a seed already promised.
    rooms = index.get(CardType.ROOM, [])

    if rooms:
        cards = _instances(rooms, "room", state)
        rng.shuffle(cards)

        state.room_deck.cards.extend(cards)


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
    seats: Sequence[Seat] = (),
) -> None:
    """
    Give every player a character and the item it starts with.

    ``seats`` is what a scenario asked for, seat by seat. A seat that asked for
    nothing is dealt exactly as it is dealt without a scenario.

    **The shuffle happens either way, in the same place, whatever was pinned.**
    That is the whole of what makes a scenario safe: the RNG is consumed in a
    fixed order, and everything dealt after this — the board, and every draw of
    the game — depends on where the generator stands. Skipping the shuffle when
    every seat is named would move all of that for a reason nobody reading the
    scenario could see. So the characters are shuffled, and then the ones a
    scenario named are lifted out of the shuffled pile.
    """
    characters = list(index.get(CardType.CHARACTER, ()))

    if len(characters) < len(players):
        raise SetupError(
            f"{len(players)} players need {len(players)} characters, "
            f"the loaded content has {len(characters)}"
        )

    rng.shuffle(characters)

    by_id = {definition.id: definition for definition in characters}

    starting_items = {
        definition.id: definition
        for definition in index.get(CardType.STARTING_ITEM, ())
    }

    pinned = _pinned_characters(seats, by_id)
    spare = iter(
        definition for definition in characters if definition.id not in pinned
    )

    for seat, name in enumerate(players):
        asked = seats[seat] if seat < len(seats) else Seat()

        definition = (
            by_id[asked.character] if asked.character else next(spare)
        )

        character = CardInstance(
            definition=definition,
            instance_id=state.ids.allocate("character"),
            owner=seat,
            controller=seat,
        )

        health = definition.health or 2

        player = PlayerState(
            player_id=seat,
            name=asked.name or name,
            hp=health,
            max_hp=health,
            character=character,
        )

        state.add_player(player)

        if asked.starting_item:
            _give_named_item(state, player, asked.starting_item, starting_items)
        else:
            _give_starting_item(state, player, definition, starting_items)


def _pinned_characters(
    seats: Sequence[Seat],
    by_id: dict[str, CardDefinition],
) -> set[str]:
    """
    The characters a scenario named, checked against the content.

    Checked here rather than when the file was read, because whether a card
    exists is a question about a library and the loader has none.
    """
    pinned: set[str] = set()

    for seat, asked in enumerate(seats):
        if not asked.character:
            continue

        if asked.character not in by_id:
            raise SetupError(
                f"seat {seat} asks for character '{asked.character}', "
                f"which is not in the loaded content"
            )

        pinned.add(asked.character)

    return pinned


def _give_named_item(
    state: GameState,
    player: PlayerState,
    wanted: str,
    starting_items: dict[str, CardDefinition],
) -> None:
    """
    Put the item a scenario asked for into play, instead of the printed one.
    """
    definition = starting_items.get(wanted)

    if definition is None:
        raise SetupError(
            f"seat {player.player_id} asks to start with '{wanted}', "
            f"which is not a starting item in the loaded content"
        )

    player.treasures.add_top(
        CardInstance(
            definition=definition,
            instance_id=state.ids.allocate("item"),
            owner=player.player_id,
            controller=player.player_id,
        )
    )


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
    Turn the first monsters, shop items and the first room face up.
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

    if state.room_deck.cards:
        # COMPREHENSIVE_RULES.md §12: the top room is turned face up into the
        # room slot at the start of the game, and that is how it enters play.
        state.room_area.add_top(state.room_deck.draw())


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
