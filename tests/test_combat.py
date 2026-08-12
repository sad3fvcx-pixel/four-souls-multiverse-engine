"""
Combat: rounds on the stack, damage, death and rewards.
"""

from __future__ import annotations

from conftest import (
    make_game,
    make_instance,
    monster_definition,
    treasure_definition,
)

from fsme.cards import CardInstance
from fsme.commands import Command, CommandType
from fsme.events import EventType
from fsme.rng.rng import RNG
from fsme.state import GamePhase


class FixedRNG(RNG):
    """
    An RNG that returns a scripted sequence of rolls.

    RNG.md section 11 allows tests to replace the generator so a scenario can
    be verified exactly instead of statistically. Once the script runs out
    every further roll is the lowest value, which in combat means a miss, so a
    scenario ends predictably instead of drifting.
    """

    def __init__(self, rolls: list[int]) -> None:
        super().__init__(0)
        self._rolls = list(rolls)

    def randint(self, a: int, b: int) -> int:
        if not self._rolls:
            return a

        return self._rolls.pop(0)


def armed_game(rolls: list[int], **kwargs):
    return make_game(rng=FixedRNG(rolls), **kwargs)


def reach_action_phase(runtime, state) -> None:
    runtime.submit(Command(type=CommandType.START_GAME, player=0))
    runtime.submit(Command(type=CommandType.END_PHASE, player=0))

    assert state.turn.phase is GamePhase.ACTION


def attack(runtime, player=0, index=0):
    return runtime.submit(
        Command(type=CommandType.ATTACK, player=player, payload={"index": index})
    )


def test_attack_is_refused_outside_the_action_phase() -> None:
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    result = attack(runtime)

    assert result.rejected
    assert "loot phase" in result.reason


def test_a_hit_damages_the_monster() -> None:
    runtime, state = armed_game([4])
    reach_action_phase(runtime, state)

    monster = state.active_monsters.cards[0]

    attack(runtime)

    assert monster.hp == 1

    types = [event.type for event in runtime.history]

    assert EventType.ATTACK_START in types
    assert EventType.AFTER_ATTACK_ROLL in types
    assert EventType.DAMAGE_DEALT in types


def test_a_miss_damages_the_attacker() -> None:
    runtime, state = armed_game([1, 1])
    reach_action_phase(runtime, state)

    monster = state.active_monsters.cards[0]

    attack(runtime)

    assert monster.hp == 2
    assert state.player(0).hp < 2


def test_combat_continues_until_the_monster_dies() -> None:
    """
    An attack is a sequence of rounds, not a single roll.
    """
    runtime, state = armed_game([6, 6])
    reach_action_phase(runtime, state)

    monster = state.active_monsters.cards[0]

    attack(runtime)

    assert monster.alive is False
    assert monster in state.monster_discard.cards
    assert state.combat.active is False
    assert EventType.ATTACK_END in [event.type for event in runtime.history]


def test_killing_a_monster_awards_its_printed_souls() -> None:
    runtime, state = armed_game([6, 6])
    reach_action_phase(runtime, state)

    attack(runtime)

    assert state.player(0).soul_count == 1
    assert EventType.SOUL_GAINED in [event.type for event in runtime.history]


def test_a_monster_killed_outside_combat_awards_nobody() -> None:
    """
    There is no killer to pay, so the printed reward goes unclaimed.
    """
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    monster = state.active_monsters.cards[0]
    runtime.context.apply("kill", [monster])
    runtime.run()

    assert monster.alive is False
    assert state.player(0).soul_count == 0


def test_combat_ends_when_the_attacker_dies() -> None:
    runtime, state = armed_game([1, 1, 1, 1, 1, 1])
    reach_action_phase(runtime, state)

    attack(runtime)

    assert state.player(0).alive is False
    assert state.combat.active is False
    assert EventType.PLAYER_DIED in [event.type for event in runtime.history]


def test_only_one_attack_per_turn() -> None:
    runtime, state = armed_game([4, 4, 4, 4])
    reach_action_phase(runtime, state)

    assert attack(runtime).accepted

    second = attack(runtime)

    assert second.rejected
    assert "no attacks remaining" in second.reason


def test_the_monster_roll_value_decides_a_hit() -> None:
    runtime, state = armed_game([5, 6], monsters=0)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    state.active_monsters.add_top(
        CardInstance(
            definition=monster_definition("test.tough", health=1, roll=6),
            instance_id="monster:tough",
            controller=None,
            owner=None,
        )
    )

    runtime.submit(Command(type=CommandType.END_PHASE, player=0))

    attack(runtime)

    monster = state.monster_discard.cards[-1]

    assert monster.alive is False
    assert state.player(0).hp == 1


def test_an_ability_may_resolve_between_combat_rounds() -> None:
    """
    Each round waits on the stack, so a reaction lands before the next roll.
    """
    runtime, state = armed_game([6, 6])
    reach_action_phase(runtime, state)

    reactor = make_instance(
        treasure_definition(
            "test.reactor",
            effects=({"gain_coins": 2},),
            trigger="after_attack_roll",
        ),
        controller=0,
        owner=0,
        instance_id="instance:reactor",
    )
    state.player(0).treasures.add_top(reactor)

    attack(runtime)

    assert state.player(0).pennies >= 2
