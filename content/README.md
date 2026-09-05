# Content

Card data. The engine reads this directory; it never reads code from it.

```
content/
├── base_game/     official Four Souls cards
├── expansions/    published expansions
├── custom/        community sets
└── user/          your own work in progress
```

The split is by origin only. All four load through the same pipeline and get
the same validation — the engine has no privileged content.

## Adding a set

A set is a directory containing `manifest.json` and any number of card files:

```json
{
  "id": "my_set",
  "name": "My Set",
  "version": "1.0.0",
  "schema_version": "1"
}
```

Card files are JSON, either a single card, a list of cards, or an object with a
`cards` list. Every card is validated against `docs/CARD_SCHEMA.md` and against
the engine's actual vocabulary of effects, triggers, conditions and targets
before a game can start.

Nothing here is loaded automatically. A caller points `ContentLoader` at this
directory:

```python
from fsme.content import ContentLoader
from fsme.runtime.vocabulary import engine_vocabulary

library = ContentLoader(engine_vocabulary()).load_root("content")
```

## What is here now

`custom/engine_demo/` — a small original set written to exercise the engine.
It is not Four Souls content and is not meant to be balanced; it exists so the
pipeline, the setup routine and the tests have something real to work with.

`base_game/` is empty. See its README.
