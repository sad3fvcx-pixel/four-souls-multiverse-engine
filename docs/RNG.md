# Four Souls Multiverse Engine
## Random Number Generator Specification
Version: 0.1.0

---

# 1. Purpose

The Random Number Generator (RNG) is the only source of randomness in the engine.

All gameplay randomness must originate from this system.

---

# 2. Philosophy

Randomness must be deterministic.

Given the same seed and the same sequence of commands, the engine must always produce identical random results.

---

# 3. Responsibilities

The RNG is responsible for:

- dice rolls
- deck shuffling
- random card selection
- random player selection
- random target selection
- any future random gameplay mechanics

No other subsystem may generate random values independently.

---

# 4. Initialization

Every game starts with a single seed.

The seed becomes part of GameState.

The seed is recorded in replay files.

---

# 5. RNG State

Besides the original seed, the engine stores the internal RNG state.

Saving a game preserves the current RNG state.

Loading restores it exactly.

---

# 6. Determinism

Calling RNG methods in a different order changes future results.

Therefore:

- every RNG call must be intentional;
- unnecessary RNG calls are prohibited.

---

# 7. Supported Operations

Examples include:

RollDice(6)

ShuffleDeck()

RandomCard()

RandomPlayer()

RandomChoice()

Future operations may be added without changing the interface.

---

# 8. Logging

Every RNG operation is logged.

Minimum information:

- operation
- arguments
- result
- RNG state before
- RNG state after

---

# 9. Replay

Replay restores the RNG state before executing recorded commands.

Replay must never request external randomness.

---

# 10. Save Compatibility

Save files contain the complete RNG state.

Loading a save guarantees that future random events remain identical.

---

# 11. Testing

Unit tests may replace the RNG implementation with a deterministic mock.

This allows exact verification of gameplay scenarios.

---

# 12. Security

Gameplay logic must never depend on system time or operating-system randomness.

Only the engine RNG is allowed.

---

End of RNG Specification v0.1
