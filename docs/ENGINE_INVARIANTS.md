# Four Souls Multiverse Engine
## Engine Invariants
Version: 0.1.0

---

# 1. Purpose

This document defines the architectural invariants of the engine.

An invariant is a rule that must always hold true during engine execution.

Violating an invariant indicates a bug in the engine.

---

# 2. General Principles

Engine invariants apply at all times unless explicitly documented otherwise.

Every subsystem is responsible for preserving these invariants.

---

# 3. GameState

- Exactly one active GameState exists per Engine instance.
- GameState is always internally consistent.
- Invalid GameStates must never be observable.

---

# 4. Commands

- All gameplay begins with a Command.
- Commands never modify GameState directly.
- Every Command passes through validation before execution.

---

# 5. Events

- Only Events may produce gameplay state changes.
- Events execute in deterministic order.
- Event execution is atomic.

---

# 6. Stack

- Every StackObject has a unique identifier.
- The Stack resolves from top to bottom.
- Empty Stack means no pending gameplay effects.

---

# 7. RNG

- All randomness originates from the engine RNG.
- No subsystem may use external random sources.
- Equal seeds always produce equal results.

---

# 8. Cards

- Runtime card definitions are immutable.
- Every CardInstance references a valid card definition.
- Card identifiers are globally unique.

---

# 9. Content

- Content is fully validated before gameplay.
- Invalid content never reaches GameState.
- Gameplay never executes raw content files.

---

# 10. Replay

- Replay executes the same pipeline as live gameplay.
- Replay never bypasses validation.
- Equal inputs always produce equal outputs.

---

# 11. Saving

- Saving never modifies GameState.
- Loading is atomic.
- Failed loading leaves the current game unchanged.

---

# 12. API

- External systems interact only through the Engine API.
- No external system modifies GameState directly.

---

# 13. Threading

- Gameplay execution is single-threaded.
- Concurrent state mutation is forbidden.

---

# 14. Testing

Every invariant should be verifiable through automated tests whenever practical.

---

End of Engine Invariants v0.1
