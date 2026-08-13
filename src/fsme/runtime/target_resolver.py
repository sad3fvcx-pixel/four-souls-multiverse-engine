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

        bound = context.targets.get(name)

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
        register("player", _player_by_index)
        register("target_player", _target_player)

        register("all_monsters", _all_monsters)
        register("current_monster", _current_monster)
        register("monster", _current_monster)
        register("random_monster", _random_monster)
        register("target_monster", _target_monster)

        register("target_player_or_monster", _target_player_or_monster)
        register("target_loot", _target_loot)
        register("target_deck_card", _target_deck_card)
        register("target_treasure", _target_treasure)
        register("owned_treasure", _owned_treasure)
        register("all_treasures", _all_treasures)

        register("top_stack", _top_stack)
        register("event_source", _event_source)
        register("previous_target", _previous_target)
        register("previous_result", _previous_result)

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
    Stop and ask the controller to pick, unless there is nothing to pick from.

    A single option is not a choice, so the engine takes it rather than
    interrupting the game to confirm the obvious. No options at all means the
    ability simply has no target.
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
        player=context.controller,
        minimum=int(params.get("minimum", count)),
        maximum=int(params.get("maximum", count)),
        prompt=str(params.get("prompt", "")),
    )


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

    return _ask(DecisionKind.CHOOSE_PLAYER, candidates, context, params, "target_player")


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
    if context.controller is None or not 0 <= context.controller < len(state.players):
        return []

    hand = list(state.player(context.controller).hand.cards)

    return _ask(DecisionKind.CHOOSE_LOOT, hand, context, params, "target_loot")


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
    zone = getattr(state, f"{deck}_deck", None)

    if zone is None:
        raise UnknownTargetError(f"unknown deck '{deck}'")

    options: list[Any] = list(reversed(zone.cards))

    card_type = params.get("card_type")

    if card_type is not None:
        options = [
            card
            for card in options
            if str(getattr(getattr(card, "definition", None), "type", "")) == card_type
        ]

    return _ask(
        DecisionKind.CHOOSE_CARD, options, context, params, "target_deck_card"
    )


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


def _all_monsters(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return [
        monster
        for monster in state.active_monsters.cards
        if getattr(monster, "alive", True)
    ]


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
    if context.controller is None or not 0 <= context.controller < len(state.players):
        return []

    return list(state.player(context.controller).treasures.cards)


def _all_treasures(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    treasures: list[Any] = []

    for player in state.players:
        treasures.extend(player.treasures.cards)

    return treasures


def _top_stack(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return [] if state.stack.is_empty() else [state.stack.peek()]


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


def _none(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return []
