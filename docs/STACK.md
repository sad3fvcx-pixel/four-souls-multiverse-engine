# Four Souls Multiverse Engine
## Stack Specification
Version: 0.1.0

---

# 1. Purpose

The Stack manages the ordered resolution of gameplay objects that require player interaction or delayed execution.

It guarantees deterministic behavior and implements the official Last In, First Out (LIFO) resolution model used by Four Souls.

---

# 2. Philosophy

The Stack exists to postpone resolution.

Objects placed on the Stack do not immediately modify GameState.

They become pending actions awaiting priority and resolution.

Only the object currently resolving may modify GameState.

---

# 3. Core Principles

The Stack must always be:

- deterministic
- ordered
- serializable
- replayable
- observable

The Stack never executes objects in parallel.

---

# 4. Stack Objects

Every StackObject represents one pending action.

A StackObject contains:

- unique identifier
- object type
- source
- controller
- targets
- originating event
- payload
- creation order
- status

---

# 5. Supported Object Types

The Stack may contain:

- Activated Abilities
- Triggered Abilities
- Loot Cards
- Treasure Activations
- Dice Resolution
- Combat Resolution
- Engine Effects
- Custom Expansion Effects

Future object types may be added without changing Stack architecture.

---

# 6. Object Lifecycle

Every StackObject follows the same lifecycle.

Created

↓

Validated

↓

Placed on Stack

↓

Priority Window

↓

Resolved

↓

Removed

↓

Logged

---

# 7. Push Operation

Adding an object to the Stack is called Push.

Push always places the object on top.

Push never resolves the object immediately.

Every Push operation generates a StackChanged event.

---

# 8. Pop Operation

Resolution always removes the topmost object.

Objects are resolved strictly in LIFO order.

No object beneath the top may resolve first.

---

# 9. Priority Windows

After every Push, players receive a priority window according to official rules.

Players may:

- activate abilities
- play loot cards
- pass priority

When all players pass consecutively, the top StackObject resolves.

---

# 10. Nested Objects

Resolving one StackObject may generate additional StackObjects.

New objects are always pushed on top.

The parent object pauses until the new top objects have fully resolved.

---

# 11. Triggered Abilities

Triggered abilities never resolve immediately.

They become StackObjects.

Their ordering follows official timing rules and deterministic engine ordering.

---

# 12. Replacement Effects

Replacement effects do not use the Stack unless explicitly required by official rules.

They modify events before Stack resolution begins.

---

# 13. Resolution

Resolution consists of:

1. Validate object.
2. Validate targets.
3. Execute effect.
4. Generate resulting events.
5. Check State-Based Actions.
6. Remove object.

Partial resolution is prohibited.

---

# 14. Failed Resolution

If an object becomes illegal before resolution:

- the object still resolves if official rules require;
- otherwise it fizzles.

The replay log must record the exact reason.

---

# 15. Target Validation

Targets are checked immediately before resolution.

Illegal targets are handled according to official rules.

Target validation never changes Stack order.

---

# 16. Interaction with Event System

Every Stack operation generates Events.

Examples:

StackPush

StackPop

StackResolve

StackCancelled

StackFinished

---

# 17. Interaction with GameState

The Stack is stored entirely inside GameState.

Saving GameState preserves the complete Stack.

Loading GameState restores the exact pending resolution order.

---

# 18. Replay Support

Every Stack mutation is recorded.

Replay reconstruction must reproduce:

- Stack contents
- resolution order
- generated events
- resulting GameState

exactly.

---

# 19. Determinism

Stack ordering is deterministic.

When official rules allow multiple simultaneous objects, the engine applies deterministic ordering rules.

No undefined ordering is permitted.

---

# 20. Invariants

The following conditions must always hold:

- Every StackObject has a unique identifier.
- Objects resolve from top to bottom only.
- No duplicate object exists.
- Removed objects never return.
- Empty Stack is valid.
- Negative Stack size is impossible.

Violation of an invariant is considered a critical engine error.

---

# 21. Logging

Every Stack operation is written to the replay log.

Minimum logged information:

- object id
- type
- source
- controller
- targets
- timestamp
- resolution result

---

# 22. Future Extensions

Future engine versions may introduce:

- delayed resolution
- scheduled objects
- multiplayer synchronization
- rollback support

These features must preserve existing Stack semantics.

---

End of Stack Specification v0.1
