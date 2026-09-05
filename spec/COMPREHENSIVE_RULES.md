# Four Souls Multiverse Engine
## Comprehensive Rules, as the engine reads them
Version: 1.1.0

---

# 1. Where this comes from

This document records the rules the engine implements, transcribed from the
comprehensive rulebook supplied for the project (*The Binding of Isaac: Four
Souls — Всеобъемлющие правила*, compiled by Jon @jonzo11, Russian edition by
Два Кадра). `RULES_SPEC.md` says which sources are canonical and how the engine
treats them; this says what they actually state, in the places where the engine
had to know and previously did not.

§12 was supplied separately, after the rest: the rulebook transcribed here has
no room section, and rooms are *Requiem* content.

It is written down for one reason: the engine may not invent a rule. Anything
not stated here or in another spec is a gap, and a gap is documented in
`PROJECT_PLAN.md` §11.5 rather than guessed at.

---

# 2. Setup

- Shuffle the treasure, loot and monster decks.
- The bank holds 100¢.
- The shop shows 2 treasure cards; the monster area shows 2 monsters, each in
  its own slot. The face-up card in a slot is the active monster of that slot.
- Event and curse cards revealed during setup go under the monster deck.
- Bonus souls, if used, are laid out face up.
- Each player takes one character and its starting item. Characters begin
  deactivated; items begin charged.
- Each player is dealt 3 loot cards and 3¢.
- Play passes clockwise. Cain goes first if he is in the game.

---

# 3. Turn sequence

A turn has three phases. Within a step, play continues until the queue is empty
and every player has passed in turn without adding anything.

## 3.1 Start phase

1. Recharge all of your activated items and your character card.
2. "At the start of your turn" effects trigger; then you receive priority.
3. The effect *loot 1* is placed in the queue; then you receive priority.

## 3.2 Action phase

You receive priority. In any order, you may:

- play 1 loot card (activating your character lets you play an additional loot
  card, and that may be done on any player's turn);
- buy one item — from the shop or the top of the treasure deck;
- attack once — an active monster or the monster deck.

A purchase and an attack may only be declared into an empty queue: neither can
be made in response to something else.

## 3.3 End phase

1. "At the end of your turn" effects trigger; then you receive priority. An
   effect that ends a turn jumps straight to this step.
2. **All players and all monsters heal fully**, and then effects that last
   "till end of turn" stop applying.
3. Discard down to 10 loot cards in hand.
4. Pass the turn to the player on your left.

---

# 4. Priority and the queue

- Only the player with priority may play effects, buy or attack.
- While you hold priority you may play any number of effects before passing.
- The top (last added) effect of the queue resolves when every player has
  passed in turn without adding anything. After anything resolves, the active
  player receives priority again.
- Loot cards, activated abilities and paid abilities may be played in response
  to anything in the queue. A purchase and an attack may not.

Simultaneous effects enter the queue in this order:

1. Effects of monster cards, including a monster's death. The active player
   orders several of these.
2. Everything else, in turn order starting from the active player; a player who
   owns several orders their own. A player's death belongs to that player.

---

# 5. Dice

- Every roll uses one six-sided die.
- A roll result and a monster's difficulty are never above 6 nor below 1.
- The initial result enters the queue; effects that change a roll modify that
  result, and the final result is what resolves.
- A roll made as part of an attack is an *attack roll*.

---

# 6. Purchase

- Once per turn, during your action phase, you may buy one item for 10¢.
- You may buy a shop item or the top card of the treasure deck.
- Declare what you are buying; the declaration goes into the queue. When it
  resolves you lose 10¢ and gain the item, and a vacated shop slot is refilled
  from the top of the treasure deck.

---

# 7. Attack

Once per turn, during your action phase, you may attack one monster: an active
monster, or the monster deck. The steps are:

1. Declare the target. The declaration goes into the queue; when it resolves,
   the attack begins.
2. If you attacked the monster deck, reveal its top card. A monster goes into a
   slot on top of the active monster there and the attack continues. Anything
   else is played, and the attack ends.
3. Make an attack roll. Below the monster's difficulty is a miss: the monster's
   attack is dealt to you. At or above it is a hit: your attack is dealt to the
   monster.
4. The damage is dealt and anything it triggers resolves. If both fighters are
   still alive, return to step 3.

An attack ends the moment either fighter dies.

Damaging or killing a monster with an effect is not an attack, and does not
trigger anything conditioned on attack rolls or on being attacked.

---

# 8. Monster death

A monster dies when its health reaches 0 or a lethal effect applies to it.

1. Its death goes into the queue.
2. Then the monster card, then its reward, then everything its death triggered.
3. A boss is kept by the active player as a soul card. An emptied slot is
   refilled.

---

# 9. Refilling slots

A slot refills as soon as it is empty, as though it carried the triggered
effect "when this slot is empty, refill it".

1. The refill goes into the queue.
2. A shop slot takes the top card of the treasure deck. A monster slot takes
   the top card of the monster deck; if that card is an event or a curse, the
   active player plays it and the refill is attempted again.

A deck that runs out is rebuilt by shuffling its discard pile. This does not
use the queue.

---

# 10. Player death

A player dies when their health reaches 0, or a lethal effect applies to them.

1. Their death goes into the queue.
2. Curse cards on them are discarded. Then the death penalty goes into the
   queue, and effects conditioned on "before paying the death penalty" and on
   "when a player dies" trigger.

**The death penalty is all of the following:**

- discard 1 loot card;
- lose 1¢;
- destroy 1 of your items, other than an eternal item;
- deactivate every activated item you control and your character card, without
  using them;
- if you are the active player, end your turn.

A player may die only once per turn. **Their health is fully restored at the
end of the next end phase** — the same moment at which everyone heals.

If a death is prevented, health returns to what it was before the lethal damage
or effect.

A dead player may still refill slots and play event and curse cards.

---

# 11. Souls and victory

- Any card with a soul symbol can become a soul card; the symbol says how many
  souls it is worth.
- The first player to hold 4 souls wins.
- A bonus soul is claimed once per game. Discarded after being claimed, it is
  turned face down and nobody may claim it again.

---

# 12. Rooms

Rooms arrived with *Requiem*. They are optional content, added to a game once
the players know the basic rules, and a game without a room deck is a game with
no rooms in it.

- The room cards form their own deck. At the start of the game its top card is
  turned face up into the room slot, which is how it enters play.
- A room in play is an object, and the object is called *the room*.

**Room abilities.**

- Passive and triggered abilities of a room work exactly as they do on any
  other card.
- An activated ability of a room may only be activated by the active player.
- Where a room's ability says "you" without naming a player, it means the
  active player.

**Changing rooms.** During the end phase, if a monster died during the turn,
the active player *may* put the room into the discard pile. If the room slot is
empty afterwards, it must be filled with the top card of the room deck. The
active player may instead keep the room that is in play.

A room that arrives during the change of rooms and prints "at the end of the
turn, discard this" is discarded at the end of the *next* turn: the
end-of-turn effects of this turn have already resolved.

---

# 13. Cancelling and fizzling

A cancelled effect leaves the queue without resolving; loot cards that were
cancelled go to the discard pile.

An effect fizzles at the moment it would resolve when:

- its target has left the game or become immune to it;
- a condition it names is no longer true;
- the monster it declared an attack on is no longer active — the attack does
  not begin, and the attack is not spent;
- the shop item it declared a purchase on has left the slot, or the buyer no
  longer has 10¢ — the purchase is not spent;
- a fighter leaves an attack, which fizzles the attack damage still queued.
