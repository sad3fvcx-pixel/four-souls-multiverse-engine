"""
Combat: rounds on the stack, damage, death and rewards.
"""

from __future__ import annotations

from conftest import (
    make_definition,
    make_game,
    make_instance,
    monster_definition,
    treasure_definition,
)

from fsme.cards import CardInstance, CardType, Static
from fsme.commands import Command, CommandType
from fsme.events import EventType
from fsme.rng.rng import RNG
from fsme.rules.constants import DICE_SIDES
from fsme.rules.slots import place
from fsme.rules.statics import ATTACK as ATTACK_STAT
from fsme.rules.statics import DIFFICULTY, monster_value
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


def drain(runtime, state, limit=12) -> None:
    """
    Let every open window close, so the queue is empty again.

    A purchase and an attack may only be declared into an empty queue, and an
    interactive game opens a window for the loot step before anybody acts.
    """
    for _ in range(limit):
        if not runtime.awaiting_priority:
            return

        runtime.submit(
            Command(type=CommandType.PASS_PRIORITY, player=state.priority.holder or 0)
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

    tough = CardInstance(
        definition=monster_definition("test.tough", health=1, roll=6),
        instance_id="monster:tough",
        controller=None,
        owner=None,
    )

    # Into the first slot, before the game opens, so that the attack below is
    # aimed at it and not at whatever the deck turns over beside it.
    place(state, tough)

    runtime.submit(Command(type=CommandType.START_GAME, player=0))
    runtime.submit(Command(type=CommandType.END_PHASE, player=0))

    attack(runtime)

    assert tough.alive is False
    assert tough in state.monster_discard.cards
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


def test_a_monster_shuffled_back_returns_in_one_piece() -> None:
    """
    A beaten monster that finds its way back into the deck comes back whole.

    What the fight did to it belonged to the monster on the table; the card in
    the deck is only a card. Bringing it up wounded would leave a corpse in a
    slot that nothing can kill and nothing can clear.

    The monster deck starts empty here, which is how the monster gets back into
    it: the deck has run out, so §9 rebuilds it by shuffling the discard, and
    the only card in that discard is the monster that has just died.
    """
    runtime, state = armed_game([6, 6], monsters=1, monster_deck=0)
    reach_action_phase(runtime, state)

    monster = state.active_monsters.cards[0]

    attack(runtime)

    assert monster in state.active_monsters.cards, "it was shuffled back and turned over"
    assert monster.alive is True
    assert monster.hp == monster.definition.health


def stock_monster_deck(state, *cards) -> None:
    """
    Put cards on the monster deck, last one on top.
    """
    for card in cards:
        state.monster_deck.add_top(card)


def test_the_monster_deck_can_be_attacked() -> None:
    """
    COMPREHENSIVE_RULES.md §7: the revealed monster joins the area and is fought.
    """
    runtime, state = armed_game([6, 6], monsters=1)
    reach_action_phase(runtime, state)

    revealed = CardInstance(
        definition=monster_definition("test.revealed", health=2),
        instance_id="monster:revealed",
        controller=None,
        owner=None,
    )
    stock_monster_deck(state, revealed)

    assert runtime.submit(
        Command(type=CommandType.ATTACK, player=0, payload={"source": "deck"})
    ).accepted

    assert revealed.alive is False, "it was the revealed monster that was fought"
    assert state.player(0).soul_count == 1
    assert state.active_monsters.cards[0].alive is True, "the slot was not attacked"


def test_turning_over_something_that_is_not_a_monster_ends_the_attack() -> None:
    """
    §7: anything that is not a monster is played, and the attack is over.
    """
    runtime, state = armed_game([6, 6], monsters=1)
    reach_action_phase(runtime, state)

    event = CardInstance(
        definition=make_definition(
            "test.happening",
            name="Test Event",
            card_type=CardType.EVENT,
        ),
        instance_id="monster:happening",
        controller=None,
        owner=None,
    )
    stock_monster_deck(state, event)

    assert runtime.submit(
        Command(type=CommandType.ATTACK, player=0, payload={"source": "deck"})
    ).accepted

    assert state.combat.active is False
    assert event in state.monster_discard.cards
    assert state.player(0).can_attack() is False, "the attack was spent all the same"


def test_attacking_an_empty_monster_deck_is_refused() -> None:
    runtime, state = armed_game([6], monsters=1, monster_deck=0)
    reach_action_phase(runtime, state)

    result = runtime.submit(
        Command(type=CommandType.ATTACK, player=0, payload={"source": "deck"})
    )

    assert result.rejected
    assert "empty" in result.reason


def test_an_attack_on_a_monster_that_leaves_fizzles_and_is_not_spent() -> None:
    """
    COMPREHENSIVE_RULES.md §12: the monster is no longer active, so the attack
    does not begin — and the attack is not spent.
    """
    runtime, state = armed_game([6, 6], monsters=1, interactive_priority=True)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))
    drain(runtime, state)
    runtime.submit(Command(type=CommandType.END_PHASE, player=0))
    drain(runtime, state)

    monster = state.active_monsters.cards[0]

    assert attack(runtime).accepted
    assert state.player(0).attacks_left == 0, "declaring spends the attack"

    # Something answers the declaration by removing the monster from its slot.
    runtime.context.apply("discard_monsters", [monster])

    for _ in range(4):
        if not runtime.awaiting_priority:
            break

        runtime.submit(
            Command(type=CommandType.PASS_PRIORITY, player=state.priority.holder or 0)
        )

    assert state.combat.active is False
    assert state.player(0).attacks_left == 1, "an attack that fizzles is not spent"
    assert EventType.ATTACK_FIZZLED in [event.type for event in runtime.history]


