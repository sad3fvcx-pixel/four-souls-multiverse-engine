# src/fsme/runtime/target_resolver.py

"""
Target resolution for Four Souls Multiverse Engine.

A target returns objects; it never changes the game.

The ``target_*`` family does not return at all when a real choice exists: it
raises DecisionRequired, and the Runtime suspends the ability until a player
answers. That keeps the choosing out of the resolver, which stays a pure
question about the state.

The one deliberate exception to purity is the ``random_*`` family.
TARGET_REGISTRY.md defines random targets, and drawing one necessarily advances
the engine RNG, whose state belongs to GameState. Randomness is therefore
consumed here, in a documented and deterministic order, and nothing else about
the game is touched.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from fsme.rng.rng import RNG
from fsme.state import DecisionKind, GameState, PlayerState

from .ability_context import AbilityContext
from .errors import DecisionRequired, UnknownTargetError

TargetFn = Callable[[GameState, AbilityContext, Mapping[str, Any], RNG], list[Any]]


class TargetResolver:
    """
    Resolves the target vocabulary used by card definitions.
    """

    def __init__(self) -> None:
        self._targets: dict[str, TargetFn] = {}
        self._register_builtin()

    def register(self, name: str, function: TargetFn) -> None:
        """
        Add a target implementation.
        """
        if name in self._targets:
            raise UnknownTargetError(f"target '{name}' is already registered")

        self._targets[name] = function

    def names(self) -> frozenset[str]:
        return frozenset(self._targets)

    def resolve(
        self,
        spec: Any,
        state: GameState,
        context: AbilityContext,
        rng: RNG,
    ) -> list[Any]:
        """
        Resolve one target specification into concrete objects.
        """
        name, params = normalise(spec)

        # A specification written on an effect names the group it will bind,
        # and that name is where the answer will be waiting when the ability
        # resumes. Looking only under the target's own name would ask again.
        for key in (str(params.get("as", name)), name):
            bound = context.targets.get(key)

            if bound is not None:
                return list(bound)

        try:
            target = self._targets[name]
        except KeyError:
            raise UnknownTargetError(f"unknown target '{name}'") from None

        return target(state, context, params, rng)

    def resolve_all(
        self,
        specs: Sequence[Any],
        state: GameState,
        context: AbilityContext,
        rng: RNG,
    ) -> None:
        """
        Resolve an ability's declared targets and bind them by name.

        A spec may carry ``"as"`` to name the resulting group so that later
        effects can point at it; otherwise the target name itself is used.

        A group that is already bound is left alone. That is what makes an
        ability resumable: after a player answers, resolution starts over from
        the top, and the target that asked the question must find the answer
        rather than ask it again.
        """
        for spec in specs:
            name, params = normalise(spec)
            alias = str(params.get("as", name))

            if alias in context.targets:
                continue

            context.bind(alias, self.resolve(spec, state, context, rng))

    def _register_builtin(self) -> None:
        register = self.register

        register("self", _self)
        register("source", _self)
        register("controller", _controller)
        register("owner", _owner)

        register("active_player", _active_player)
        register("current_player", _active_player)
        register("all_players", _all_players)
        register("opponents", _opponents)
        register("another_player", _opponents)
        register("random_player", _random_player)
        register("character", _character)
        register("player_left", _player_left)
        register("player_right", _player_right)
        register("random_loot", _random_loot)
        register("player", _player_by_index)
        register("target_player", _target_player)

        register("all_monsters", _all_monsters)
        register("current_monster", _current_monster)
        register("monster", _current_monster)
        register("random_monster", _random_monster)
        register("target_monster", _target_monster)
        register("target_curse", _target_curse)

        register("target_player_or_monster", _target_player_or_monster)
        register("target_loot", _target_loot)
        register("target_soul", _target_soul)
        register("target_deck_card", _target_deck_card)
        register("deck_top", _deck_top)
        register("target_treasure", _target_treasure)
        register("owned_treasure", _owned_treasure)
        register("all_treasures", _all_treasures)
        register("shop_items", _shop_items)
        register("target_shop_item", _target_shop_item)

        register("top_stack", _top_stack)
        register("all_stack", _all_stack)
        register("target_stack_item", _target_stack_item)
        register("event_source", _event_source)
        register("event_player", _event_player)
        register("previous_target", _previous_target)
        register("previous_result", _previous_result)

        register("group", _group)
        register("none", _none)


def normalise(spec: Any) -> tuple[str, Mapping[str, Any]]:
    """
    Reduce every accepted target spelling to a name and parameters.

    Accepted forms::

        "all_players"
        {"player": 2}
        {"target": "player", "player": 2, "as": "victim"}
        {"random_player": {"exclude_controller": true}}
    """
    if isinstance(spec, str):
        return spec, {}

    if not isinstance(spec, Mapping):
        raise UnknownTargetError(f"invalid target spec: {spec!r}")

    if "target" in spec:
        params = {key: value for key, value in spec.items() if key != "target"}

        return str(spec["target"]), params

    if len(spec) != 1:
        raise UnknownTargetError(
            f"target spec must name exactly one target: {dict(spec)!r}"
        )

    name, value = next(iter(spec.items()))

    if isinstance(value, Mapping):
        return str(name), value

    return str(name), {"value": value}


def _controller_player(state: GameState, context: AbilityContext) -> list[Any]:
    if context.controller is None:
        return []

    if not 0 <= context.controller < len(state.players):
        return []

    return [state.player(context.controller)]


def _self(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return [context.source] if context.source is not None else []


def _controller(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return _controller_player(state, context)


def _owner(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    index = context.owner if context.owner is not None else context.controller

    if index is None or not 0 <= index < len(state.players):
        return []

    return [state.player(index)]


def _active_player(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return [state.active_player] if state.players else []


def _all_players(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    if params.get("include_dead", False):
        return list(state.players)

    return state.living_players()


def _opponents(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return [
        player
        for player in state.living_players()
        if player.player_id != context.controller
    ]


def _character(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    The controller's character card, which taps and recharges like an item.
    """
    if context.controller is None or not 0 <= context.controller < len(state.players):
        return []

    character = state.player(context.controller).character

    return [character] if character is not None else []


