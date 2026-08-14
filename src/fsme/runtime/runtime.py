# src/fsme/runtime/runtime.py

"""
The engine's execution core.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

from fsme.cards import Ability, CardInstance, CardRegistry
from fsme.commands import (
    Command,
    CommandRegistry,
    CommandResult,
    CommandType,
    UnknownCommandError,
)
from fsme.effects import EffectOp, EffectRegistry, builtin_registry
from fsme.events import Event, EventBus, EventType
from fsme.rng.rng import RNG
from fsme.stack import SETTLE_ROLL, StackItem, StackItemType
from fsme.state import GameState, PendingDecision, PendingRoll, PlayerState

from .ability_context import AbilityContext
from .condition_evaluator import NTH_TIME, TIMES_THIS_TURN, ConditionEvaluator
from .effect_executor import EffectExecutor
from .errors import (
    AbilityResolutionError,
    DecisionRequired,
    InterpreterError,
    RollRequired,
    StabilityError,
)
from .execution_context import ExecutionContext
from .interpreter import Interpreter
from .target_resolver import TargetResolver

if TYPE_CHECKING:
    from fsme.rules import ProcedureRegistry

DEFAULT_MAX_ITERATIONS = 512

MAX_REPLACEMENT_DEPTH = 8
"""
How deeply replacements may nest.

A replacement that causes another event which is itself replaced is legal; an
unbounded chain of them is a content bug, and the engine says so rather than
hanging.
"""

SELF_SCOPED_TRIGGERS = frozenset(
    {
        "on_enter",
        "on_leave",
        "on_destroy",
        "on_discard",
        "on_gain",
        "on_lose",
        "on_play",
        "before_activate",
        "on_activate",
        "after_activate",
        "treasure_charged",
        "treasure_deactivated",
        "treasure_destroyed",
        "treasure_stolen",
    }
)
"""
Triggers that concern one specific card.

Activating an item fires that item's ability, not every item in play. Triggers
outside this set — a turn starting, a monster dying — concern the whole table.
"""

OUT_OF_PLAY_ZONES = (
    "monster_discard",
    "loot_discard",
    "treasure_discard",
    "room_discard",
)
"""
Where a card may still be doing something without being in play.

Only the abilities that name one of these are ever looked at there, so the
piles cost a glance per card and nothing more.
"""

RESPONSE_COMMANDS = frozenset(
    {
        CommandType.PASS_PRIORITY,
        CommandType.ACTIVATE_TREASURE,
        CommandType.PLAY_LOOT,
    }
)
"""
What a player may do while holding priority.