def test_an_attack_that_resolves_begins_the_fight() -> None:
    runtime, state = armed_game([6, 6], monsters=1, interactive_priority=True)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))
    drain(runtime, state)
    runtime.submit(Command(type=CommandType.END_PHASE, player=0))
    drain(runtime, state)

    monster = state.active_monsters.cards[0]

    assert attack(runtime).accepted

    for _ in range(4):
        if not runtime.awaiting_priority:
            break

        runtime.submit(
            Command(type=CommandType.PASS_PRIORITY, player=state.priority.holder or 0)
        )

    assert state.combat.active is True
    assert state.combat.monster is monster


# ----------------------------------------------------------------------
# What a monster can ask for
# ----------------------------------------------------------------------


def test_a_difficulty_bonus_cannot_ask_for_more_than_a_die_can_roll() -> None:
    """
    COMPREHENSIVE_RULES.md §5: "A roll result and a monster's difficulty are
    never above 6 nor below 1."

    Without the bound, +1 on a monster printed at 6 asks for a 7. One die
    cannot roll a 7, so the monster cannot be hit by attacking at all — and
    that is not a hard monster, it is a monster outside the rules. Measured on
    real content before the bound: three attack rolls needing 7, in two games
    of two hundred, against The Beast.
    """
    runtime, state = make_game(monsters=0, monster_deck=0, monster_slots=1)

    beast = CardInstance(
        definition=monster_definition("test.beast", health=6, roll=DICE_SIDES),
        instance_id="monster:beast",
        controller=None,
        owner=None,
    )
    place(state, beast)

    assert monster_value(state, DIFFICULTY, beast, DICE_SIDES) == DICE_SIDES

    runtime.context.apply("add_modifier", [beast], stat=DIFFICULTY, amount=1)

    assert monster_value(state, DIFFICULTY, beast, DICE_SIDES) == DICE_SIDES

    runtime.context.apply("add_modifier", [beast], stat=DIFFICULTY, amount=5)

    assert monster_value(state, DIFFICULTY, beast, DICE_SIDES) == DICE_SIDES


def test_a_difficulty_penalty_cannot_take_it_below_one() -> None:
    """
    The other half of §5. A difficulty of 0 is a monster every roll hits, which
    is what a 1 already means; below that the number stops meaning anything.
    """
    runtime, state = make_game(monsters=0, monster_deck=0, monster_slots=1)

    weak = CardInstance(
        definition=monster_definition("test.weak", health=1, roll=2),
        instance_id="monster:weak",
        controller=None,
        owner=None,
    )
    place(state, weak)

    runtime.context.apply("add_modifier", [weak], stat=DIFFICULTY, amount=-9)

    assert monster_value(state, DIFFICULTY, weak, 2) == 1


def test_the_bound_is_on_the_difficulty_and_not_on_every_monster_number() -> None:
    """
    A monster's attack is not a roll and is not bounded by the die.

    Worth asserting: the bound lives where the stat is worked out, so a bound
    written one line too wide would quietly cap how hard a monster hits.
    """
    runtime, state = make_game(monsters=0, monster_deck=0, monster_slots=1)

    brute = CardInstance(
        definition=monster_definition("test.brute", health=4, attack=6),
        instance_id="monster:brute",
        controller=None,
        owner=None,
    )
    place(state, brute)

    runtime.context.apply("add_modifier", [brute], stat=ATTACK_STAT, amount=3)

    assert monster_value(state, ATTACK_STAT, brute, 6) == 9


def test_an_unhittable_monster_is_hittable_again() -> None:
    """
    The same thing from the table's side: the fight happens and the roll that
    matches the printed difficulty is a hit, bonus or no bonus.
    """
    runtime, state = armed_game([6, 6], monsters=0, monster_deck=0, monster_slots=1)

    beast = CardInstance(
        definition=monster_definition("test.beast", health=1, roll=DICE_SIDES),
        instance_id="monster:beast",
        controller=None,
        owner=None,
    )
    place(state, beast)

    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    runtime.context.apply("add_modifier", [beast], stat=DIFFICULTY, amount=1)
    runtime.run()

    runtime.submit(Command(type=CommandType.END_PHASE, player=0))

    attack(runtime)

    rolls = [
        event
        for event in runtime.history
        if event.type is EventType.AFTER_ATTACK_ROLL
    ]

    assert rolls, "the attack happened"
    assert all(event.payload["required"] == DICE_SIDES for event in rolls)
    assert all(event.payload["hit"] for event in rolls), "a six is a hit against a six"
    assert EventType.MONSTER_KILLED in [event.type for event in runtime.history]


def test_a_static_that_reaches_monsters_is_bounded_too() -> None:
    """
    "Monsters have +1 DC" printed on a card in play, rather than a modifier
    sitting on the monster: the same number, arrived at another way.
    """
    runtime, state = make_game(monsters=0, monster_deck=0, monster_slots=1)

    beast = CardInstance(
        definition=monster_definition("test.beast", health=6, roll=DICE_SIDES),
        instance_id="monster:beast",
        controller=None,
        owner=None,
    )
    place(state, beast)

    harder = make_instance(
        make_definition(
            "test.harder",
            name="Everything Is Worse",
            card_type=CardType.TREASURE,
            statics=(Static(DIFFICULTY, 1, scope="all_monsters"),),
        ),
        controller=0,
        owner=0,
        instance_id="instance:harder",
    )
    state.player(0).treasures.add_top(harder)

    assert monster_value(state, DIFFICULTY, beast, DICE_SIDES) == DICE_SIDES
