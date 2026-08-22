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
from types import MappingProxyType
from typing import Any

from fsme.cards.types import CardType
from fsme.content.vocabulary import (
    A_LIST,
    ANY_GROUP,
    CARDS,
    MIXED,
    PASSTHROUGH,
    PLAYERS,
    UNCHECKED,
    ParamShape,
    TargetShape,
)
from fsme.events import EventType
from fsme.rng.rng import RNG
from fsme.stack.item import StackItemType
from fsme.state import DecisionKind, GameState, PlayerState

from .ability_context import AbilityContext
from .errors import DecisionRequired, UnknownTargetError

TargetFn = Callable[[GameState, AbilityContext, Mapping[str, Any], RNG], list[Any]]

WHOLE = "a whole number"
TEXT = "text"
FLAG = "true or false"
LIST = A_LIST


def _shape(*parts: Mapping[str, ParamShape]) -> dict[str, ParamShape]:
    """
    Join the parameter sets a target inherits from the helpers it calls.

    Every target here has the same signature, so what one takes cannot be read
    off it. What can be read is which helper it hands its parameters to, and
    the helper is where they are understood — so each set is written once,
    beside its helper, and each target names the sets it inherits.
    """
    joined: dict[str, ParamShape] = {}

    for part in parts:
        joined.update(part)

    return joined


A_BOUND_GROUP = UNCHECKED
"""
The kind of a parameter that names a group the ability bound earlier.

Deliberately not checked. Answering means resolving an ability's alias graph —
which targets bind which names, in what order, and whether a reference points
at something bound before it is read — and that is a question of its own.
``of`` also accepts the literal ``all_players``, which is not a group at all,
so even the shape of the answer is not settled here.
"""

NOTHING: dict[str, ParamShape] = {}
"""
A target that reads nothing beyond what every target reads. A card writing
parameters into one is not narrowing it — it is being ignored.
"""

EVERY_TARGET = {"as": ParamShape("as", TEXT)}
"""
What ``resolve`` and ``resolve_all`` read, whichever target it is.

``as`` names the group a target binds, and it is the resolver's own: it is
read before the target is looked up and again when the answer is bound. So it
belongs to every target rather than to any helper — which is not obvious, and
was got wrong once before the content said otherwise.
"""


