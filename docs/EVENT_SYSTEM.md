# Four Souls Multiverse Engine
## Event System Specification
Version: 0.1.0

---

# 1. Purpose

The Event System is responsible for coordinating every gameplay interaction inside the engine.

No gameplay mechanic should modify the GameState directly without first creating an event.

Events provide a deterministic, extensible and observable execution model.

---

# 2. Philosophy

Everything that happens in the game is represented as an event.

Examples include:

- start turn
- end turn
- draw card
- play loot
- activate treasure
- attack monster
- roll dice
- deal damage
- heal
- death
- gain coins
- lose coins
- destroy card
- recharge item
- discard card

If something changes the GameState, an event must exist.

---

# 3. Event Lifecycle

Every event passes through the same lifecycle.

Created

↓

Validated

↓

Pre Events

↓

Replacement Effects

↓

Stack (if applicable)

↓

Resolution

↓

Post Events

↓

State-Based Actions

↓

Finished

---

# 4. Event Structure

Every event contains:

- unique identifier
- event type
- source
- controller
- targets
- payload
- timestamp
- status

Events never contain executable code.

---

# 5. Event Categories

The engine distinguishes several categories.

Gameplay Events

Player Events

Combat Events

Card Events

Economy Events

System Events

Custom Events

---

# 6. Pre Events

Pre Events occur before the main effect resolves.

Examples:

BeforeDamage

BeforeDeath

BeforeDiceRoll

BeforeDraw

Abilities may modify or cancel the upcoming event.

---

# 7. Replacement Effects

Replacement effects modify an event before it resolves.

Examples:

Prevent damage.

Replace healing.

Replace death.

Replace reward.

Replacement effects never occur after resolution.

---

# 8. Resolution

During resolution the engine performs the event.

Resolution is atomic.

Either the event succeeds completely or fails without partial execution.

---

# 9. Post Events

After successful resolution, Post Events are generated.

Examples:

AfterDamage

AfterDeath

AfterAttack

AfterDraw

AfterRecharge

These events allow triggered abilities to react.

---

# 10. Event Queue

Events are processed sequentially.

Only one event may be resolving at any given moment.

Nested events are allowed through the Stack.

---

# 11. Cancellation

Events may be cancelled before resolution.

Cancelled events:

- do not modify GameState
- still exist in the replay log
- preserve deterministic history

---

# 12. Event Logging

Every event is recorded.

The replay system reconstructs the entire game from the ordered event log.

---

# 13. Determinism

Events are resolved in a deterministic order.

If multiple events are generated simultaneously, the engine applies official priority rules.

No undefined ordering is permitted.

---

# 14. Extensibility

New event types may be added without changing the Event System architecture.

Unknown custom events must not affect existing engine behavior.

---

# 15. Responsibilities

The Event System is responsible for:

- event creation
- validation
- dispatch
- ordering
- cancellation
- logging
- lifecycle management

The Event System is NOT responsible for:

- rendering
- networking
- animations
- UI

---

End of Event System Specification v0.1
