# Four Souls Multiverse Engine
## Game State Specification
Version: 0.1.0

---

# 1. Purpose

GameState represents the complete and authoritative state of a running game.

At any point in time, the entire game must be reconstructible from a single GameState instance.

No gameplay information may exist outside of GameState.

---

# 2. Philosophy

GameState is the single source of truth.

All gameplay systems read from and write to GameState.

UI, networking, AI and replay systems observe GameState but never own it.

---

# 3. Core Principles

GameState must be:

- complete
- deterministic
- serializable
- versioned
- immutable during event execution (modified only through engine-controlled state transitions)

---

# 4. Global State

The global state contains information shared by the entire game.

Examples include:

- current turn
- active player
- current phase
- priority holder
- stack
- event queue
- RNG state
- game status

---

# 5. Player State

Each player owns an independent PlayerState.

PlayerState includes:

- health
- coins
- souls
- hand
- loot area
- treasures
- active effects
- death status
- statistics

---

# 6. Zones

GameState tracks every game zone.

Required zones include:

- Loot Deck
- Loot Discard
- Monster Deck
- Monster Discard
- Treasure Deck
- Treasure Shop
- Room Deck
- Room Area
- Active Monsters

Future expansions may introduce additional zones.

---

# 7. Card Instances

A card definition is immutable.

When a card enters a game, it becomes a CardInstance.

CardInstance stores runtime information such as:

- current zone
- owner
- controller
- tapped state
- counters
- temporary modifiers

---

# 8. Active Effects

Temporary gameplay effects belong to GameState.

Examples:

- stat modifiers
- prevention effects
- duration-based effects
- turn-based effects

These effects expire according to engine rules.

---

# 9. Stack State

The current Stack is stored inside GameState.

Every unresolved object on the Stack must be represented explicitly.

---

# 10. Event State

The Event Queue is part of GameState.

Pending events, active events and processed events are tracked by the engine.

---

# 11. RNG State

The internal state of the random number generator is stored.

Saving and restoring GameState must also restore future randomness exactly.

---

# 12. Serialization

GameState must support lossless serialization.

Saving and immediately loading a GameState must produce an identical playable state.

---

# 13. Validation

GameState is continuously validated by the engine.

Invalid states must never persist.

Engine invariants are checked after every completed event.

---

# 14. Replay Compatibility

Replay reconstruction must recreate GameState exactly.

Any divergence is considered a critical engine error.

---

# 15. Versioning

Serialized GameState includes a schema version.

Future engine versions should support migration whenever practical.

---

End of Game State Specification v0.1
