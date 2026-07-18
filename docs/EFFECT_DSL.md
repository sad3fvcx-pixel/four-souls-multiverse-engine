# Four Souls Multiverse Engine
## Effect DSL Specification
Version: 0.1.0

---

# 1. Purpose

The Effect DSL (Domain Specific Language) defines how gameplay effects are described as data.

Effects are interpreted by the engine.

Cards never execute code directly.

---

# 2. Philosophy

The DSL is declarative.

Cards describe **what** should happen.

The engine decides **how** it happens.

This guarantees deterministic behavior and allows replay, validation and testing.

---

# 3. Effect Structure

Every effect contains:

- type
- parameters
- optional conditions
- optional targets

Example:

DrawCard

DealDamage

GainCoins

Destroy

RollDice

---

# 4. Primitive Effects

Primitive effects are implemented directly by the engine.

Examples:

- DrawCard
- DrawLoot
- GainCoins
- LoseCoins
- Heal
- DealDamage
- Kill
- Destroy
- Recharge
- Tap
- Untap
- RollDice
- AddCounter
- RemoveCounter

Primitive effects are atomic.

---

# 5. Composite Effects

Effects may contain child effects.

Example:

Sequence

Choice

Repeat

RandomChoice

Conditional

Composite effects never perform gameplay directly.

They control other effects.

---

# 6. Conditions

Conditions determine whether an effect executes.

Examples:

- IsActivePlayer
- DiceEquals
- HasCoins
- ControlsTreasure
- HasSoul
- IsMonster
- IsAlive

Conditions never modify GameState.

---

# 7. Targets

Targets are resolved by the engine.

Supported target types include:

- Self
- Owner
- Controller
- ChosenPlayer
- ChosenMonster
- AllPlayers
- AllMonsters
- RandomPlayer
- RandomMonster

Future target types may be registered.

---

# 8. Parameters

Each primitive defines its own parameters.

Examples:

DealDamage:

amount

target

GainCoins:

amount

RollDice:

faces

---

# 9. Validation

Effects are validated before gameplay begins.

Validation checks:

- required parameters
- parameter types
- supported targets
- supported conditions

Invalid effects prevent the game from starting.

---

# 10. Nesting

Effects may contain other effects.

Example:

Sequence

↓

DealDamage

↓

DrawCard

↓

GainCoins

Execution order is deterministic.

---

# 11. Choice

Choice effects allow players to select one branch.

Example:

Choose one:

- Draw 2 cards

or

- Gain 10¢

The engine validates available choices before presenting them.

---

# 12. Random Effects

Random effects must use the engine RNG.

Example:

RandomChoice

RandomTarget

RandomLoot

No randomness may bypass the RNG subsystem.

---

# 13. Engine Extensions

Expansions may register additional effect types.

Extensions must not modify existing primitive behavior.

---

# 14. Serialization

Effects are serialized as structured data.

The DSL contains no executable code.

---

# 15. Versioning

Every DSL document includes a schema version.

Older engine versions should reject unsupported DSL features gracefully.

---

End of Effect DSL Specification v0.1
