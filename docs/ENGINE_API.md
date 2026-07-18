# Four Souls Multiverse Engine
## Engine API Specification
Version: 0.1.0

---

# 1. Purpose

This document defines the public API of the Four Souls Multiverse Engine.

The API is the only supported interface between the engine and external systems.

External systems include:

- User Interface
- Artificial Intelligence
- Networking
- Replay
- Save/Load
- Testing Framework
- Editors

No external system may modify GameState directly.

---

# 2. Design Principles

The Engine API must be:

- deterministic
- stable
- minimal
- platform-independent
- testable

Gameplay logic must never leak outside the engine.

---

# 3. Engine Lifecycle

The engine follows a predictable lifecycle.

Create Engine

↓

Load Content

↓

Create Game

↓

Initialize Players

↓

Start Game

↓

Gameplay Loop

↓

Game Ends

↓

Dispose

---

# 4. Core Interfaces

The engine exposes the following logical interfaces:

- Game Management
- Command Submission
- State Queries
- Event Observation
- Replay
- Save/Load
- Content Loading

---

# 5. Game Management

Responsible for:

- creating a game
- starting a game
- ending a game
- resetting a game

Only one active GameState exists per Engine instance.

---

# 6. Command Interface

External systems submit Commands.

Example flow:

UI

↓

AttackCommand

↓

Engine

↓

Validation

↓

Events

↓

Stack

↓

GameState

Commands never bypass validation.

---

# 7. State Queries

External systems may read GameState.

Queries never modify GameState.

Examples:

CurrentPlayer

CurrentPhase

StackContents

PlayerState

VisibleCards

---

# 8. Event Observation

External systems may subscribe to engine events.

Examples:

GameStarted

TurnStarted

StackChanged

CardPlayed

DamageDealt

GameEnded

Observers receive notifications only.

Observers never change GameState.

---

# 9. Replay Interface

Replay systems may:

- load replay
- start replay
- pause replay
- step replay
- stop replay

Replay uses the same engine as normal gameplay.

---

# 10. Save Interface

Save systems may:

- create save
- load save
- validate save version

Saving captures GameState only.

---

# 11. Content Interface

The engine loads:

- cards
- expansions
- localization
- assets metadata

Gameplay code is never loaded from content files.

---

# 12. Error Handling

Every API operation returns either:

Success

or

Structured Engine Error

Errors never leave GameState partially modified.

---

# 13. Thread Safety

Gameplay execution is single-threaded.

External systems may observe asynchronously but never execute gameplay concurrently.

---

# 14. Versioning

The API follows semantic versioning.

Breaking API changes require a major version increment.

---

# 15. Future Compatibility

Future engine versions may extend the API.

Existing public behavior must remain compatible whenever practical.

---

# 16. Architecture Overview

The overall engine flow is:

External System

↓

Engine API

↓

Command System

↓

Event System

↓

Stack

↓

GameState

↓

Observers

Every gameplay action follows this path.

---

End of Engine API Specification v0.1