class TargetResolver:
    """
    Resolves the target vocabulary used by card definitions.
    """

    def __init__(self) -> None:
        self._targets: dict[str, TargetFn] = {}
        self._shapes: dict[str, TargetShape] = {}
        self._register_builtin()

    def register(
        self,
        name: str,
        function: TargetFn,
        takes: Mapping[str, ParamShape] | None = None,
        yields: str = "",
        describes: str = "",
    ) -> None:
        """
        Add a target implementation, and say what it is.

        ``describes`` is the target in a person's words — what it picks out,
        not how. An effect has said this since it was written; a target had no
        way to, so anything showing an author a list of targets had to invent
        the words itself, which is a second table.

        ``takes`` is what a card file may write inside this target. Leaving it
        out does not mean the target accepts anything: it means whoever
        registered it did not say, so nothing outside a game may judge its
        parameters. Every target the engine ships says.
        """
        if name in self._targets:
            raise UnknownTargetError(f"target '{name}' is already registered")

        self._targets[name] = function
        self._shapes[name] = TargetShape(
            name=name,
            params=MappingProxyType(_shape(EVERY_TARGET, takes or {})),
            open_ended=takes is None,
            yields=yields,
            describes=describes,
        )

    def names(self) -> frozenset[str]:
        return frozenset(self._targets)

    def shapes(self) -> Mapping[str, TargetShape]:
        """
        What each target takes, as plain data.

        The functions stay here. What leaves is names and kinds, because the
        content pipeline that asks runs before a game exists and must not be
        handed anything that could start one.
        """
        return MappingProxyType(dict(self._shapes))

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

        register("self", _self, NOTHING, CARDS, "this card itself")
        register("source", _self, NOTHING, CARDS, "this card itself")
        register("controller", _controller, NOTHING, PLAYERS, "whoever controls this card")
        register("owner", _owner, NOTHING, PLAYERS, "whoever owns this card")

        register("active_player", _active_player, NOTHING, PLAYERS, "the player whose turn it is")
        register("current_player", _active_player, NOTHING, PLAYERS, "the player whose turn it is")
        register("all_players", _all_players, THE_LIVING, PLAYERS, "every living player")
        register("opponents", _opponents, NOTHING, PLAYERS, "every other player")
        register("another_player", _opponents, NOTHING, PLAYERS, "every other player")
        register("random_player", _random_player, NOT_ME, PLAYERS, "a player at random")
        register("character", _character, NOTHING, CARDS, "your character card")
        register(
            "target_character",
            _target_character,
            ASKING,
            CARDS,
            "a character card somebody picks",
        )
        register("player_left", _player_left, NOTHING, PLAYERS, "the player to the left")
        register("player_right", _player_right, NOTHING, PLAYERS, "the player to the right")
        register("random_loot", _random_loot, WHOSE, CARDS, "a loot card taken blindly from a hand")
        register("player", _player_by_index, BY_SEAT, PLAYERS, "the player in a particular seat")
        register(
            "target_player",
            _target_player,
            A_CHOSEN_PLAYER,
            PLAYERS,
            "a player somebody picks",
        )

        register("all_monsters", _all_monsters, MONSTERS, CARDS, "every monster in play")
        register("current_monster", _current_monster, MONSTERS, CARDS, "the monster being fought")
        register("monster", _current_monster, MONSTERS, CARDS, "the monster being fought")
        register("random_monster", _random_monster, MONSTERS, CARDS, "a monster at random")
        register(
            "target_monster",
            _target_monster,
            _shape(MONSTERS, ASKING),
            CARDS,
            "a monster somebody picks",
        )
        register("target_curse", _target_curse, A_CHOSEN_CURSE, CARDS, "a curse somebody picks")

        register(
            "target_player_or_monster",
            _target_player_or_monster,
            _shape(NOT_ME, MONSTERS, ASKING),
            MIXED,
            "a player or a monster, whichever is picked",
        )
        register(
            "target_loot",
            _target_loot,
            _shape(WHOSE, ASKING),
            CARDS,
            "a loot card somebody picks out of a hand",
        )
        register("target_soul", _target_soul, _shape(WHOSE, ASKING), CARDS, "a soul somebody picks")
        register(
            "target_deck_card",
            _target_deck_card,
            _shape(SEARCHING, ASKING),
            CARDS,
            "a card somebody finds by searching a deck",
        )
        register("deck_top", _deck_top, OFF_THE_TOP, CARDS, "the top cards of a deck")
        register(
            "target_treasure",
            _target_treasure,
            _shape(ITEMS, ASKING),
            CARDS,
            "an item somebody picks",
        )
        register(
            "holder",
            _holder,
            WHOSE_CARDS,
            PLAYERS,
            "whoever is holding a card chosen earlier",
        )
        register("random_treasure", _random_treasure, ITEMS, CARDS, "an item at random")
        register(
            "owned_treasure",
            _owned_treasure,
            OWN_ITEMS,
            CARDS,
            "every item a player controls",
        )
        register("all_treasures", _all_treasures, ITEMS, CARDS, "every item in play")
        register("shop_items", _shop_items, NOTHING, CARDS, "everything for sale in the shop")
        register(
            "target_shop_item",
            _target_shop_item,
            ASKING,
            CARDS,
            "an item somebody picks from the shop",
        )

        register("top_stack", _top_stack, NOTHING, CARDS, "the ability waiting on top of the stack")
        register("all_stack", _all_stack, ON_THE_STACK, CARDS, "everything waiting on the stack")
        register(
            "target_stack_item",
            _target_stack_item,
            _shape(ON_THE_STACK, ASKING),
            CARDS,
            "something waiting on the stack, picked",
        )
        register("event_source", _event_source, NOTHING, CARDS, "the card the event is about")
        register("event_player", _event_player, NOTHING, PLAYERS, "the player the event is about")
        register(
            "previous_target",
            _previous_target,
            NOTHING,
            PASSTHROUGH,
            "whatever the last effect acted on",
        )
        register(
            "previous_result",
            _previous_result,
            NOTHING,
            PASSTHROUGH,
            "whatever the last effect produced",
        )

        register(
            "group",
            _group,
            ANY_BOUND_GROUP,
            PASSTHROUGH,
            "several things chosen earlier, together",
        )
        register(
            "vote",
            _vote,
            _shape(ITEMS, {"prompt": ParamShape("prompt", TEXT)}),
            CARDS,
            "the item every player votes for",
        )
        register(
            "most_common",
            _most_common,
            ANY_BOUND_GROUP,
            PASSTHROUGH,
            "the thing named more often than any other",
        )
        register("none", _none, NOTHING, PASSTHROUGH, "nothing at all")


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


THE_LIVING = {"include_dead": ParamShape("include_dead", FLAG)}
"""
What ``_all_players`` reads. "Each player" means each living player unless a
card says otherwise.
"""


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