def _neighbour(state: GameState, seat: int, step: int) -> list[Any]:
    """
    Return the living player that many seats away, going round the table.
    """
    if not state.players:
        return []

    size = len(state.players)

    for distance in range(1, size + 1):
        candidate = state.player((seat + step * distance) % size)

        if candidate.alive:
            return [candidate]

    return []


def _player_left(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    The player to the left of the active player, who takes the next turn.
    """
    return _neighbour(state, state.turn.active_player, 1)


def _player_right(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    The player to the right of the active player, who took the last turn.
    """
    return _neighbour(state, state.turn.active_player, -1)


def _random_loot(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    One card taken blindly from a hand.

    "At random" is the engine's business, not a player's: nobody chooses, so
    nobody is asked, and the RNG is consumed here in a documented order.
    """
    named = params.get("of")

    holders = [
        target
        for target in context.targets.get(str(named), ())
        if isinstance(target, PlayerState)
    ] if named is not None else [
        player
        for player in state.living_players()
        if player.player_id != context.controller
    ]

    cards: list[Any] = []

    for holder in holders:
        if not holder.hand.cards:
            continue

        cards.append(holder.hand.cards[rng.randint(0, len(holder.hand.cards) - 1)])

    return cards


def _random_player(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    candidates: list[PlayerState] = (
        _opponents(state, context, params, rng)
        if params.get("exclude_controller", False)
        else state.living_players()
    )

    if not candidates:
        return []

    return [candidates[rng.randint(0, len(candidates) - 1)]]


def _player_by_index(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    index = params.get("value", params.get("player"))

    if not isinstance(index, int) or not 0 <= index < len(state.players):
        return []

    return [state.player(index)]


def _ask(
    kind: DecisionKind,
    options: list[Any],
    context: AbilityContext,
    params: Mapping[str, Any],
    bind: str,
) -> list[Any]:
    """
    Stop and ask somebody to pick, unless there is nothing to pick from.

    A single option is not a choice, so the engine takes it rather than
    interrupting the game to confirm the obvious. No options at all means the
    ability simply has no target.

    The question usually goes to the ability's controller, because usually it
    is their card. ``chooser`` sends it elsewhere: "that player discards a loot
    card" is their choice to make, not the card holder's.
    """
    if not options:
        return []

    if len(options) == 1 and int(params.get("count", 1)) == 1:
        return list(options)

    count = int(params.get("count", 1))

    raise DecisionRequired(
        kind,
        options,
        bind=str(params.get("as", bind)),
        player=_chooser(context, params),
        minimum=int(params.get("minimum", count)),
        maximum=int(params.get("maximum", count)),
        prompt=str(params.get("prompt", "")),
    )


def _chooser(context: AbilityContext, params: Mapping[str, Any]) -> int | None:
    """
    Whose choice this is.
    """
    named = params.get("chooser")

    if named is None:
        return context.controller

    for candidate in context.targets.get(str(named), ()):
        if isinstance(candidate, PlayerState):
            return candidate.player_id

    return context.controller


def _named_players(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> list[PlayerState]:
    """
    Whose cards a choice is about: a bound group, or the controller.
    """
    named = params.get("of")

    if named is None:
        if context.controller is None or not 0 <= context.controller < len(state.players):
            return []

        return [state.player(context.controller)]

    if named == "all_players":
        return list(state.players)

    return [
        target
        for target in context.targets.get(str(named), ())
        if isinstance(target, PlayerState)
    ]


def _target_player(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    candidates: list[Any] = [
        player
        for player in state.living_players()
        if not (
            params.get("exclude_controller", False)
            and player.player_id == context.controller
        )
    ]

    candidates = _with_the_most(candidates, params)

    return _ask(DecisionKind.CHOOSE_PLAYER, candidates, context, params, "target_player")


_COUNTABLE: dict[str, Callable[[Any], int]] = {
    "souls": lambda player: player.soul_count,
    "coins": lambda player: player.pennies,
    "loot": lambda player: player.hand_size,
    "treasures": lambda player: player.treasure_count,
}


def _with_the_most(candidates: list[Any], params: Mapping[str, Any]) -> list[Any]:
    """
    Narrow a list of players to those tied for the most of something.

    "A player who controls the most souls or tied for the most" is a
    restriction on who may be chosen, not a separate kind of choosing, so it
    belongs here rather than in a target of its own.
    """
    most = params.get("most")

    if most is None or not candidates:
        return candidates

    try:
        count = _COUNTABLE[str(most)]
    except KeyError:
        raise UnknownTargetError(
            f"cannot count '{most}'; countable things are "
            f"{', '.join(sorted(_COUNTABLE))}"
        ) from None

    best = max(count(player) for player in candidates)

    return [player for player in candidates if count(player) == best]


def _target_curse(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    Let the controller pick a curse to be rid of.

    A curse afflicts a player but is not theirs to keep, so every curse on the
    table is a candidate unless the card says otherwise.
    """
    curses: list[Any] = []

    for player in state.players:
        if params.get("owner") == "controller" and player.player_id != context.controller:
            continue

        curses.extend(player.curses.cards)

    return _ask(DecisionKind.CHOOSE_CARD, curses, context, params, "target_curse")


def _target_monster(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return _ask(
        DecisionKind.CHOOSE_MONSTER,
        _all_monsters(state, context, params, rng),
        context,
        params,
        "target_monster",
    )


def _target_player_or_monster(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    Let the controller pick anything that can be damaged.

    "A monster or player" is one choice on the card and so it is one choice
    here. Offering the two lists separately would make the player answer a
    question the card never asked.
    """
    options: list[Any] = list(state.living_players())
    options.extend(_all_monsters(state, context, params, rng))

    return _ask(
        DecisionKind.CHOOSE_CARD, options, context, params, "target_player_or_monster"
    )


def _target_loot(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    A card out of a hand — the controller's, or one the card names.
    """
    hand: list[Any] = []

    for player in _named_players(state, context, params):
        hand.extend(player.hand.cards)

    return _ask(DecisionKind.CHOOSE_LOOT, hand, context, params, "target_loot")


def _target_soul(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    A soul out of a player's pile.

    Souls are not interchangeable: a bonus soul card counts once and can be
    taken away again, so a card that destroys one has to say which.
    """
    souls: list[Any] = []

    for player in _named_players(state, context, params):
        souls.extend(player.souls.cards)

    return _ask(DecisionKind.CHOOSE_CARD, souls, context, params, "target_soul")


def _target_deck_card(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    Let the controller pick a card out of a named deck.

    Searching a deck is a choice like any other, which is why it is a target
    rather than an effect: the machinery that stops the game and asks already
    exists, and a search is one more question.
    """
    deck = str(params.get("deck", "loot"))
    pile = str(params.get("pile", "deck"))
    zone = getattr(state, f"{deck}_{pile}", None)

    if zone is None:
        raise UnknownTargetError(f"unknown pile '{deck} {pile}'")

    # "Look at the top 5 cards and pick one" is a search of five cards, not of
    # the deck. Without the limit the player would be shown everything.
    depth = params.get("from_top")

    options: list[Any] = (
        list(reversed(zone.cards[-int(depth):]))
        if depth is not None and int(depth) > 0
        else list(reversed(zone.cards))
    )

    card_type = params.get("card_type")

    if card_type is not None:
        options = [
            card
            for card in options
            if str(getattr(getattr(card, "definition", None), "type", "")) == card_type
        ]

    excluded = params.get("exclude_type")

    if excluded is not None:
        options = [
            card
            for card in options
            if str(getattr(getattr(card, "definition", None), "type", "")) != excluded
        ]

    tag = params.get("tag")

    if tag is not None:
        # Cards belong to families — Guppy items, for one — and a card that
        # searches for one asks by the family's name.
        options = [
            card
            for card in options
            if str(tag) in getattr(getattr(card, "definition", None), "tags", ())
        ]

    return _ask(
        DecisionKind.CHOOSE_CARD, options, context, params, "target_deck_card"
    )


def _deck_top(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    Return the top cards of a deck, without asking anybody anything.

    ``exclude`` names a group already bound by this ability and leaves those
    cards out. That is what "put the rest on the bottom" means: the rest is
    what is left after the player has kept one.
    """
    deck = str(params.get("deck", "loot"))
    zone = getattr(state, f"{deck}_deck", None)

    if zone is None:
        raise UnknownTargetError(f"unknown deck '{deck}'")

    count = int(params.get("count", 1))
    cards: list[Any] = list(reversed(zone.cards[-count:])) if count > 0 else []

    excluded = params.get("exclude")

    if excluded is not None:
        kept = context.targets.get(str(excluded), ())

        cards = [card for card in cards if card not in kept]

    return cards


def _target_treasure(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return _ask(
        DecisionKind.CHOOSE_TREASURE,
        _all_treasures(state, context, params, rng),
        context,
        params,
        "target_treasure",
    )


def _holders(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> list[Any]:
    """
    Whose items a treasure target is about.

    ``of`` names a group this ability has already chosen — "choose a player,
    recharge each item they control" — and without it the answer is the
    controller's own items, which is what "an item you control" means.
    """
    named = params.get("of")

    if named is None:
        if context.controller is None or not 0 <= context.controller < len(state.players):
            return []

        return [state.player(context.controller)]

    if named == "all_players":
        return list(state.players)

    return [
        player
        for player in context.targets.get(str(named), ())
        if isinstance(player, PlayerState)
    ]


def _all_monsters(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    Every monster in play, optionally leaving out the one under attack.
    """
    monsters = [
        monster
        for monster in state.active_monsters.cards
        if getattr(monster, "alive", True)
    ]

    if params.get("exclude_attacked", False) and state.combat.active:
        monsters = [monster for monster in monsters if monster is not state.combat.monster]

    return monsters


def _current_monster(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    monsters = _all_monsters(state, context, params, rng)

    return [monsters[-1]] if monsters else []


def _random_monster(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    monsters = _all_monsters(state, context, params, rng)

    if not monsters:
        return []

    return [monsters[rng.randint(0, len(monsters) - 1)]]


def _owned_treasure(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    treasures: list[Any] = []

    for player in _holders(state, context, params):
        treasures.extend(player.treasures.cards)

    return treasures


def _all_treasures(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    Every item that can be pointed at.

    ``owner`` narrows the list the way a card does: "an item you control" is
    ``controller``, "an item another player controls" is ``opponents``.
    ``include_shop`` adds the items for sale, which some cards may take.
    ``exclude_eternal`` leaves out the ones no effect may touch.
    """
    owner = params.get("owner")

    if owner == "controller":
        players = [
            player
            for player in state.players
            if player.player_id == context.controller
        ]
    elif owner == "opponents":
        players = [
            player
            for player in state.players
            if player.player_id != context.controller
        ]
    else:
        players = list(state.players)

    treasures: list[Any] = []

    for player in players:
        treasures.extend(player.treasures.cards)

    if params.get("include_shop", False):
        treasures.extend(state.treasure_shop.cards)

    if params.get("exclude_eternal", False):
        treasures = [
            card
            for card in treasures
            if not getattr(getattr(card, "definition", None), "is_eternal", False)
        ]

    if params.get("exclude_source", False):
        # "Recharge another item" — the item saying so is not another item.
        treasures = [card for card in treasures if card is not context.source]

    return treasures


def _shop_items(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    Everything for sale right now.
    """
    return list(state.treasure_shop.cards)


def _target_shop_item(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    Let the controller pick from what is for sale.
    """
    return _ask(
        DecisionKind.CHOOSE_TREASURE,
        list(state.treasure_shop.cards),
        context,
        params,
        "target_shop_item",
    )


def _top_stack(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return [] if state.stack.is_empty() else [state.stack.peek()]


def _stack_items(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> list[Any]:
    """
    Everything waiting on the stack, top first, optionally by kind.

    The ability doing the asking has already been popped, so a card can never
    cancel itself by cancelling "everything on the stack".
    """
    items = list(reversed(list(state.stack)))

    kinds = params.get("kinds")

    if isinstance(kinds, (list, tuple)):
        wanted = {str(kind) for kind in kinds}
        items = [item for item in items if str(item.kind) in wanted]

    triggers = params.get("triggers")

    if isinstance(triggers, (list, tuple)):
        # A loot card being played and an item being activated are both
        # abilities on the stack; what tells them apart from a triggered
        # ability nobody played is what set them off.
        answered = {str(trigger) for trigger in triggers}

        items = [
            item
            for item in items
            if item.ability is not None and str(item.ability.trigger) in answered
        ]

    return items


def _all_stack(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return _stack_items(state, context, params)


def _target_stack_item(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return _ask(
        DecisionKind.CHOOSE_CARD,
        _stack_items(state, context, params),
        context,
        params,
        "target_stack_item",
    )


def _event_player(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    The player the event being answered is about.

    "Each time a player rolls a 6, deal 1 damage to them" needs a name for
    them, and the event already knows: it is the player who rolled.
    """
    if context.event is None:
        return []

    who = context.event.controller

    if who is None or not 0 <= who < len(state.players):
        return []

    return [state.player(who)]


def _event_source(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    if context.event is None or context.event.source is None:
        return []

    return [context.event.source]


def _previous_target(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return context.last_targets


def _previous_result(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    value = context.last_value

    return [] if value is None else [value]


def _group(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    One group made of several the ability has already bound.

    Some effects are about a pair rather than a list — swapping two cards is
    the obvious one — and the two halves are chosen separately.
    """
    names = params.get("of", ())

    if isinstance(names, str):
        names = [names]

    members: list[Any] = []

    for name in names:
        members.extend(context.targets.get(str(name), ()))

    return members


def _none(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return []
