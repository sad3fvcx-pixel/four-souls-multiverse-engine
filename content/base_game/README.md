# Base game

The published base set: loot, treasures, monsters, rooms, characters and their
starting items.

## Two kinds of file

`cards/` is generated. `tools/import_cards.py` writes it from the verified card
database and nothing else — names, printed values, rewards and the English
rules text of every card. Do not edit it by hand; the next import would
overwrite the edit.

`_abilities.json` is written by hand. It maps a card identifier to the
abilities and statics that make the card *do* something:

```json
{
  "loot_deck-bombs-base_game-bomb": {
    "abilities": [
      {
        "trigger": "on_play",
        "targets": [{"target_player_or_monster": {"as": "victim"}}],
        "effects": [{"effect": "deal_damage", "amount": 1, "target": "victim"}],
        "description": "Deal 1 damage to a monster or player."
      }
    ]
  }
}
```

The import merges the overlay into the generated cards, so re-running it never
loses hand-written behaviour. Files beginning with `_` are not loaded as card
files: the overlay is a source for the import, not content in itself.

## Why behaviour is written by hand

Rules text is prose, and prose does not convert into an effect tree without
somebody reading it. A machine guess produces a set that looks official and is
quietly wrong — a monster with the wrong roll value or an item with invented
wording is worse than no card at all, because nothing would tell you it was
wrong.

So a card counts as implemented only when its English text has been read, its
ability written, and a test plays it in a real game and checks the result
(`tests/test_official_cards.py`). Everything else is an imported card with no
behaviour, and `docs/OFFICIAL_CARD_COVERAGE.md` — generated from the content
itself — says exactly which is which.
