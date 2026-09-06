# Second pass as an outside author

The MVP path worked. This asked what a Four Souls player would hit next, by
building the cards they would actually build. Five things were found; five
were fixed; two are named and left.

---

## What the audit found

### 1. Cards came out doing the opposite of what they said — the serious one

Four target cards were built through the real interface:

| the card | what it built | what it did |
|---|---|---|
| deal 1 damage to a chosen player | no target at all | **damaged the author** |
| choose a player, they lose 2¢ | no target | took the author's cents |
| steal an item from another player | no target | engine's default |
| destroy a chosen item | no target | engine's default |

All four passed validation, and the page said *"This card is ready."* An
author writing "deal 1 damage to another player" got a card that hurt them and
no indication anything was wrong. Nothing else in the audit came close to
this.

### 2. A card that did nothing was called ready

An ability with no effects builds a card with no rules. That is valid content —
the shipped sets are full of cards whose text is not implemented — but
somebody who has just filled in a form did not mean to make one.

### 3. Errors named things the author never chose

`'gain_coins' takes a whole number of at least 0` — but they picked *"Add
coins to a player"* from a list and typed into a box labelled *"how many
cents"*. Neither name in the message was theirs.

### 4. Two moments read identically

"damage has been dealt" and "damage is dealt" were both offered, and so were
two different "an item is destroyed". Not choices anybody can make. And *a
player dies* — one of the six moments in the brief — was buried under "less
common".

### 5. The preview lied by omission

An item card reported "nothing changed", because a fresh table holds only
starting items and those are eternal. The board was wrong, not the card, and
the message sent the author looking for a fault that was not there.

---

## What was changed

**Effects can now be aimed.** An effect that acts on something asks *"Who or
what does this happen to?"*, and the choices are the engine's own words — "a
player somebody picks", "an item somebody picks", "every other player". 41 of
46 targets are offered; the five that are not are the ones meaning nothing on
their own, and that is read off `yields`, not listed.

The author says it once. Both halves are written for them:

```json
"targets": [{"target_player": {"exclude_controller": true, "as": "chosen_1"}}],
"effects": [{"effect": "deal_damage", "amount": 1, "target": "chosen_1"}]
```

Two effects aimed the same way share one choice, because "deal 1 damage to a
player and steal a cent from them" is one player. The words `as` and
`chosen_1` never appear on screen.

The damage card now hits somebody else — tested by playing it, not by reading
the JSON.

**A card with no rules is refused**, in those words.

**Messages name the box.** *"How many cents needs a whole number of at least 0
— you wrote text ('three')."* No path, no identifier. The engine's own
sentence is kept whenever nothing better can be built from it, because a plain
message that has lost the detail is worse than a technical one that still has
it.

**The moments are distinguishable**, all 66 of them, asserted by a test; and
*a player dies* is in the short list where the brief put it.

**The preview plays on a board a card can act on**, and says what it chose:

```
You chose Number Two
You gained 1 item (2 → 3)
Bea lost 1 item (1 → 0)
```

When nothing happens, the choice above it usually explains why — an eternal
item cannot be destroyed, and now the author can see that is what they were
handed rather than suspecting their card.

## What was deliberately not changed

**Multiple abilities and statics.** Asked for as a cost estimate, so here it
is rather than a half-built version.

- *Cost:* moderate, and mostly interface. The card format already allows both;
  `author.build_card` writes one ability because the form has one. A second
  ability is the same form again with its own trigger — perhaps 80 lines of
  page and 20 of Python. Statics are a different form (a number, a scope, a
  condition) and the shapes for it already exist: `node_shapes["static"]`
  carries the keys and the scope domain, and the stat domain is already
  enforced by kind.
- *Risk:* low. Neither touches the engine.
- *Why not now:* neither blocks a first real card, and both would have taken
  the time that the aiming problem needed. A passive item is somebody's third
  card, not their first.

**A separate capability browser.** The brief said not to add one if the data
is already there. It is: every list in the editor is the whole registry, common
entries first, "everything else" one click away. An author discovers what the
engine can do by opening the dropdown they were going to open anyway.

## Checked

| | result |
|---|---|
| whole suite | **1251 pass** |
| `content/` | 1045 cards, unchanged |
| `author-kit` examples | 5 of 5 |
| 1000 recorded games | **0 changed** |
| ruff, mypy --strict | clean |
| the journey over HTTP | 24 steps |

No change to the card format, the engine's rules, or the loader.

## Still open

- One ability per card; statics not on the page (above).
- Parameter labels cover the common effects; the rest show their own name.
- The preview answers every question with the first option. It now says which,
  which makes it honest, but it is not a person playing.