def _target_character(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    Any character card at the table, chosen.

    "Recharge up to 1 character" is not "recharge your character": a character
    taps like an item, and waking somebody else's is the point of the card that
    says so.
    """
    characters = [
        player.character
        for player in state.players
        if player.alive and player.character is not None
    ]

    return _ask(
        DecisionKind.CHOOSE_CARD, characters, context, params, "target_character"
    )


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


NOT_ME = {"exclude_controller": ParamShape("exclude_controller", FLAG)}
"""
The difference between "a player" and "another player".
"""


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


BY_SEAT = {
    "value": ParamShape(
        "value", WHOLE, least=0, describes="which seat at the table"
    ),
    "player": ParamShape(
        "player", WHOLE, least=0, describes="which seat at the table"
    ),
}
"""
What ``_player_by_index`` reads. Two spellings of one seat number: the
shorthand ``{"player": 2}`` arrives as ``value``, and the long form says
``player`` outright.
"""


def _player_by_index(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    index = params.get("value", params.get("player"))

    if not isinstance(index, int) or not 0 <= index < len(state.players):
        return []

    return [state.player(index)]


ASKING = {
    "count": ParamShape("count", WHOLE, least=0),
    "minimum": ParamShape("minimum", WHOLE, least=0),
    "maximum": ParamShape("maximum", WHOLE, least=0),
    "prompt": ParamShape("prompt", TEXT),
    "chooser": ParamShape(
        "chooser",
        A_BOUND_GROUP,
        refers_to=PLAYERS,
        describes="who makes the choice, if not the card's controller",
    ),
}
"""
What ``_ask`` reads: how many to pick, and who is being asked.
"""


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

    # A card that says "choose 5" of something there are four of asks for four:
    # a question nobody could answer would stop the game, and the rules read an
    # instruction that cannot be carried out as far as it goes.
    wanted = min(int(params.get("minimum", count)), len(options))
    allowed = min(int(params.get("maximum", count)), len(options))

    raise DecisionRequired(
        kind,
        options,
        bind=str(params.get("as", bind)),
        player=_chooser(context, params),
        minimum=min(wanted, allowed),
        maximum=allowed,
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


WHOSE = {
    "of": ParamShape(
        "of", A_BOUND_GROUP, refers_to=PLAYERS, describes="whose things"
    )
}
"""
What ``_named_players`` reads: whose things, when the card named them.

It keeps only the players out of the group it is handed, so a card naming a
group of items here is naming nobody — which is worth saying before a game.
"""

WHOSE_CARDS = {
    "of": ParamShape(
        "of", A_BOUND_GROUP, refers_to=CARDS, describes="which cards"
    )
}
"""
What ``_holder`` reads. The other way round: it is handed cards and answers
with the players holding them.
"""

ANY_BOUND_GROUP = {
    "of": ParamShape(
        "of",
        A_BOUND_GROUP,
        refers_to=ANY_GROUP,
        describes="which of the things this ability already chose",
    )
}
"""
What ``_group`` reads: one name or several, of anything at all.
"""


def _named_players(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> list[PlayerState]:
    """
    Whose things a target is about, when the card named them.

    ``of`` points at a group this ability has already bound — "choose a
    player, destroy an item they control" is two steps, and this is the second
    one reading the first. Without it the answer is the controller, which is
    what "an item you control" and "a card in your hand" both mean.

    ``all_players`` is the one value that is not a bound group. It is written
    on cards that are about the whole table and would otherwise have to bind a
    group they never use.

    This is the only reading of ``of`` that names players, and every target
    that asks whose things it is about comes here. It used to be written
    twice, once for hands and souls and once for items, and the copies drifted:
    the third place that needed it grew a parameter of its own instead, and two
    cards written against the shared meaning were quietly ignored.
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


THE_MOST = {
    "most": ParamShape("most", TEXT, values=tuple(sorted(_COUNTABLE)))
}
"""
What ``_with_the_most`` reads, over the keys of the table that does the
counting. A thing the engine cannot count is refused at load time by the same
fact that makes it fail at run time.
"""


A_CHOSEN_PLAYER = _shape(NOT_ME, THE_MOST, ASKING)
"""
What ``_target_player`` takes, from the three helpers it passes through.
"""


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


A_CHOSEN_CURSE = _shape(
    {"owner": ParamShape("owner", TEXT, values=("controller",))}, ASKING
)
"""
``owner`` here is not ``owner`` on an item target.

``_target_curse`` tests for ``controller`` and treats everything else as the
whole table, so ``opponents`` — which items understand — would be accepted and
ignored. The domain is the one this target actually has, which is why the
descriptions belong to targets rather than to parameter names.
"""


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

    if params.get("exclude_controller", False):
        # "A monster or another player" excludes one seat and no monsters.
        options = [
            player for player in options if player.player_id != context.controller
        ]

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


def _piles_of(state_type: type) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """
    The decks and piles a card may name, read off the state they are found in.

    ``_target_deck_card`` and ``_deck_top`` look their zone up by building an
    attribute name out of the two words a card wrote. The words that work are
    therefore the attributes that exist, and reading them here is the same
    fact rather than a second copy of it — a list written out again would be
    free to drift from the lookup it is supposed to describe.
    """
    from dataclasses import fields

    names = {field.name for field in fields(state_type)}
    decks = tuple(sorted({n.rsplit("_", 1)[0] for n in names if n.endswith("_deck")}))
    piles = tuple(
        sorted(
            {
                n.rsplit("_", 1)[1]
                for n in names
                if "_" in n
                and n.rsplit("_", 1)[0] in decks
                and n.rsplit("_", 1)[1] in ("deck", "discard")
            }
        )
    )

    return decks, piles


DECKS, PILES = _piles_of(GameState)

CARD_TYPES = tuple(str(kind) for kind in CardType)

SEARCHING = {
    "deck": ParamShape("deck", TEXT, values=DECKS),
    "pile": ParamShape("pile", TEXT, values=PILES),
    "from_top": ParamShape("from_top", WHOLE, least=1),
    "card_type": ParamShape("card_type", TEXT, values=CARD_TYPES),
    "exclude_type": ParamShape("exclude_type", TEXT, values=CARD_TYPES),
    "tag": ParamShape("tag", TEXT),
    "named": ParamShape("named", TEXT),
}
"""
What ``_target_deck_card`` reads. A misspelt deck stops the game today, deep
inside a study and naming no card; this is the same knowledge asked earlier.
"""

OFF_THE_TOP = {
    "deck": ParamShape("deck", TEXT, values=DECKS),
    "count": ParamShape("count", WHOLE, least=0),
    "exclude": ParamShape(
        "exclude",
        A_BOUND_GROUP,
        refers_to=CARDS,
        describes="cards to leave out",
    ),
}
"""
What ``_deck_top`` reads. ``count`` is how many cards, not how many to choose:
the same word, a different question from ``_ask``'s.
"""


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

    named = params.get("named")

    if named is not None:
        # "Search the monster deck for a card named The Bloat" asks for one
        # card by its printed name, which is not a family and not a type.
        options = [
            card
            for card in options
            if str(getattr(getattr(card, "definition", None), "name", "")) == str(named)
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


def _holder(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    The player holding a card this ability has already named.

    "Destroy that item and replace it with the top card of the treasure deck"
    replaces it for whoever owned it, which need not be the player doing the
    destroying — so the card has to be able to point at its holder rather than
    at a seat.
    """
    named = params.get("of")

    if named is None:
        return []

    seats: list[Any] = []

    for card in context.targets.get(str(named), ()):
        seat = getattr(card, "controller", None)

        if seat is None:
            seat = getattr(card, "owner", None)

        if seat is None or not 0 <= int(seat) < len(state.players):
            continue

        player = state.player(int(seat))

        if player not in seats:
            seats.append(player)

    return seats


MONSTERS = {"exclude_attacked": ParamShape("exclude_attacked", FLAG)}
"""
What ``_all_monsters`` reads.
"""


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


OWN_ITEMS = _shape(WHOSE, {"exclude_eternal": ParamShape("exclude_eternal", FLAG)})
"""
What ``_owned_treasure`` reads: whose items, and whether the untouchable ones
are among them.
"""


def _owned_treasure(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    The items some player controls.

    ``exclude_eternal`` leaves out the ones no effect may touch, and means the
    same thing here as everywhere else: a card that says "each item they
    control other than eternal ones" must not be handed one, or it will do the
    rest of its work once too often — destroying nothing and replacing it all
    the same.
    """
    treasures: list[Any] = []

    for player in _named_players(state, context, params):
        treasures.extend(player.treasures.cards)

    if params.get("exclude_eternal", False):
        treasures = [
            card for card in treasures if not getattr(card, "is_eternal", False)
        ]

    return treasures


ITEMS = _shape(
    WHOSE,
    {
        "owner": ParamShape("owner", TEXT, values=("controller", "opponents")),
        "include_shop": ParamShape("include_shop", FLAG),
        "exclude_eternal": ParamShape("exclude_eternal", FLAG),
        "exclude_source": ParamShape("exclude_source", FLAG),
        "counter": ParamShape("counter", TEXT),
        "tag": ParamShape("tag", TEXT),
    },
)
"""
What ``_all_treasures`` reads. Whose items may be said either way — a role, or
a group the ability bound — so both are here.
"""


def _all_treasures(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    Every item that can be pointed at.

    Whose items may be said two ways, and both are the card's own words.
    ``owner`` names a role: "an item you control" is ``controller``, "an item
    another player controls" is ``opponents``. ``of`` names a group this
    ability has already bound: "choose a player at random, that player
    destroys an item they control" cannot be a role, because the player chosen
    may turn out to be anybody.

    ``of`` means here exactly what it means for a hand or a pile of souls, and
    is read by the same helper. It did not used to be read at all, and the two
    cards written with it were handed every item on the table instead.

    With neither, every item is a candidate — a card that does not say whose
    is not asking about anybody in particular.

    ``include_shop`` adds the items for sale, which some cards may take.
    ``exclude_eternal`` leaves out the ones no effect may touch.
    """
    owner = params.get("owner")

    if "of" in params:
        players = _named_players(state, context, params)
    elif owner == "controller":
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
            if not getattr(card, "is_eternal", False)
        ]

    if params.get("exclude_source", False):
        # "Recharge another item" — the item saying so is not another item.
        treasures = [card for card in treasures if card is not context.source]

    counter = params.get("counter")

    if counter is not None:
        # "An item with a gold counter on it" is a family the game made rather
        # than one the card was printed with.
        treasures = [
            card
            for card in treasures
            if int(getattr(card, "counters", {}).get(str(counter), 0)) > 0
        ]

    tag = params.get("tag")

    if tag is not None:
        # "A non-eternal passive item" is a family, and a card that is copying
        # another card's rules belongs to the family it is wearing.
        treasures = [card for card in treasures if card.has_tag(str(tag))]

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


ON_THE_STACK = {
    "kinds": ParamShape(
        "kinds",
        LIST,
        values=tuple(str(kind) for kind in StackItemType),
        describes="which sorts of thing on the stack",
    ),
    "triggers": ParamShape(
        "triggers",
        LIST,
        values=tuple(str(event) for event in EventType),
        describes="which moments the thing on the stack reacted to",
    ),
}
"""
What ``_stack_items`` reads: two lists, each drawn from the enum the filter
compares against. A list's ``values`` are what each of its items may be.
"""


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


def _random_treasure(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    One item taken blindly from those a card is talking about.

    "Destroy a non-eternal item you control chosen at random" is nobody's
    choice, so nobody is asked and the RNG is consumed here in a documented
    order.
    """
    options = _all_treasures(state, context, dict(params), rng)

    if not options:
        return []

    return [options[rng.randint(0, len(options) - 1)]]


def _vote(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    Ask every living player to pick one thing, one player at a time.

    A vote is several questions, not one, and they are asked in seating order
    so that a replayed game asks them in the same order. Each answer is bound
    under a name of its own, which is what lets the ability be suspended and
    resumed once per voter — the votes already cast are found waiting rather
    than asked again.

    The result is every vote, in the order cast, duplicates and all: who won is
    a separate question, and counting is not this function's business.
    """
    name = str(params.get("as", "vote"))
    options = _all_treasures(state, context, dict(params), rng)

    if not options:
        return []

    votes: list[Any] = []

    for player in state.players:
        if not player.alive:
            continue

        cast = context.targets.get(f"{name}:{player.player_id}")

        if cast is None:
            raise DecisionRequired(
                DecisionKind.CHOOSE_TREASURE,
                options,
                bind=f"{name}:{player.player_id}",
                player=player.player_id,
                prompt=str(params.get("prompt", "")),
            )

        votes.extend(cast)

    return votes


def _most_common(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    """
    The one thing a group names more often than any other.

    A tie is not a winner: "if there is a tie, nothing happens" is what the
    card says, and an empty answer is how an ability says nothing happened.
    """
    counted: list[tuple[Any, int]] = []

    for member in _group(state, context, params, rng):
        for index, (candidate, votes) in enumerate(counted):
            if candidate is member:
                counted[index] = (candidate, votes + 1)
                break
        else:
            counted.append((member, 1))

    if not counted:
        return []

    most = max(votes for _, votes in counted)
    winners = [candidate for candidate, votes in counted if votes == most]

    return winners if len(winners) == 1 else []


def _none(
    state: GameState, context: AbilityContext, params: Mapping[str, Any], rng: RNG
) -> list[Any]:
    return []
