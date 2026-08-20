# Four Souls Multiverse Engine
## Card Schema Specification
Version: 0.1.0

---

# 1. Purpose

This document defines the universal card model used by the engine.

Every official card and every custom card must follow this schema.

The schema defines card structure only.

It does not define gameplay rules.

---

# 2. Design Philosophy

Cards are immutable data.

Cards never contain gameplay logic.

Cards describe abilities.

The engine executes abilities.

---

# 3. Card Identity

Every card must have a globally unique identifier.

Example:

base.d6
base.monstro
multiverse.corrupted_isaac

Identifiers are permanent.

Changing an identifier is considered a breaking change.

---

# 4. Required Fields

Every card contains the following mandatory fields.

- id
- name
- type
- abilities
- expansion

---

# 5. Optional Fields

Depending on card type, a card may additionally contain:

- health
- attack
- rewards
- roll
- cost
- passive effects
- activated effects
- flavor text
- artwork
- tags

---

# 6. Card Types

The engine supports the following primary card types.

- Loot
- Treasure
- Monster
- Bonus Soul
- Room
- Curse
- Starting Item
- Event (optional engine extension)

Additional card types may be registered by future engine versions.

---

# 7. Card Metadata

Metadata is never used to resolve gameplay.

Examples include:

- artist
- illustration
- release
- expansion
- rarity
- localization

Metadata exists for editors, UI and asset management.

---

# 8. Abilities

Every gameplay ability is represented as structured data.

Abilities describe:

- trigger
- condition
- effect

The engine interprets abilities.

Cards never execute code directly.

---

# 8.1 Ability Fields

Every ability is an object with the following fields.

Required:

- trigger

Optional:

- conditions
- targets
- effects
- scope
- replacement
- optional
- description

## scope

Determines which events an ability answers.

"self" reacts only when the event concerns this very card.

"any" reacts to every matching event.

When omitted the engine derives it from the trigger: card lifecycle and
activation triggers are self-scoped, everything else is not.

## replacement

When true, the ability changes an event before it happens instead of reacting
to one after.

A replacement applies immediately and never uses the stack.

A replacement is not also a trigger: an ability is one or the other.

---

# 8.2 Statics

A card may change a value for as long as it is in play.

```json
"statics": [
  { "stat": "attack", "amount": 1, "scope": "controller" }
]
```

A static is not an ability. Nothing triggers it, it never reaches the stack,
and it stops applying the moment the card leaves play. It is written separately
because there is no moment at which it happens.

Recognised stats:

- attack
- max_hp
- attacks
- loot_plays

Scopes:

- controller
- opponents
- all_players

---

# 9. Effects

Effects are represented by engine primitives.

Examples include:

- DrawCard
- GainCoins
- LoseCoins
- DealDamage
- Heal
- Destroy
- Recharge
- RollDice
- PreventDamage
- ModifyStat

Future primitives may be introduced without changing existing cards.

---

# 10. Conditions

Abilities may define conditions.

Examples:

- owner is active player
- target is monster
- dice result equals six
- player controls treasure

Conditions are evaluated by the engine.

---

# 11. Targets

Effects may specify one or more targets.

Targets are resolved by the engine.

Examples:

- self
- owner
- chosen player
- chosen monster
- all players
- all monsters

---

# 12. Tags

Tags provide semantic information.

Examples:

- Flying
- Boss
- Curse
- Human
- Demon

Tags are extensible.

Unknown tags must not break the engine.

---

# 13. Validation

Every card is validated during loading.

Invalid cards are rejected before the game starts.

The engine must never load partially valid content.

Validation covers four things, and each is checked against what the engine
actually implements rather than against a document:

1. **Structure.** Required fields, and fields of the right kind.
2. **Names.** Every effect, trigger, condition and target the card mentions.
3. **Arguments.** What the card gives each effect and each condition: the kind
   of value, the values allowed where only a few are, and the floors below
   which a number means nothing. A parameter that is not taken is named, with
   the nearest one that is offered. This matters most for conditions, which
   ignore a parameter they do not recognise: `{"player_hp": {"operatr": "<",
   "value": 2}}` is not a card that fails, it is a card that quietly means
   "equal to zero" and plays a whole game that way. Conditions are checked
   wherever they are written — on an ability, on a static, and inside `if`
   within an ability's effects.
4. **Values worked out while an ability runs.** `{"amount": {"from": "dice"}}`
   is legal; there are five such forms — `from`, `count`, `from_event`,
   `last_result`, `player_of` — and a sixth spelling is a typo rather than a
   new one.

Target parameters are not yet checked; target *names* are. See
`docs/TARGET_AUDIT.md`.

A parameter the engine can only judge with a board in front of it — a card, a
player, a structure, or a value an event happens to be carrying — is not
checked here. That is not permission for anything
to be written: the guard inside the effect stays exactly where it is and still
refuses. It means load time is the wrong moment to ask.

Every problem in a batch is reported together, with the expansion, the file,
the card, the ability and the path inside it:

```
[semantic] example_expansion cards/loot.json: example_expansion-loot-dark_coin:
  ability 0: effects[0].amount: 'gain_coins' takes a whole number of at least 0
  here, and the card gives text ('lots')
```

---

# 14. Forward Compatibility

Unknown optional fields should be ignored safely.

Older engine versions must fail gracefully when encountering unsupported required features.

---

# 15. Serialization

Cards are loaded from external data files.

Runtime modifications belong to GameState, never to the card definition itself.

Card definitions remain immutable during gameplay.

---

End of Card Schema Specification v0.1
