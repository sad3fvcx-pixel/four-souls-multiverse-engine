# Base game

Empty on purpose.

This is where the official Four Souls cards go: the base set's loot, treasures,
monsters, rooms, characters and their starting items.

They are not here because the engine's author has to put them here. Card names,
printed values and rules text are the published game's content, and transcribing
them from memory would produce a set that looks official and is quietly wrong —
a monster with the wrong roll value or an item with invented wording is worse
than no card at all, because nothing would tell you it was wrong.

The pipeline that loads them is finished and tested. What it needs is accurate
data, from the rulebook, the official card list, or an existing verified
database.

Drop a `manifest.json` here — or a directory per set under this one — and the
loader will pick it up:

```json
{
  "id": "base_game",
  "name": "Four Souls",
  "version": "1.0.0",
  "schema_version": "1",
  "official": true
}
```

Track what is covered in `docs/OFFICIAL_CARD_COVERAGE.md`.
