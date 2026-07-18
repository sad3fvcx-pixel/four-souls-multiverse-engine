# Four Souls Multiverse Engine
## Engine Specification
Version: 0.1.0

---

# 1. Purpose

This document defines the architecture of the Four Souls Multiverse Engine.

The purpose of this specification is to establish a stable engineering foundation before implementation begins.

All future source code should follow the principles described in this document.

If implementation contradicts this specification, the specification must be reviewed first.

---

# 2. Project Goals

The engine must provide:

- Complete implementation of the official Four Souls rules.
- Fully deterministic simulation.
- Replay support.
- Save/Load support.
- Expansion support without modifying engine code.
- Automated testing.
- Platform-independent game logic.
- Clear separation between engine, content and presentation.

---

# 3. Design Principles

## 3.1 Deterministic

The same:

- initial state
- random seed
- player actions

must always produce exactly the same game result.

Determinism is considered a mandatory property of the engine.

---

## 3.2 Engine First

The engine is the source of truth.

UI, animations, networking and AI never modify game state directly.

Every state modification must pass through the engine.

---

## 3.3 Data Driven

Cards are data.

Rules are engine logic.

Adding new cards should not require modifying engine source code whenever existing mechanics are sufficient.

---

## 3.4 Event Driven

Game systems communicate through events.

Systems should not directly depend on each other whenever an event-based solution is possible.

---

## 3.5 Explicit State

The entire game must always be represented by a complete GameState.

No hidden or implicit state is allowed.

---

# 4. Engine Responsibilities

The engine is responsible for:

- validating player actions
- maintaining game state
- deterministic random generation
- stack resolution
- priority handling
- turn progression
- event dispatching
- triggered abilities
- replacement effects
- save/load
- replay generation

The engine is NOT responsible for:

- graphics
- animations
- sounds
- networking implementation
- user interface

---

# 5. Core Components

The engine consists of the following major systems.

- Game State
- Command Processor
- Event Bus
- Effect Resolver
- Stack
- Priority Manager
- Turn Manager
- RNG
- Card Registry
- Expansion Loader
- Save System
- Replay System
- Logger

Each subsystem will receive its own specification document.

---

# 6. Source of Truth

At any moment, there exists exactly one valid GameState.

All systems operate on that state.

No subsystem may maintain an alternative copy of gameplay state.

---

# 7. Content Philosophy

Official Four Souls cards and custom expansion cards are loaded through the same content pipeline.

The engine knows game mechanics.

The engine does not know individual cards.

Cards describe what they do.

The engine performs how they do it.

---

# 8. Future Specifications

The following documents expand this specification.

- RULES_SPEC.md
- CARD_SCHEMA.md
- EVENT_SYSTEM.md
- STACK.md
- RNG.md
- SAVE_SYSTEM.md

These documents together define the complete engine.

---

# 9. Versioning

This specification evolves together with the engine.

Breaking architectural changes require updating this document before implementation.

---

End of Engine Specification v0.1
