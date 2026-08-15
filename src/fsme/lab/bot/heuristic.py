# src/fsme/lab/bot/heuristic.py

"""
A bot that thinks one move ahead, and shows its working.

It is not strong and is not trying to be. It knows four things — that souls
win, that dying is expensive, that a die has six faces, and that ten cents buys
an item — and it applies them to the moves the engine says it may make. Every
number it uses comes from the position or from the rules; nothing is estimated
from games it has not played.

Its purpose is to be *legible*. A bot whose reasoning can be read is one whose
mistakes can be found, and finding them is the whole point of writing the
reasoning down. Where it guesses, the guess is a named preference with a weight
beside it, so that a reader disagreeing with a choice can see exactly which
number to argue with.

What it does not do is worth stating too. It does not look ahead past the move
in front of it, it does not model what other players will do, and it does not
know what most cards say — a loot card it has no opinion about is worth a small
constant, because playing something is usually better than passing and the
engine will not let it play anything illegal.
"""

from __future__ import annotations

import random
from typing import Any

from fsme.api.moves import legal_moves
from fsme.commands import Command, CommandType
from fsme.game import Game
from fsme.rules.constants import DICE_SIDES, TREASURE_COST
from fsme.rules.statics import DIFFICULTY, monster_value

from .evaluation import Decision, Evaluation, Reason

NAME = "heuristic-1"

SOUL_IS_WORTH = 12.0
"""
Points for a soul, against everything else being measured in the same currency.

Four of them win the game, so nothing else the bot can see in one move should
outweigh one. That is the whole justification, and it is why this number is
large rather than tuned.
"""

DYING_COSTS = 9.0
"""
Points for dying: a loot card, a cent, an item, a turn ended, everything
deactivated. Slightly less than a soul, because a death is recoverable and a
soul is permanent.
"""

DAMAGE_COSTS = 1.5
"""Points per hit point, when the hit point is not the last one."""

COIN_IS_WORTH = 0.6
"""
Points for a cent — a tenth of an item, plus a little for flexibility.
"""

ITEM_IS_WORTH = 5.0
"""Points for an item, which is what ten cents is for."""

LOOT_IS_WORTH = 1.2
"""
Points for a card in hand, and for playing one the bot has no opinion about.

Deliberately small and deliberately positive: doing something is usually better
than passing, and the engine has already refused anything illegal.
"""


