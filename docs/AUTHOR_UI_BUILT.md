# Author Experience: what was built

Stage 2 of `docs/AUTHOR_UI.md`. The measure was never "the UI works" but
whether somebody holding one executable can make a card without being told
anything, and find it still there tomorrow.

**That path now runs end to end.** Verified from an empty workspace, over
HTTP, including closing the program and opening it again.

---

## What changed, in three parts

### The engine

| what | why |
|---|---|
| `content/workspace.py` — **new** | an author's sets need somewhere that survives. A frozen build carries its cards *inside itself*, in a directory the operating system wipes; anything saved there is gone before it can be played twice. Sets now live in `Documents/FSME/my sets`, made by the program and never typed by anybody. `FSME_HOME` overrides it for anyone with a reason |
| `ContentLoader.load_roots` | the cards we ship and the cards somebody writes are both content and belong in one library. Read together, checked together — a card id repeated between them is reported exactly as one repeated inside either. A root that does not exist is skipped, because an author with no sets yet has not made a mistake |
| `describes` on every condition and target | 44 + 46 names that anything showing a person a list had no words for. Beside the registration, as effects have had since they were written |
| `asks` on effect parameters | `amount` is cents on one effect and damage on another, so the words belong to the effect. Done for the effects real cards use most |
| `WHEN_IT_HAPPENS` beside `EventType` | 66 moments, in the words somebody would use. In the same file as the enum, so the two cannot drift |
| `ABILITY_SCOPES`, `STATIC_SCOPES` | unchanged from the previous stage; used here to build form choices |

Nothing in the rules changed. **1000 recorded games are identical.**

### The interface

`/` is now the page a person lands on, and it offers what they came to do:

```
Make a card          Start something new.
My cards             2 cards in 1 set.
Watch a game         See the engine play, with your cards in it.
─────────
Everything else      Runs, studies, reports — the tools for measuring.
```

The four tools that used to be the front door — Play a game, Run a study,
Test a card, Open a report — moved to `/advanced`, unchanged. Nothing was
taken away.

Making a card is four questions: what kind, what it is called, when it
happens, what happens. Every list on that page is generated from the
registries:

| the list of | comes from |
|---|---|
| effects, with what each does | `EffectSpec.description` — 63 of 63 |
| what to type into each field | `ParamShape` — kind picks the widget, `values` fills a dropdown, `least` sets the minimum |
| conditions | `ConditionShape.describes` |
| targets | `TargetShape.describes`, filtered by `yields` |
| moments | `WHEN_IT_HAPPENS` |

**There is no second list anywhere in the page.** A test asserts that the
words shown for `gain_coins` and `target_player` are byte-for-byte the
engine's own, so the page cannot drift from what the engine does without the
engine changing first.

### The format

**Unchanged.** The page writes an ordinary set — a directory, a manifest, one
JSON file per card — exactly what somebody typing by hand would produce. A
test loads what the page made through the ordinary pipeline and counts 1046
cards; there is no special case anywhere, and an `author-kit` example and a
page-made card are the same kind of thing.

## What a person never sees

`scope`, `as`, an alias, a JSON path, a file, a folder, a command, or the word
JSON. The engine's messages name a path — `abilities[0].effects[0].amount` —
and the page shows the last clause of it against the field that caused it:
*"'gain_coins' takes a whole number of at least 0 here, and the card gives
text ('three')"*.

Most of the validation layer is unreachable from the page by construction: a
dropdown of real effects cannot produce an unknown effect. What remains
reachable is what somebody types, and that is checked on every keystroke.

## The two cards from the plan

**A simple one** — build it, and it plays:

```
You gained 3¢ (3 → 6)
```

**A die roll and a branch**, the commonest real shape. What the page writes:

```json
{"trigger": "on_play", "effects": [
  {"effect": "roll_dice", "sides": 6},
  {"if": [{"dice_greater": {"value": 3}}],
   "then": [{"effect": "gain_coins", "amount": 4}],
   "else": [{"effect": "lose_coins", "amount": 1}]}]}
```

An author saw three sentences and a pair of boxes. The word "if" never
appeared; it is offered as *"＋ depending on something"*, because `if` is used
more than any single effect in real cards and cannot be an advanced feature.

## Trying a card

"Test a card" answers *does this change how games go* — 200 games, statistics,
two minutes. That is not anybody's first question, and one new card in a
thousand usually never gets dealt, so it used to answer "too scarce to say".

*Try it* answers the first question instead: the card is put in a hand and
played, and what the engine announced is read back. A card that does nothing
says so, because that is an answer too and a common one.

## Checked

| | result |
|---|---|
| the whole test suite | **1243 pass** |
| `content/` | 1045 cards, unchanged |
| `author-kit` examples | 5 of 5 load |
| 1000 recorded games | **0 changed** |
| ruff, mypy --strict | clean |
| the journey, over HTTP, from an empty workspace | 16 steps, all pass |
| closing the program and opening it | the set and the card are still there |

## What is not done

- **Only one ability per card.** A card that reacts to two different moments
  needs the JSON view. Most first cards do not.
- **Statics** — a number that is simply always on — are not on the page yet.
  That is the next thing to add, and the shapes for it already exist.
- **Targets are not offered in the form.** An effect that needs something to
  act on falls back to the engine's default, which is right for a first card
  and wrong for "deal damage to a player you choose". The data is there
  (`yields`, `refers_to`); the form is not.
- **The advanced JSON view is a page away, not built in.**
- **Parameter labels cover the common effects**, not all 74. The rest fall
  back to the parameter's own name, which is honest but plainer.

None of these blocks the path in the title. Each is an ordinary next step.
