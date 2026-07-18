# Four Souls Multiverse Engine
## Save System Specification
Version: 0.1.0

---

# 1. Purpose

The Save System provides complete serialization and restoration of an active game.

A saved game must preserve every piece of information required to continue gameplay without any behavioral differences.

---

# 2. Design Principles

The Save System must be:

- deterministic
- lossless
- versioned
- portable
- forward-compatible whenever practical

Saving and immediately loading a game must produce an identical GameState.

---

# 3. Save Contents

A save file includes:

- GameState
- RNG state
- Stack
- Event Queue
- Active Effects
- Player States
- Zones
- Card Instances
- Engine Version
- Save Format Version

---

# 4. Save Format

The engine uses a structured serialization format.

The format must be:

- human-readable when possible
- deterministic
- extensible

Implementation details are independent of gameplay logic.

---

# 5. Serialization Rules

Every runtime object is serialized exactly once.

References between objects are restored using unique identifiers.

Object identity must remain stable after loading.

---

# 6. Loading

Loading a save performs the following steps:

1. Validate save format.
2. Validate engine version.
3. Restore GameState.
4. Restore RNG.
5. Restore Stack.
6. Restore Event Queue.
7. Validate integrity.
8. Resume gameplay.

---

# 7. Validation

Before gameplay resumes, the engine verifies:

- object references
- player states
- stack integrity
- zone consistency
- active effects
- RNG state

Invalid saves are rejected safely.

---

# 8. Versioning

Every save contains:

- save schema version
- engine version

Migration between compatible versions should be supported whenever practical.

---

# 9. Replay Compatibility

Save files may serve as replay checkpoints.

Replay may continue from a saved GameState without altering deterministic behavior.

---

# 10. Security

Save files are treated as untrusted input.

Every loaded field must be validated before becoming part of GameState.

---

# 11. Error Handling

Loading failures never partially modify the current game.

Either the save loads completely or the current GameState remains unchanged.

---

# 12. Testing

Automated tests verify:

- save → load equality
- deterministic continuation
- version compatibility
- corrupted save rejection

---

End of Save System Specification v0.1
