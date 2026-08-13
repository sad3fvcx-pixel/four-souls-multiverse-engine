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
from fsme.stack import StackItem, StackItemType
from fsme.state import GameState, PendingDecision, PlayerState

from .ability_context import AbilityContext
from .condition_evaluator import ConditionEvaluator
from .effect_executor import EffectExecutor
from .errors import (
    AbilityResolutionError,
    DecisionRequired,
    InterpreterError,
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
        )

        self._interactive_priority = interactive_priority
        self._max_iterations = max_iterations

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
        finally:
            self._replacement_depth -= 1

    def _replacements_for(self, event: Event) -> list[tuple[CardInstance, Ability]]:
        """
        Find the replacement abilities watching for an event.
        """
        matches: list[tuple[CardInstance, Ability]] = []

        for card in self._candidates(event):
            for ability in card.definition.abilities_for(str(event.type)):
                if not ability.replacement:
                    continue

                if ability_scope(ability) == "self" and event.source is not card:
                    continue

                probe = AbilityContext(
                    source=card,
                    ability=ability,
                    controller=self._controller_for(card, event),
                    owner=card.owner,
                    event=event,
                )

                if self._conditions.evaluate_all(
                    ability.conditions, self._state, probe
                ):
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

        self._context._set_event(event)
        self._context._set_source(card)

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
            self._context._set_event(None)
            self._context._set_source(None)

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

            event.mark_resolved()

        self._history.append(event)

    def _triggered_by(self, event: Event) -> list[tuple[CardInstance, Ability]]:
        """
        Find every ability that reacts to an event and may legally do so.

        Conditions are checked here, before anything is placed on the stack,
        because a condition that fails must leave no trace of the ability at
        all.
        """
        matches: list[tuple[CardInstance, Ability]] = []

        for card in self._candidates(event):
            for ability in card.definition.abilities_for(str(event.type)):
                if ability.replacement:
                    # A replacement already had its say before the event was
                    # queued. It is not also a trigger, or preventing damage
                    # would prevent it and then react to it.
                    continue

                if ability_scope(ability) == "self" and event.source is not card:
                    continue

                probe = AbilityContext(
                    source=card,
                    ability=ability,
                    controller=self._controller_for(card, event),
                    owner=card.owner,
                    event=event,
                )

                if self._conditions.evaluate_all(
                    ability.conditions, self._state, probe
                ):
                    matches.append((card, ability))

        return matches

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
        """
        seen: set[int] = set()

        source = event.source

        if isinstance(source, CardInstance):
            seen.add(id(source))
            yield source

        for card in self._ability_sources():
            if id(card) in seen:
                continue

            seen.add(id(card))
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

        if item.ability is not None:
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
        from fsme.rules import refresh_derived

        changed = refresh_derived(self._state)

        for player in self._state.players:
            if player.alive and player.hp <= 0:
                player.kill()
                changed = True

                self._context.emit(
                    EventType.PLAYER_DIED,
                    controller=player.player_id,
                    targets=[player],
                )

        for monster in list(self._state.active_monsters.cards):
            if not getattr(monster, "alive", False):
                continue

            if (monster.hp or 0) > 0:
                continue

            self._kill_monster(monster)
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
        state.active_monsters.cards.remove(monster)
        state.monster_discard.add_top(monster)

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
        """
        definition = monster.definition

        if definition.souls > 0:
            self._context.apply("gain_soul", [player], count=definition.souls)

        rewards = definition.rewards

        cents = int(rewards.get("cents", 0))

        if cents > 0:
            self._context.apply("gain_coins", [player], amount=cents)

        loot = int(rewards.get("loot", 0))

        if loot > 0:
            self._context.apply("draw_loot", [player], count=loot)

        treasure = int(rewards.get("treasure", 0))

        if treasure > 0:
            self._context.apply("gain_treasure", [player], count=treasure)
