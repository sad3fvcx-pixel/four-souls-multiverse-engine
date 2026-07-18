# Four Souls Multiverse Engine
## Command System Specification
Version: 0.1.0

---

# 1. Purpose

The Command System is the only entry point through which external actors may request gameplay actions.

Players, AI, networking, replay and tests never modify GameState directly.

Instead, they submit Commands to the engine.

---

# 2. Philosophy

Commands express intent.

Events express results.

Example:

Player presses "Attack"

↓

AttackCommand

↓

Validation

↓

AttackEvent

↓

Stack

↓

Resolution

↓

GameState changes

Commands never modify GameState directly.

---

# 3. Responsibilities

The Command System is responsible for:

- accepting commands
- validating legality
- rejecting illegal commands
- creating gameplay events
- logging command history

It is NOT responsible for executing gameplay logic.

---

# 4. Command Lifecycle

Every command follows the same lifecycle.

Created

↓

Validated

↓

Accepted / Rejected

↓

Generate Events

↓

Finished

---

# 5. Command Structure

Every command contains:

- unique identifier
- issuing player
- command type
- payload
- timestamp

Commands contain intent only.

---

# 6. Validation

Before execution the engine validates:

- game phase
- player priority
- legal targets
- costs
- ownership
- timing restrictions

Invalid commands never create events.

---

# 7. Command Types

Examples include:

- PlayLootCommand
- ActivateTreasureCommand
- AttackCommand
- BuyTreasureCommand
- EndTurnCommand
- ChooseTargetCommand
- PassPriorityCommand

Future command types may be added without changing engine architecture.

---

# 8. Player Input

User interface translates player actions into Commands.

The engine never communicates with UI directly.

---

# 9. AI

AI produces Commands exactly like human players.

No special execution path exists for AI.

---

# 10. Networking

Remote players submit Commands.

Networking never synchronizes GameState directly.

Only validated Commands are exchanged.

---

# 11. Replay

Replay reproduces gameplay by replaying Commands and deterministic RNG.

Replay never injects GameState snapshots unless loading a save.

---

# 12. Logging

Every command is logged.

Minimum information:

- command id
- player
- timestamp
- result
- generated events

---

# 13. Determinism

Identical command sequences with identical RNG state must always produce identical GameState.

---

# 14. Extensibility

Custom expansions may introduce new command types.

Unknown commands are rejected safely.

---

# 15. Security

Commands must never bypass engine validation.

All gameplay integrity is enforced by the engine.

---

End of Command System Specification v0.1
