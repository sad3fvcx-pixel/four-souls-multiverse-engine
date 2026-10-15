# src/fsme/lab/simulation/agent.py

"""
A player that is not clever, only thorough.

It picks uniformly among the moves the engine says it may make, and answers a
question with as many options as the question asks for. That is the whole of
it, and the modesty is deliberate: a simulation run by a strong player measures
the player, and a simulation run by this one measures the game.

It is seeded, so a thousand games are a thousand *particular* games. The same
seed and the same content deal and play out identically, which is what makes a
surprising result something you can go back and look at.
"""

from __future__ import annotations

import random
from typing import Any

from fsme.api.moves import legal_moves
from fsme.commands import Command, CommandType
from fsme.game import Game


class ScriptedAgent:
    """
    Chooses at random among what is legal.
    """

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    def choose(
        self, game: Game, seats: tuple[int, ...] = ()
    ) -> tuple[Command, str] | None:
        """
        Decide the next thing to do, or say there is nothing.

        A question comes first: while one is open it is the only move there is,
        which is the engine's rule and not this agent's preference.

        ``seats`` narrows the moves to the ones belonging to the seats this
        agent is playing, for the same reason the bot does it: a table where
        everybody may play everybody's cards is not a table anyone can be
        compared at.
        """
        decision = game.runtime.awaiting_decision

        if decision is not None:
            return self._answer(decision)

        moves = legal_moves(game)

        if seats:
            moves = [
                move for move in moves if int(move["player"]) in seats
            ] or moves

        if not moves:
            return None

        move = self._rng.choice(moves)

        return (
            Command(
                type=CommandType(move["type"]),
                player=int(move["player"]),
                payload=dict(move["payload"]),
            ),
            str(move["label"]),
        )

    def _answer(self, decision: Any) -> tuple[Command, str]:
        """
        Answer a question with a legal number of its options.
        """
        count = len(decision.options)

        lowest = max(0, min(decision.minimum, count))
        highest = max(lowest, min(decision.maximum, count))

        picks = (
            self._rng.sample(range(count), self._rng.randint(lowest, highest))
            if count
            else []
        )

        chosen = ", ".join(
            str(getattr(decision.options[index], "name", decision.options[index]))
            for index in picks
        )

        return (
            Command(
                type=CommandType.CHOOSE_TARGET,
                player=decision.player,
                payload={"choices": picks},
            ),
            f"{decision.prompt or decision.kind} → {chosen or 'nothing'}",
        )
