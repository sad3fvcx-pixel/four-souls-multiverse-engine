# Four Souls Multiverse Engine
## Rules Specification
Version: 0.1.0

---

# 1. Purpose

This document defines the rule set implemented by the engine.

It specifies which rules are considered canonical, which mechanics must be supported by the engine, and how compatibility with future expansions is maintained.

This document is not intended to replace the official rulebook.

---

# 2. Canonical Sources

The engine follows the official Four Souls rules.

The following sources are considered authoritative:

- Official Four Souls Rulebook
- Official Four Souls Comprehensive Rules
- Official card wording
- Official errata and rule clarifications

If multiple sources conflict, the newest official clarification has priority.

---

# 3. Engine Philosophy

The objective of the engine is to reproduce the official game behavior.

The engine must never intentionally simplify or alter official mechanics unless explicitly configured by a custom ruleset.

Correctness has higher priority than implementation simplicity.

---

# 4. Supported Mechanics

The engine must support every official gameplay mechanic, including but not limited to:

- Turn structure
- Priority
- The Stack
- Triggered abilities
- Activated abilities
- Replacement effects
- Static effects
- Dice rolls
- Combat
- Death
- Rewards
- Souls
- Loot cards
- Treasure cards
- Monster cards
- Rooms
- Curses
- Eternal items
- Passive abilities
- Active abilities
- State-based actions

Future official mechanics should be implementable without redesigning the engine.

---

# 5. Turn Structure

The engine must implement the official turn order.

Each phase is represented explicitly.

The active phase is always part of the current GameState.

---

# 6. Priority

Priority determines which player may perform actions.

Priority handling must be deterministic.

Whenever the official rules require players to respond, the engine enters a priority window.

---

# 7. Stack

The Stack is the only mechanism used to resolve effects that officially use it.

The Stack operates using Last In, First Out (LIFO).

Resolution order must always be deterministic.

---

# 8. Trigger Resolution

Triggered abilities are generated automatically by the engine.

Triggers enter the Stack according to official timing rules.

The engine must preserve deterministic ordering whenever multiple triggers occur simultaneously.

---

# 9. State-Based Actions

State-Based Actions are checked automatically whenever required by the rules.

Players cannot interrupt this process.

The engine is solely responsible for executing State-Based Actions.

---

# 10. Randomness

Every random event must originate from the engine RNG.

Examples include:

- Dice rolls
- Deck shuffling
- Random card selection
- Random player selection

No gameplay randomness may exist outside the engine RNG.

---

# 11. Illegal Actions

Players cannot perform illegal actions.

The engine validates every command before execution.

Illegal commands never modify GameState.

---

# 12. Custom Content

Custom cards must obey the same engine rules as official cards.

Custom content extends gameplay.

It does not redefine engine behavior.

---

# 13. Compatibility

The engine should remain compatible with future official Four Souls expansions whenever technically possible.

Engine APIs should be designed with forward compatibility in mind.

---

# 14. Deviations

If the engine intentionally differs from official rules, every deviation must be:

- documented,
- versioned,
- optional whenever possible.

Silent rule changes are prohibited.

---

# 15. Testing Requirements

Every implemented mechanic must be covered by automated tests.

Official examples should be reproducible inside the engine.

Regression tests must ensure future changes do not alter existing behavior unintentionally.

---

End of Rules Specification v0.1
