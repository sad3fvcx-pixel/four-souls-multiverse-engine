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
