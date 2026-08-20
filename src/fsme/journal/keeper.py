# src/fsme/journal/keeper.py

"""
Keeping a journal while a game is played.

The keeper sits between whoever is playing and the game, and writes down each
accepted command with the position it was made from and the events it caused.
It decides nothing and changes nothing: a game played through a keeper is the
same game, command for command and die for die.

What it costs is worth stating plainly. Reading the position is a handful of
attribute lookups. Recording the alternatives is not — it asks the engine about
every conceivable move before every real one — so that is off unless asked for,
and a simulation running ten thousand games can keep a full journal of each
without paying for the part nobody will read.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from fsme.commands import Command, CommandResult
from fsme.events import Event
from fsme.game import Game
from fsme.replay import state_digest

from .entry import Entry, Happening, Journal, Position

Offers = Callable[[Game], Sequence[str]]
"""
Where the alternatives come from.

Passed in rather than imported: what a player may do is a rules question, and
the module that answers it sits above this one. The keeper only writes down
whatever answer it is handed.
"""


class JournalKeeper:
    """
    A game, and the journal being kept of it.
    """

    def __init__(
        self,
        game: Game,
        *,
        offers: Offers | None = None,
        content_version: str | None = None,
    ) -> None:
        from fsme import __version__
        from fsme.scenario import digest_of

        self._game = game
        self._offers = offers

        # Read off the game rather than asked for. A keeper is built in three
        # places and a game already knows how it was set up; making each caller
        # remember to hand the same two facts over is how they come to differ.
        #
        # A scenario that asks for nothing is not recorded, because it is not
        # an experiment: an empty scenario deals the game FSME deals anyway, so
        # a journal that noted one would say a game was configured when it was
        # not, and two records of the same game would differ.
        scenario = game.scenario

        if scenario is not None and scenario.is_empty:
            scenario = None

        self._journal = Journal(
            seed=game.state.seed,
            players=tuple(player.name for player in game.state.players),
            characters=tuple(
                str(getattr(player.character, "name", "")) for player in game.state.players
            ),
            engine_version=__version__,
            content_version=(
                game.content_version if content_version is None else content_version
            ),
            scenario=None if scenario is None else scenario.to_dict(),
            scenario_digest=digest_of(scenario),
            interactive_priority=game.interactive_priority,
        )

    @property
    def game(self) -> Game:
        return self._game

    @property
    def journal(self) -> Journal:
        return self._journal

    def submit(
        self,
        command: Command,
        *,
        label: str = "",
        decision: Mapping[str, Any] | None = None,
    ) -> CommandResult:
        """
        Play one command, and write down what it was and what came of it.

        ``label`` is the move in the words the client offered it in. It is a
        separate argument rather than something smuggled through the payload:
        the payload is what the engine reads, and a journal must not be able to
        change the game it is recording.

        ``decision`` is the working of whatever chose the move, when it showed
        any. It is written down as handed over: a journal that reshaped a bot's
        reasoning would stop being evidence about the bot.

        A rejected command is not written down. It changed nothing, so it is
        part of the session and not part of the game — the same reason a replay
        does not keep one.
        """
        before = self._position()
        offered = tuple(self._offers(self._game)) if self._offers else ()

        result = self._game.submit(command)

        if not result.accepted:
            return result

        self._journal.add(
            Entry(
                index=len(self._journal),
                command=str(command.type),
                player=command.player,
                payload=dict(command.payload),
                label=label,
                before=before,
                offered=offered,
                events=tuple(_happening(event) for event in result.events),
                decision=dict(decision) if decision is not None else None,
                digest=state_digest(self._game.state),
            )
        )

        self._note_the_ending()

        return result

    def _note_the_ending(self) -> None:
        """
        Record how the game finished, once it has.
        """
        state = self._game.state

        if not state.game_over or self._journal.outcome:
            return

        winner = state.winner

        self._journal.outcome = {
            "winner": winner,
            "winner_name": (
                state.players[winner].name
                if winner is not None and 0 <= winner < len(state.players)
                else None
            ),
            "turns": state.turn.turn_number,
            "commands": len(self._journal),
            "souls": [player.soul_count for player in state.players],
        }

    def _position(self) -> Position:
        """
        The few numbers a reader wants about where the game stands.
        """
        state = self._game.state
        waiting = self._game.runtime.awaiting_decision

        kind: str
        who: int | None

        if waiting is not None:
            kind, who = "decision", waiting.player
        elif self._game.runtime.awaiting_priority:
            kind, who = "priority", state.priority.holder
        else:
            kind, who = "action", state.turn.active_player

        return Position(
            turn=state.turn.turn_number,
            phase=str(state.turn.phase),
            active_player=state.turn.active_player,
            waiting_kind=kind,
            waiting_player=who,
            stack=tuple(_name_of(item) for item in state.stack),
            players=tuple(
                {
                    "name": player.name,
                    "hp": player.hp,
                    "max_hp": player.max_hp,
                    "coins": player.pennies,
                    "souls": player.soul_count,
                    "alive": bool(player.alive),
                }
                for player in state.players
            ),
        )


def _name_of(item: Any) -> str:
    """
    Name one thing on the queue: what it is, and what put it there.
    """
    source = getattr(item.source, "name", None)

    return f"{item.label}" + (f" ({source})" if source else "")


def _happening(event: Event) -> Happening:
    """
    Flatten one event into the words it would be read in.
    """
    return Happening(
        type=str(event.type),
        source=getattr(event.source, "name", None),
        source_id=getattr(getattr(event.source, "definition", None), "id", None),
        controller=event.controller,
        targets=tuple(
            str(getattr(target, "name", getattr(target, "player_id", target)))
            for target in event.targets
        ),
        payload={
            key: _plain(value)
            for key, value in event.payload.items()
            if key != "stack_id"
        },
    )


def _plain(value: Any) -> Any:
    """
    Reduce whatever an event is carrying to something JSON can hold.
    """
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    name = getattr(value, "name", None)

    if name is not None:
        return str(name)

    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]

    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}

    return str(value)
