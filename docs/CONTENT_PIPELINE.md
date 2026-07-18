# Four Souls Multiverse Engine
## Content Pipeline Specification
Version: 0.1.0

---

# 1. Purpose

The Content Pipeline defines how external game content is transformed into validated runtime objects.

The pipeline guarantees that every card loaded by the engine is complete, valid and deterministic before gameplay begins.

Gameplay never operates directly on raw content files.

---

# 2. Design Principles

The pipeline must be:

- deterministic
- extensible
- validation-first
- version-aware
- independent of gameplay execution

Loading content must never modify GameState.

---

# 3. Supported Content

The pipeline loads:

- Cards
- Expansions
- Localization
- Metadata
- Future content types

Every content type follows the same validation philosophy.

---

# 4. Pipeline Stages

Every content file passes through the following stages.

Read File

↓

Parse

↓

Schema Validation

↓

Semantic Validation

↓

Reference Resolution

↓

Registry Registration

↓

Runtime Definition

↓

Ready for Gameplay

No stage may be skipped.

---

# 5. Parsing

Raw files are converted into structured objects.

Parsing validates syntax only.

Gameplay validation does not occur here.

---

# 6. Schema Validation

Schema validation verifies:

- required fields
- field types
- identifier format
- schema version

Invalid content is rejected immediately.

---

# 7. Semantic Validation

Semantic validation verifies:

- referenced effects
- conditions
- targets
- card types
- duplicate identifiers

The pipeline validates meaning, not just structure.

---

# 8. Registry

Validated content is registered inside engine registries.

Examples include:

- Card Registry
- Effect Registry
- Expansion Registry
- Localization Registry

Registries contain immutable runtime definitions.

---

# 9. Runtime Definitions

After registration, content becomes runtime definitions.

Runtime definitions are immutable.

Gameplay creates instances from these definitions.

---

# 10. Error Reporting

Validation errors must include:

- file
- identifier
- location
- error category
- human-readable explanation

The pipeline should report all detectable errors in a single validation pass whenever practical.

---

# 11. Version Compatibility

Each content file specifies its schema version.

Unsupported schema versions are rejected safely.

Migration tools may be provided by future engine versions.

---

# 12. Extensibility

Future engine versions may introduce new content types.

Existing pipeline stages must remain compatible whenever possible.

---

# 13. Testing

The pipeline supports automated validation tests.

Every official expansion must pass validation before release.

---

# 14. Security

Content files are treated as untrusted input.

No executable code may be loaded from content files.

The pipeline interprets data only.

---

# 15. Responsibilities

The Content Pipeline is responsible for:

- loading content
- validating content
- resolving references
- registering definitions

The Content Pipeline is NOT responsible for:

- gameplay execution
- GameState
- player interaction
- rendering

---

End of Content Pipeline Specification v0.1