class HeuristicBot:
    """
    Scores the legal moves and takes the best, keeping its working.
    """

    def __init__(self, seed: int = 0, *, name: str = NAME) -> None:
        self._rng = random.Random(seed)
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def choose(
        self, game: Game, seats: tuple[int, ...] = ()
    ) -> tuple[Command, str, Decision] | None:
        """
        Decide the next thing to do, and say why.

        ``seats`` are the seats this bot is playing. The engine offers every
        legal move at the table, including cards other players may respond
        with, and a bot that took those would be playing their game as well as
        its own — which would make any comparison between it and them
        meaningless. So it chooses from its own moves when it has any.
        """
        decision = game.runtime.awaiting_decision

        if decision is not None:
            return self._answer(game, decision)

        opinions = self.opinions(game, seats=seats)

        if not opinions:
            return None

        moves = [move for move, _ in opinions]
        weighed = [evaluation for _, evaluation in opinions]

        best = max(weighed, key=lambda evaluation: evaluation.score)

        # Ties go to chance rather than to whichever the engine listed first:
        # a bot that always breaks ties the same way plays a much narrower
        # range of games than it appears to.
        tied = [
            evaluation
            for evaluation in weighed
            if evaluation.score >= best.score - 1e-9
        ]

        chosen = self._rng.choice(tied)
        move = moves[weighed.index(chosen)]

        return (
            Command(
                type=CommandType(move["type"]),
                player=int(move["player"]),
                payload=dict(move["payload"]),
            ),
            str(move["label"]),
            Decision(
                by=self._name,
                chosen=chosen,
                considered=tuple(weighed),
                notes=(
                    ("nothing scored above doing nothing",)
                    if chosen.score <= 0
                    else ()
                ),
            ),
        )

    def opinions(
        self, game: Game, seats: tuple[int, ...] = ()
    ) -> tuple[tuple[dict[str, Any], Evaluation], ...]:
        """
        Weigh every move on offer, without taking any of them.

        The same arithmetic ``choose`` runs, exposed so that a move somebody
        else made can be held against it. That is the only way this bot's
        opinion is worth anything about a game it did not play: it says what it
        would have done, in the currency it says everything in.
        """
        moves = legal_moves(game)

        if seats:
            mine = [move for move in moves if int(move["player"]) in seats]

            # Falling back is not politeness: if this bot has nothing to do and
            # the game is waiting on it, somebody has to move or the run stops.
            moves = mine or moves

        return tuple((move, self._weigh(game, move)) for move in moves)

    def _weigh(self, game: Game, move: dict[str, Any]) -> Evaluation:
        """
        Score one move from what the position and the rules say about it.
        """
        kind = str(move["type"])
        label = str(move["label"])
        seat = int(move["player"])

        if kind == str(CommandType.ATTACK):
            return self._weigh_attack(game, move, label, seat)

        if kind == str(CommandType.BUY_TREASURE):
            return self._weigh_purchase(game, label, seat)

        if kind == str(CommandType.PLAY_LOOT):
            return Evaluation(
                label,
                LOOT_IS_WORTH,
                (Reason("a card played is a card working", 1, LOOT_IS_WORTH),),
            )

        if kind == str(CommandType.ACTIVATE_TREASURE):
            return Evaluation(
                label,
                LOOT_IS_WORTH,
                (Reason("an item used is an item working", 1, LOOT_IS_WORTH),),
            )

        if kind in (str(CommandType.END_TURN), str(CommandType.END_PHASE)):
            return Evaluation(label, 0.0, (Reason("nothing left worth doing", 0, 0.0),))

        return Evaluation(label, -0.1, (Reason("passing", 0, -0.1),))

    def _weigh_attack(
        self, game: Game, move: dict[str, Any], label: str, seat: int
    ) -> Evaluation:
        """
        Score an attack from the die, the monster and the attacker's health.

        The chance of hitting is exact: one six-sided die against a printed
        difficulty. What follows from a hit or a miss is one round's worth and
        no further — this bot does not fight the whole fight in its head.
        """
        state = game.state
        player = state.player(seat)

        monster = self._monster(game, move)

        if monster is None:
            return Evaluation(
                label,
                0.5,
                (Reason("an unknown monster, turned over blind", 0, 0.5),),
            )

        printed = getattr(getattr(monster, "definition", None), "roll", None)
        required = monster_value(state, DIFFICULTY, monster, int(printed or 4))

        hits = max(0.0, min(1.0, (DICE_SIDES - required + 1) / DICE_SIDES))

        souls = int(getattr(getattr(monster, "definition", None), "souls", 0) or 0)
        attack = int(getattr(getattr(monster, "definition", None), "attack", 1) or 1)
        health = int(getattr(monster, "hp", 0) or 0)

        reasons = [Reason("chance the die is enough", round(hits, 3), 0.0)]

        score = 0.0

        # One hit finishes it, so the souls are on the table this round.
        if health <= 1 and souls:
            worth = hits * souls * SOUL_IS_WORTH
            score += worth
            reasons.append(Reason("a hit would finish it", souls, worth))
        elif souls:
            worth = hits * souls * SOUL_IS_WORTH / max(1, health)
            score += worth
            reasons.append(Reason("souls, further off", souls, worth))

        misses = 1.0 - hits

        if attack >= player.hp:
            worth = -misses * DYING_COSTS
            score += worth
            reasons.append(Reason("a miss would kill you", player.hp, worth))
        else:
            worth = -misses * attack * DAMAGE_COSTS
            score += worth
            reasons.append(Reason("what a miss costs", attack, worth))

        return Evaluation(label, score, tuple(reasons))

    def _weigh_purchase(self, game: Game, label: str, seat: int) -> Evaluation:
        """
        Score a purchase: an item for ten cents, if the cents are spare.
        """
        player = game.state.player(seat)

        spent = -TREASURE_COST * COIN_IS_WORTH

        return Evaluation(
            label,
            ITEM_IS_WORTH + spent,
            (
                Reason("an item", 1, ITEM_IS_WORTH),
                Reason("what it costs", TREASURE_COST, spent),
                Reason("cents in hand", player.pennies, 0.0),
            ),
        )

    def _monster(self, game: Game, move: dict[str, Any]) -> Any | None:
        """
        The monster a declared attack is aimed at, when it is aimed at one.
        """
        payload = move["payload"]

        if payload.get("source") == "deck":
            return None

        index = int(payload.get("index", 0))
        monsters = game.state.active_monsters.cards

        return monsters[index] if 0 <= index < len(monsters) else None

    def _answer(self, game: Game, decision: Any) -> tuple[Command, str, Decision]:
        """
        Answer a question the engine asked.

        The bot has no opinion about most questions — which loot card to
        discard, which of three effects to take — and says so rather than
        inventing a preference it does not have. It answers with the fewest
        options the question allows, which is the least it can do without
        pretending to a judgement it has not made.
        """
        count = len(decision.options)

        lowest = max(0, min(decision.minimum, count))
        highest = max(lowest, min(decision.maximum, count))

        wanted = lowest if lowest else min(highest, 1 if count else 0)
        picks = self._rng.sample(range(count), wanted) if count else []

        chosen = ", ".join(
            str(getattr(decision.options[index], "name", decision.options[index]))
            for index in picks
        )

        label = f"{decision.prompt or decision.kind} → {chosen or 'nothing'}"

        return (
            Command(
                type=CommandType.CHOOSE_TARGET,
                player=decision.player,
                payload={"choices": picks},
            ),
            label,
            Decision(
                by=self._name,
                chosen=Evaluation(label, 0.0, ()),
                notes=("no opinion about this question; answered at random",),
            ),
        )
