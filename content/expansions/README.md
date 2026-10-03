# Expansions

One directory per published expansion, each with its own `manifest.json`.

An expansion that builds on another declares it:

```json
{
  "id": "requiem",
  "name": "Requiem",
  "version": "1.0.0",
  "requires": ["base_game"]
}
```

The loader refuses a library where a required set is missing, rather than
letting a game start with cards whose references do not resolve.