STACK.md section 9: during a priority window players may activate abilities,
play loot cards, or pass. Everything else waits until the stack is empty.
"""


def ability_scope(ability: Ability) -> str:
    """
    Return the effective scope of an ability.
    """
    if ability.scope is not None:
        return ability.scope

    return "self" if ability.trigger in SELF_SCOPED_TRIGGERS else "any"


def in_scope(ability: Ability, card: CardInstance, event: Event) -> bool:
    """
    Decide whether an ability may react to an event at all.

    ``self`` is the card's own business: activating one item does not fire
    every item. ``controller`` is its holder's business, which is what a card
    means by "you" — "each time you take damage" is not each time anybody does.
    ``any`` is the whole table's.
    """
    scope = ability_scope(ability)

    if scope == "self":
        # The card's own business either way: it may be what the event is
        # about — an item being activated — or what the event happened to,
        # which is what a monster means by "each time this takes damage".
        return event.source is card or any(target is card for target in event.targets)

    if scope == "controller":
        return card.controller is not None and event.controller == card.controller

    return True


def counting_conditions(
    conditions: tuple[Any, ...],
) -> tuple[list[Any], list[Any]]:
    """
    Split an ability's conditions into the counting one and the rest.

    "The third time a player rolls a 6 each turn" counts sixes, not rolls, so
    the tally is kept only when everything else the card asks for is already
    true. The occurrence condition is therefore held back and asked last,
    against the count it just caused.

    Only a condition written at the top level is recognised; one buried inside
    an ``or`` is asked with the others and counts nothing.
    """
    from .condition_evaluator import normalise

    counting: list[Any] = []
    rest: list[Any] = []

    for node in conditions:
        name, _ = normalise(node)

        (counting if name == NTH_TIME else rest).append(node)

    return counting, rest


def names_ability(event: Event, card: CardInstance, ability: Ability) -> bool:
    """
    Decide whether an event naming one ability of a card names this one.

    An item with a tap ability and a paid ability is two abilities on one card,
    and activating it uses exactly one. Events that name no ability concern
    every ability that listens, as they always did.
    """
    index = event.get("ability_index")

    if index is None or event.source is not card:
        return True

    abilities = card.face.abilities_for(str(event.type))

    return bool(0 <= int(index) < len(abilities) and abilities[int(index)] is ability)


class Runtime:
    """
    Owns a running game and is the only thing allowed to change it.

    The Runtime implements the loop described in ENGINE_EXECUTION_MODEL.md:
    accept a command, drain the event queue, let events trigger abilities,
    resolve the stack from the top, apply State-Based Actions, and repeat until
    nothing is pending. Everything else in the engine either describes the game
    (content), states its rules (rules), or observes it (UI, replay, tests).
    """

    def __init__(
        self,
        state: GameState,
        *,
        cards: CardRegistry | None = None,
        effects: EffectRegistry | None = None,
        commands: CommandRegistry | None = None,
        procedures: ProcedureRegistry | None = None,
        rng: RNG | None = None,
        interactive_priority: bool = False,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        # Imported here rather than at module level: the rules read the
        # Runtime's condition evaluator, and the Runtime reads the rules for
        # its defaults. Deferring one direction lets either package be
        # imported first without the other being half-built.
        from fsme.rules import default_command_registry, default_procedure_registry

        self._state = state
        self._cards = cards if cards is not None else CardRegistry()
        self._effects = effects if effects is not None else builtin_registry()
        self._commands = (
            commands if commands is not None else default_command_registry()
        )
        self._procedures = (
            procedures if procedures is not None else default_procedure_registry()
        )
        self._rng = rng if rng is not None else RNG(state.seed)

        self._bus = EventBus()
        self._conditions = ConditionEvaluator()
        self._target_resolver = TargetResolver()
        self._interpreter = Interpreter(
            self._conditions, self._target_resolver, self._effects
        )
        self._executor = EffectExecutor(self._effects, self._target_resolver)

        self._context = ExecutionContext(
            state,
            self._rng,
            self._effects,
            emit=self._enqueue,
            push=self._push,
            propose=self._propose,
            request_roll=self._request_roll,
        )

        self._interactive_priority = interactive_priority
        self._max_iterations = max_iterations

        # A roll is worth stopping for only when somebody could answer it.
        self._context._set_answerable_rolls(interactive_priority)

        self._history: list[Event] = []
        self._command_log: list[CommandResult] = []
        self._replacement_depth = 0

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def cards(self) -> CardRegistry:
        return self._cards

    @property
    def effects(self) -> EffectRegistry:
        return self._effects

    @property
    def commands(self) -> CommandRegistry:
        return self._commands

    @property
    def procedures(self) -> ProcedureRegistry:
        return self._procedures

    @property
    def rng(self) -> RNG:
        return self._rng

    @property
    def context(self) -> ExecutionContext:
        return self._context

    @property
    def history(self) -> tuple[Event, ...]:
        """
        Every event this Runtime has processed, in order.

        This is the raw material of the replay log.
        """
        return tuple(self._history)

    @property
    def command_log(self) -> tuple[CommandResult, ...]:
        """
        Every command submitted, accepted or not, with its outcome.
        """
        return tuple(self._command_log)

    @property
    def awaiting_decision(self) -> PendingDecision | None:
        """
        The question the engine is waiting on, if any.
        """
        return self._state.pending_decision

    @property
    def awaiting_priority(self) -> bool:
        """
        Return True while the engine is waiting for players to respond.
        """
        return self._state.priority.is_open

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], Any],
    ) -> None:
        """
        Observe events. Observers never change the game.
        """
        self._bus.subscribe(event_type, handler)

    def is_stable(self) -> bool:
        """
        Return True when no gameplay work is pending.
        """
        return self._state.is_stable() and not self._pending_state_based_actions()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def submit(self, command: Command) -> CommandResult:
        """
        Validate a command and, if it is legal, carry it out.

        A rejected command leaves the game exactly as it was — it is not even
        given an identifier, because allocating one would advance state that a
        replay has to reproduce.
        """
        reason = self._refuse_reason(command)

        if reason is not None:
            return self._log(CommandResult.reject(command, reason))

        try:
            handler = self._commands.handler(command.type)
        except UnknownCommandError as error:
            return self._log(CommandResult.reject(command, str(error)))

        reason = handler.validate(command, self._state)

        if reason is not None:
            return self._log(CommandResult.reject(command, reason))

        command.command_id = self._state.ids.allocate("command")
        command.sequence = self._state.ids.counter

        first_event = len(self._history)

        self._context._set_actor(command.player)

        try:
            handler.execute(command, self._context)
        finally:
            self._context._set_actor(None)

        self.run()

        # The generator's position is part of the game, not of the session: a
        # replay compares it, and a save has to reload rolling the same dice.
        # It is written down at the one moment the game is quiet enough for it
        # to mean anything — after a command has been fully carried out.
        self._state.rng_state = self._rng.get_state()

        return self._log(
            CommandResult.accept(command, tuple(self._history[first_event:]))
        )

    def _refuse_reason(self, command: Command) -> str | None:
        """
        Return why the engine cannot even look at a command right now.
        """
        if not 0 <= command.player < len(self._state.players):
            return f"unknown player {command.player}"

        decision = self._state.pending_decision

        if decision is not None:
            if command.type is CommandType.CHOOSE_TARGET:
                return None

            return (
                f"'{command.type}' must wait: player {decision.player} "
                f"is still choosing"
            )

        if self.awaiting_priority:
            if command.type in RESPONSE_COMMANDS:
                return None

            return (
                f"'{command.type}' is not a response; "
                f"the stack is waiting on priority"
            )

        if not self._state.is_stable():
            return "the engine is still resolving; no command may be accepted"

        return None

    def _log(self, result: CommandResult) -> CommandResult:
        self._command_log.append(result)

        return result

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def emit(
        self,
        event_type: EventType,
        *,
        source: Any | None = None,
        controller: int | None = None,
        targets: list[Any] | None = None,
        **payload: Any,
    ) -> Event:
        """
        Queue an event without running the loop.
        """
        return self._context.emit(
            event_type,
            source=source,
            controller=controller,
            targets=targets,
            **payload,
        )

    def dispatch(
        self,
        event_type: EventType,
        *,
        source: Any | None = None,
        controller: int | None = None,
        targets: list[Any] | None = None,
        **payload: Any,
    ) -> Event:
        """
        Queue an event and run the engine until it stops.
        """
        event = self.emit(
            event_type,
            source=source,
            controller=controller,
            targets=targets,
            **payload,
        )

        self.run()

        return event

    def run(self) -> None:
        """
        Process pending work until the game is stable or waiting on players.
        """
        for _ in range(self._max_iterations):
            decision = self._state.pending_decision

            if decision is not None:
                if decision.chosen is None:
                    return

                self._resume(decision)
                continue

            if not self._state.events.is_empty():
                self._process_event(self._state.events.pop())
                continue

            if self._state.game_over:
                self._abandon_pending_work()
                return

            if not self._state.stack.is_empty():
                if self.awaiting_priority:
                    # The table is about to be asked what it wants to do, and
                    # it must be asked about a position the rules already
                    # agree with: a player at no hit points is dead before
                    # anybody responds to anything, not after. A death queued
                    # here is answerable like any other, which is the whole
                    # point of asking now rather than later.
                    if self._state_based_actions():
                        continue

                    return

                self._resolve_top()
                self._state_based_actions()
                self._open_priority_window()
                continue

            if self._state_based_actions():
                continue

            return

        raise StabilityError(
            f"game state did not stabilise within {self._max_iterations} steps"
        )

    # ------------------------------------------------------------------
    # Mutation channel
    # ------------------------------------------------------------------

    def _enqueue(self, event: Event) -> Event:
        """
        Assign identity to an event and queue it.
        """
        event.event_id = self._state.ids.allocate("event")
        event.sequence = self._state.ids.counter

        self._state.events.push(event)

        return event

    def _push(self, item: StackItem) -> StackItem:
        """
        Place an item on the stack, announce it and reopen priority.
        """
        item.stack_id = self._state.ids.allocate("stack")
        item.order = self._state.ids.counter

        self._state.stack.push(item)

        self._context.emit(
            EventType.STACK_PUSH,
            source=item.source,
            controller=item.controller,
            stack_id=item.stack_id,
        )

        self._open_priority_window()

        return item

    def _abandon_pending_work(self) -> None:
        """
        Drop everything still pending once the game has been won.

        A finished game does not finish resolving: the effects waiting on the
        stack, the attack in progress and any open priority window are all
        answers to a question nobody is asking any more. Queued events are
        delivered first, so observers still see the game end.
        """
        self._state.stack.clear()
        self._state.priority.close()
        self._state.combat.end()
        self._state.pending_decision = None

    def _propose(self, event: Event) -> Event:
        """
        Let replacement abilities edit an event, then queue it.

        EVENT_SYSTEM.md separates two ways of answering an event. A
        replacement changes it before it happens and never touches the stack;
        a triggered ability waits its turn and resolves afterwards. Both get
        their chance here: replacements run immediately, and the event is then
        queued so ordinary triggers still see it — modified, or cancelled and
        recorded as such.
        """
        self._apply_replacements(event)

        return self._enqueue(event)

    def _apply_replacements(self, event: Event) -> None:
        """
        Run every replacement ability that applies to an event, once each.
        """
        if self._replacement_depth >= MAX_REPLACEMENT_DEPTH:
            raise StabilityError(
                f"replacement effects nested more than "
                f"{MAX_REPLACEMENT_DEPTH} deep on {event.type}"
            )

        self._replacement_depth += 1

        try:
            for card, ability in self._replacements_for(event):
                label = f"{card.instance_id}:{ability.trigger}"

                if label in event.replacements_applied:
                    continue

                event.replacements_applied.append(label)

                self._run_replacement(card, ability, event)

                if event.cancelled:
                    return

            self._keep_promises(event)
            self._spend_shield(event)
        finally:
            self._replacement_depth -= 1

    def _keep_promises(self, event: Event) -> None:
        """
        Apply the changes owed to this event by cards that have already gone.

        Promises are kept after the cards in play have replaced what they
        replace and before any shield is spent, so that "the next instance of
        damage is reduced to 1" meets the damage before prevention does and
        prevention has the smaller number to work on.
        """
        player_id: int | None = None
        card_ids: set[str] = set()

        for target in event.targets:
            if player_id is None:
                player_id = getattr(target, "player_id", None)

            instance_id = getattr(target, "instance_id", None)

            if instance_id is not None:
                card_ids.add(str(instance_id))

        kept = frozenset(card_ids)

        for promise in list(self._state.promises):
            if promise.event != str(event.type):
                continue

            if not promise.concerns(player_id, kept):
                continue

            if not promise.about(event.payload):
                continue

            for key, value in promise.apply_to(event.payload).items():
                event.set(key, value)

            if not promise.spend():
                self._state.promises.remove(promise)

    def _spend_shield(self, event: Event) -> None:
        """
        Let a promised prevention meet the damage it was promised against.

        A shield is not a card and has no ability, so it cannot be found among
        the replacements; it is stored on the game and spent here, after the
        cards have had their say. One instance of damage spends one shield,
        which is what "the next instance of up to N damage" means.
        """
        if event.type is not EventType.BEFORE_DAMAGE:
            return

        for target in event.targets:
            player_id = getattr(target, "player_id", None)

            if player_id is None:
                continue

            for shield in self._state.shields:
                if shield.player_id != player_id:
                    continue

                before = int(event.get("amount", 0))
                after = max(0, before - shield.stops(before))

                event.set("amount", after)
                self._state.shields.remove(shield)

                if before > after:
                    # Announced, because cards care that they prevented damage
                    # and not only that they took none: "when you prevent
                    # damage this way, deal 1 damage to another player".
                    self._enqueue(
                        Event(
                            type=EventType.DAMAGE_PREVENTED,
                            controller=player_id,
                            targets=[target],
                            payload={
                                "amount": before - after,
                                "shield": shield.label,
                            },
                        )
                    )

                if after == 0:
                    event.cancel()

                return

    def _replacements_for(self, event: Event) -> list[tuple[CardInstance, Ability]]:
        """
        Find the replacement abilities watching for an event.
        """
        from fsme.rules import record_trigger

        matches: list[tuple[CardInstance, Ability]] = []

        for card in self._candidates(event):
            for ability in card.face.abilities_for(str(event.type)):
                if not ability.replacement:
                    continue

                if not in_scope(ability, card, event):
                    continue

                if not names_ability(event, card, ability):
                    continue

                probe = AbilityContext(
                    source=card,
                    ability=ability,
                    controller=self._controller_for(card, event),
                    owner=card.owner,
                    event=event,
                )

                counting, rest = counting_conditions(ability.conditions)

                if not self._conditions.evaluate_all(rest, self._state, probe):
                    continue

                # Counted once everything else the card asks for is true, and
                # before the occurrence is asked about: a card that acts only
                # the first time still watched the other times go by.
                probe.store(TIMES_THIS_TURN, record_trigger(self._state, card, ability))

                if self._conditions.evaluate_all(counting, self._state, probe):
                    matches.append((card, ability))

        return matches

    def _run_replacement(
        self,
        card: CardInstance,
        ability: Ability,
        event: Event,
    ) -> None:
        """
        Execute one replacement ability against the event it is editing.
        """
        context = AbilityContext(
            source=card,
            ability=ability,
            controller=self._controller_for(card, event),
            owner=card.owner,
            event=event,
        )

        # A replacement may cause an event that is itself replaced, and the
        # inner replacement must hand the outer one its event back when it is
        # done. Clearing to nothing would leave the outer ability editing an
        # event the engine no longer remembers, halfway through editing it.
        outer_event = self._context.event
        outer_source = self._context.source

        self._context._set_event(event)
        self._context._set_source(card)

        # A replacement that rolls a die rolls it here and now. The table
        # answers a roll by responding to it, and there is nothing yet to
        # respond to: the event being replaced has not happened. So the roll is
        # taken unanswered, for the same reason the decision below is refused.
        answerable = self._context.answerable_rolls

        self._context._set_answerable_rolls(False)

        try:
            self._target_resolver.resolve_all(
                ability.targets, self._state, context, self._rng
            )

            self._run_replacement_ops(ability, context)

        except DecisionRequired:
            # A replacement applies at once or not at all: there is no moment
            # in which to stop and ask, because the event it is editing has
            # not happened yet and nothing else can proceed until it has.
            raise AbilityResolutionError(
                f"replacement ability on '{card.id}' asked for a decision; "
                f"replacements must resolve without input"
            ) from None

        finally:
            self._context._set_answerable_rolls(answerable)
            self._context._set_event(outer_event)
            self._context._set_source(outer_source)

    def _run_replacement_ops(
        self,
        ability: Ability,
        context: AbilityContext,
    ) -> None:
        """
        Run a replacement's operations, opening control flow as it goes.
        """
        ops = self._interpreter.build(ability.effects)
        index = 0

        while index < len(ops):
            op = ops[index]

            if self._interpreter.is_control(op):
                expansion, stopped = self._interpreter.expand(
                    op, self._state, context, self._rng
                )

                if stopped:
                    ops[index:] = expansion
                else:
                    ops[index : index + 1] = expansion

                continue

            self._executor.execute(op, self._context, context)
            index += 1

    def _open_priority_window(self) -> None:
        """
        Give players the chance to answer the top of the stack.

        Priority starts with the active player and passes in seat order. In
        non-interactive games no window opens at all: every player is treated
        as having passed immediately, which is what lets tests, AI and balance
        simulations run a game without an input source.
        """
        if not self._interactive_priority:
            return

        if self._state.stack.is_empty():
            self._state.priority.close()
            return

        self._state.priority.open_window(self._state.turn.active_player)

    # ------------------------------------------------------------------
    # Event processing
    # ------------------------------------------------------------------

    def _process_event(self, event: Event) -> None:
        """
        Deliver one event to observers and to the abilities watching for it.
        """
        if event.cancelled:
            self._history.append(event)
            return

        event.mark_resolving()

        self._bus.emit(event)

        if not event.cancelled:
            for source, ability in self._triggered_by(event):
                self._push_ability(source, ability, event)

            self._wake_watchers(event)

            event.mark_resolved()

        self._history.append(event)

    def _triggered_by(self, event: Event) -> list[tuple[CardInstance, Ability]]:
        """
        Find every ability that reacts to an event and may legally do so.

        Conditions are checked here, before anything is placed on the stack,
        because a condition that fails must leave no trace of the ability at
        all.
        """
        from fsme.rules import record_trigger

        matches: list[tuple[CardInstance, Ability]] = []

        from fsme.rules import cards_in_play

        in_play = {id(card) for card in cards_in_play(self._state)}

        # Whatever the event is about answers for itself wherever it is: a
        # loot card being played is in no zone, and a monster answering the
        # blow that killed it is already off the table.
        about = {id(event.source)} | {id(target) for target in event.targets}

        for card in self._candidates(event):
            for ability in card.face.abilities_for(str(event.type)):
                if id(card) not in about and not self._where_it_works(
                    card, ability, in_play
                ):
                    continue

                if ability.replacement:
                    # A replacement already had its say before the event was
                    # queued. It is not also a trigger, or preventing damage
                    # would prevent it and then react to it.
                    continue

                if not in_scope(ability, card, event):
                    continue

                if not names_ability(event, card, ability):
                    continue

                probe = AbilityContext(
                    source=card,
                    ability=ability,
                    controller=self._controller_for(card, event),
                    owner=card.owner,
                    event=event,
                )

                counting, rest = counting_conditions(ability.conditions)

                if not self._conditions.evaluate_all(rest, self._state, probe):
                    continue

                # Counted once everything else the card asks for is true, and
                # before the occurrence is asked about: a card that acts only
                # the first time still watched the other times go by.
                probe.store(TIMES_THIS_TURN, record_trigger(self._state, card, ability))

                if self._conditions.evaluate_all(counting, self._state, probe):
                    matches.append((card, ability))

        return matches

    def _where_it_works(
        self,
        card: CardInstance,
        ability: Ability,
        in_play: set[int],
    ) -> bool:
        """
        Whether this ability works from where its card is standing.

        An ability naming a zone works there and nowhere else; an ability
        naming none works in play and nowhere else. Which is why a card in the
        discard pile does not go on quietly doing what it did on the table.

        The card the event is about is exempt: a loot card being played is in
        no zone at all, and a monster answering the blow that killed it has
        already left the table.
        """
        if not ability.zone:
            return id(card) in in_play

        zone = getattr(self._state, ability.zone, None)

        return zone is not None and any(
            held is card for held in getattr(zone, "cards", ())
        )

    def _wake_watchers(self, event: Event) -> None:
        """
        Let abilities with no card in play answer an event.

        A watcher is a triggered ability that outlived the card that set it up,
        so it is placed on the stack exactly as one, and the card it came from
        is still named as its source — a card in the discard pile is still the
        reason the ability is resolving.
        """
        for watcher in list(self._state.watchers):
            if watcher.event != str(event.type):
                continue

            if event.event_id and event.event_id in watcher.fired:
                continue

            player_id = event.controller

            for target in event.targets:
                seat = getattr(target, "player_id", None)

                if seat is not None:
                    player_id = seat
                    break

            if not watcher.concerns(player_id):
                continue

            ability = Ability(
                trigger=watcher.event,
                conditions=tuple(watcher.conditions),
                effects=tuple(watcher.effects),
                scope="any",
            )

            probe = AbilityContext(
                source=watcher.source,
                ability=ability,
                controller=watcher.controller,
                event=event,
            )

            if event.event_id:
                watcher.fired.append(event.event_id)

            if not self._conditions.evaluate_all(
                ability.conditions, self._state, probe
            ):
                # The event was not what the card was hoping for. Whether that
                # uses the watcher up is the card's business: a die that showed
                # something else was still the next roll.
                if not watcher.waits and not watcher.spend():
                    self._state.watchers.remove(watcher)

                continue

            self._push(
                StackItem(
                    kind=StackItemType.TRIGGERED_ABILITY,
                    label=watcher.label or f"watcher:{watcher.event}",
                    source=watcher.source,
                    ability=ability,
                    controller=watcher.controller,
                    event=event,
                )
            )

            if not watcher.spend():
                self._state.watchers.remove(watcher)

    @staticmethod
    def _controller_for(card: CardInstance, event: Event) -> int | None:
        """
        Decide who controls an ability while it resolves.

        A card nobody owns — a monster, a room — still has abilities, and they
        act on behalf of the player the event concerns. That is how a monster
        card can award its soul to whoever killed it without naming anyone.
        """
        if card.controller is not None:
            return card.controller

        return event.controller

    def _candidates(self, event: Event) -> Iterator[CardInstance]:
        """
        Yield every card that could react to an event, without repeats.

        The card the event is about comes first, even when it sits in no zone
        at all. A loot card being played has already left its owner's hand and
        has not yet reached the discard pile, and it still has to be able to do
        what it says. Coming first also puts it lowest on the stack, so any
        response to it resolves before it does.

        The cards the event happened *to* come next, for the same reason: a
        monster that answers the damage it takes must still answer the damage
        that killed it, and by the time triggers are matched the killing blow
        has already swept it off the table.
        """
        seen: set[int] = set()

        source = event.source

        if isinstance(source, CardInstance):
            seen.add(id(source))
            yield source

        for target in event.targets:
            if isinstance(target, CardInstance) and id(target) not in seen:
                seen.add(id(target))
                yield target

        for card in self._ability_sources():
            if id(card) in seen:
                continue

            seen.add(id(card))
            yield card

        for card in self._watching_from_elsewhere():
            if id(card) in seen:
                continue

            seen.add(id(card))
            yield card

    def _watching_from_elsewhere(self) -> Iterator[CardInstance]:
        """
        Yield the cards that act from somewhere other than play.

        A discard pile is not in play and almost nothing in it can do anything.
        The exceptions say so on their abilities, by naming the zone they work
        from, and only those are looked at here.
        """
        for name in OUT_OF_PLAY_ZONES:
            zone = getattr(self._state, name, None)

            if zone is None:
                continue

            for card in zone.cards:
                if not isinstance(card, CardInstance):
                    continue

                if any(ability.zone for ability in card.face.abilities):
                    yield card

    def _ability_sources(self) -> Iterator[CardInstance]:
        """
        Yield every card in play able to trigger, in a fixed order.

        "In play" is one list, shared with static modifiers, so a card cannot
        be live for one and dead for the other. The order is part of
        determinism: players by seat, then their cards in zone order, then the
        shared board.
        """
        from fsme.rules import cards_in_play

        yield from cards_in_play(self._state)

    def _push_ability(
        self,
        source: CardInstance,
        ability: Ability,
        event: Event,
    ) -> StackItem:
        """
        Place a triggered ability on the stack.
        """
        return self._push(
            StackItem(
                kind=StackItemType.TRIGGERED_ABILITY,
                label=f"{source.id}:{ability.trigger}",
                source=source,
                ability=ability,
                controller=self._controller_for(source, event),
                event=event,
            )
        )

    # ------------------------------------------------------------------
    # Stack resolution
    # ------------------------------------------------------------------

    def _resolve_top(self) -> None:
        """
        Resolve the topmost stack item completely.
        """
        item = self._state.stack.pop()
        item.mark_resolving()

        if item.label == SETTLE_ROLL:
            self._settle_roll(item)
            item.mark_resolved()

        elif item.ability is not None:
            if not self._resolve_ability(item, item.ability):
                return

        elif item.label in self._procedures:
            # An engine procedure belongs to a player just as an ability does:
            # the attack being resolved is somebody's attack, and the dice it
            # rolls are that player's dice.
            self._context._set_actor(item.controller)

            try:
                self._procedures.get(item.label)(item, self._context)
            finally:
                self._context._set_actor(None)

            item.mark_resolved()
        else:
            item.fizzle()

        self._finish(item)

    def _finish(self, item: StackItem) -> None:
        """
        Announce that a stack object is done with.
        """
        self._context.emit(
            EventType.STACK_RESOLVE,
            source=item.source,
            controller=item.controller,
            stack_id=item.stack_id,
            status=str(item.status),
        )

    def _resolve_ability(
        self,
        item: StackItem,
        ability: Ability,
        *,
        context: AbilityContext | None = None,
        ops: list[EffectOp] | None = None,
        index: int = 0,
    ) -> bool:
        """
        Run one ability, or as much of it as can run right now.

        Returns False when the ability stopped to ask a player something. The
        stack object is then held by the pending decision rather than the
        stack, and resumes from the exact operation it stopped on.
        """
        if context is None:
            context = AbilityContext(
                source=item.source,
                ability=ability,
                controller=item.controller,
                owner=getattr(item.source, "owner", None),
                event=item.event,
            )

        self._context._set_actor(context.controller)
        self._context._set_source(context.source)

        try:
            if ops is None:
                self._target_resolver.resolve_all(
                    ability.targets, self._state, context, self._rng
                )

                ops = self._interpreter.build(ability.effects)

            steps = 0

            while index < len(ops):
                steps += 1

                if steps > self._interpreter.max_ops:
                    raise InterpreterError(
                        f"ability ran more than {self._interpreter.max_ops} steps"
                    )

                op = ops[index]

                if self._interpreter.is_control(op):
                    # A branch opens now, not when the queue was built: the
                    # effects before it have run, and it may be asking about
                    # what they did.
                    expansion, stopped = self._interpreter.expand(
                        op, self._state, context, self._rng
                    )

                    if stopped:
                        ops[index:] = expansion
                    else:
                        ops[index : index + 1] = expansion

                    continue

                self._executor.execute(op, self._context, context)
                index += 1

        except DecisionRequired as request:
            self._suspend(item, ability, context, ops, index, request)

            return False

        except RollRequired as request:
            self._open_roll(
                request, continuation=(item, ability, context, ops, index)
            )

            return False

        finally:
            self._context._set_actor(None)
            self._context._set_source(None)

        item.mark_resolved()

        return True

    def _suspend(
        self,
        item: StackItem,
        ability: Ability,
        context: AbilityContext,
        ops: list[EffectOp] | None,
        index: int,
        request: DecisionRequired,
    ) -> None:
        """
        Park a half-resolved ability until a player answers.
        """
        player = request.player

        if player is None or not 0 <= player < len(self._state.players):
            player = self._state.turn.active_player

        self._state.pending_decision = PendingDecision(
            decision_id=self._state.ids.allocate("decision"),
            player=player,
            kind=request.kind,
            options=list(request.options),
            minimum=request.minimum,
            maximum=request.maximum,
            bind=request.bind,
            prompt=request.prompt,
            continuation=(item, ability, context, ops, index),
        )

    def _request_roll(self, sides: int, attack: bool) -> None:
        """
        Open a roll on behalf of an engine procedure.
        """
        self._open_roll(RollRequired(sides, attack=attack))

    def _open_roll(
        self,
        request: RollRequired,
        *,
        continuation: Any = None,
    ) -> PendingRoll:
        """
        Roll the die and give the table its chance to answer.

        The roll itself happens now — it is the answer that waits, not the die
        — and everything that changes a roll without being asked has already
        had its say. What is left is the window: an object on the stack that
        settles the roll once nobody wants to respond any further.
        """
        from fsme.effects.builtin.dice import natural_roll

        state = self._state
        roller = self._context.actor

        self._context.emit(
            EventType.BEFORE_ROLL, controller=roller, sides=request.sides
        )

        value = natural_roll(self._context, request.sides, attack=request.attack)

        state.pending_roll = PendingRoll(
            roll_id=state.ids.allocate("roll"),
            sides=request.sides,
            natural=value,
            value=value,
            roller=roller,
            attack=request.attack,
            continuation=continuation,
        )

        self._push(
            StackItem(
                kind=StackItemType.DICE,
                label=SETTLE_ROLL,
                controller=roller,
            )
        )

        return state.pending_roll

    def _settle_roll(self, item: StackItem) -> None:
        """
        Close a roll nobody wants to answer any further.
        """
        waiting = self._state.pending_roll

        if waiting is None:
            return

        self._state.pending_roll = None

        self._context.emit(
            EventType.AFTER_ROLL,
            controller=waiting.roller,
            sides=waiting.sides,
            value=waiting.value,
            natural=waiting.natural,
            attack=waiting.attack,
        )

        if waiting.continuation is None:
            # A combat round asks for the roll and pushes its own next step, so
            # there is nothing here to wake up.
            self._state.combat.settled_roll = waiting.value

            return

        parked, ability, context, ops, index = waiting.continuation

        self._context._set_settled_roll(waiting.value)

        if self._resolve_ability(
            parked, ability, context=context, ops=ops, index=index
        ):
            self._finish(parked)

    def _resume(self, decision: PendingDecision) -> None:
        """
        Carry on resolving now that a player has answered.

        The binding goes into the ability's own context, so the target that
        asked the question finds the answer waiting when it is resolved again.
        """
        item, ability, context, ops, index = decision.continuation

        context.bind(decision.bind, list(decision.chosen or ()))

        self._state.pending_decision = None

        if self._resolve_ability(
            item, ability, context=context, ops=ops, index=index
        ):
            self._finish(item)

    # ------------------------------------------------------------------
    # State-Based Actions
    # ------------------------------------------------------------------

    def _pending_state_based_actions(self) -> bool:
        """
        Return True if any State-Based Action would fire right now.
        """
        state = self._state

        if any(player.alive and player.hp <= 0 for player in state.players):
            return True

        if any(
            player.hp > player.max_hp for player in state.players
        ):
            return True

        if any(
            getattr(monster, "alive", False) and (monster.hp or 0) <= 0
            for monster in state.active_monsters.cards
        ):
            return True

        if not state.game_over and any(
            player.soul_count >= state.souls_to_win for player in state.players
        ):
            return True

        return False

    def _state_based_actions(self) -> bool:
        """
        Apply every State-Based Action once.

        Returns True when something changed, which tells the loop to run
        another pass: a death may award a soul, and that soul may win the game.
        """
        from fsme.rules import kill_player, refill_monsters, refresh_derived

        changed = refresh_derived(self._state)

        for player in self._state.players:
            if not player.alive or player.hp > 0:
                continue

            # Death is offered for replacement before it is applied: a card
            # that says "prevent death" is answering the death, not reacting
            # to it. A prevented death leaves the player alive at no hit
            # points, and is not asked again until they take damage.
            if player.died_this_turn or self._propose(
                Event(
                    type=EventType.BEFORE_DEATH,
                    controller=player.player_id,
                    targets=[player],
                )
            ).cancelled:
                # COMPREHENSIVE_RULES.md §10: a prevented death gives back the
                # health the lethal blow found, and a player dies only once a
                # turn — the second nothing is not a second death.
                player.hp = max(1, min(player.max_hp, player.hp_before_lethal))
                changed = True

                continue

            kill_player(self._context, player)
            changed = True

        for monster in list(self._state.active_monsters.cards):
            if not getattr(monster, "alive", False):
                continue

            if (monster.hp or 0) > 0:
                continue

            self._kill_monster(monster)
            changed = True

        before_refill = len(self._state.active_monsters)


        refill_monsters(self._context)

        if len(self._state.active_monsters) != before_refill:
            changed = True

        if not self._state.game_over:
            for player in self._state.players:
                if player.soul_count >= self._state.souls_to_win:
                    self._state.finish(player.player_id)
                    changed = True

                    self._context.emit(
                        EventType.WINNER_DECLARED,
                        controller=player.player_id,
                        targets=[player],
                    )
                    self._context.emit(EventType.GAME_END)
                    break

        return changed

    def _kill_monster(self, monster: CardInstance) -> None:
        """
        Remove a dead monster and pay out what its card prints.

        The killer is whoever was attacking it. A monster killed by an effect
        outside combat has no killer, and its printed reward goes unclaimed —
        the same as a card that leaves play without being defeated.
        """
        state = self._state

        killer = (
            state.combat.attacker
            if state.combat.active and state.combat.monster is monster
            else monster.last_damaged_by
        )

        monster.alive = False
        from fsme.rules.slots import remove as leave_slot

        leave_slot(state, monster)
        state.monster_discard.add_top(monster)

        if state.combat.active and state.combat.monster is monster:
            from fsme.rules import end_combat

            # An attack ends the moment either fighter dies.
            end_combat(self._context)

        self._context.emit(
            EventType.MONSTER_KILLED,
            source=monster,
            controller=killer,
            targets=[monster],
            souls=monster.definition.souls,
        )

        if killer is None or not 0 <= killer < len(state.players):
            return

        self._pay_rewards(monster, state.player(killer))

    def _pay_rewards(self, monster: CardInstance, player: PlayerState) -> None:
        """
        Hand a defeated monster's printed rewards to the player who beat it.

        What is printed is offered for replacement first, because cards change
        it: "when this dies on an attack roll of 6, double its rewards" is a
        card editing a payment the rules are about to make. So the numbers are
        read back off the proposal rather than off the card.
        """
        definition = monster.definition
        rewards = definition.rewards

        offer = self._propose(
            Event(
                type=EventType.BEFORE_REWARDS,
                source=monster,
                controller=player.player_id,
                targets=[player],
                payload={
                    "souls": int(definition.souls),
                    "cents": int(rewards.get("cents", 0)),
                    "loot": int(rewards.get("loot", 0)),
                    "treasure": int(rewards.get("treasure", 0)),
                },
            )
        )

        if offer.cancelled:
            return

        paid = {
            name: max(0, int(offer.get(name, 0)))
            for name in ("souls", "cents", "loot", "treasure")
        }

        if paid["souls"] > 0:
            self._context.apply("gain_soul", [player], count=paid["souls"])

        if paid["cents"] > 0:
            self._context.apply("gain_coins", [player], amount=paid["cents"])

        if paid["loot"] > 0:
            self._context.apply("draw_loot", [player], count=paid["loot"])

        if paid["treasure"] > 0:
            self._context.apply("gain_treasure", [player], count=paid["treasure"])
