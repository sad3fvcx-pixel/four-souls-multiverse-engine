# Migrating `CARD_KINDS.name` into the card-type model

Analysis of an implementation. Nothing in `src/` or `tests/` was changed and
nothing was committed. Measured at `188e36f`.

Everything below was **built and served as a working prototype in the
scratchpad**, patching `catalogue()` at import time, and every mandatory check
was run against a live desk on that prototype. The measurements are of a thing
that ran, not of a thing described.

`promise`, `PRINTED_NUMBERS`, `content/`, `rules/` and `a.out` were not
touched.


## 1. Where the label physically lives

**In `cards/types.py`, beside `TYPE_WORDS`** — one mapping keyed by `CardType`,
carrying the one fact about a card type that nothing else in the repository
holds.

That file is already where the person-facing facts about a card type live:
`TYPE_WORDS` says what each kind is, `PRINTED_NUMBERS` says what each kind
prints. A third mapping saying what each kind is *called* is the same pattern,
not a new one. `capabilities.py` imports nothing from `fsme.cards`, and must
not start — the label reaches the desk the way `used_by` already does.

**How it reaches the page.** `Vocabulary` already carries exactly this kind of
thing:

```python
used_by: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
"""
How a card of each kind does the thing it is for, where the engine says.
"""
```

A sibling field — a mapping from kind to its name — is the precedented
publication, and it is the smallest one: no new `ParamShape` field, no new
metadata concept, nothing generic invented for a single user. A short label is
wanted by one closed set of values in the whole vocabulary; adding a general
"short name for a choice" to `ParamShape` would be inventing a concept for one
caller.

So the chain is the one that already exists for `used_by`:

```
cards/types.py            the label, declared once per member
        ↓
runtime/vocabulary.py     carried on Vocabulary, beside used_by
        ↓
capabilities.py           read, never restated
        ↓
author.html               drawn, unchanged
```


## 2. Replacing the reading of `CARD_KINDS`

One function, and the prototype is what ran:

```python
def kinds(vocabulary):
    """
    Every kind of card there is, named and described, in the order declared.

    Read off the card's own `type` field — the same one the editor draws — so
    a kind the engine gains is offered without anything here being told.
    """
    field = vocabulary.node_shape("card").params["type"]
    said = dict(field.values_mean)
    return [
        {
            "id": kind,
            "name": vocabulary.type_labels.get(kind, kind),
            "about": said.get(kind, ""),
            "used_by": vocabulary.used_by.get(kind, ""),
        }
        for kind in field.values
    ]
```

Four fields, four sources, none of them written here:

| field | source | already published? |
|---|---|---|
| `id` | the `type` field's `values` ← `CardType` | yes |
| `about` | the `type` field's `values_mean` ← `TYPE_WORDS` | yes |
| `used_by` | `vocabulary.used_by` ← `USED_BY` | yes |
| `name` | `vocabulary.type_labels` ← the new declaration | **no — this is the migration** |

`CARD_KINDS` is then read by nothing and deleted.


## 3. Files that change

| file | change | size |
|---|---|---|
| `src/fsme/cards/types.py` | one mapping declared, beside `TYPE_WORDS` | one block |
| `src/fsme/content/vocabulary.py` | one field on `Vocabulary`, beside `used_by` | one field |
| `src/fsme/runtime/vocabulary.py` | pass it in `engine_vocabulary()`, as `used_by` is passed | one line |
| `src/fsme/lab/desk/capabilities.py` | `CARD_KINDS` deleted; `catalogue()["kinds"]` calls the function above | one tuple out, one function in |
| `tests/` | new: the offer equals the model; every member has a label | two tests |

**Not changed:** `static/author.html` — measured, zero edits; `author.py`;
`cards/definition.py`; `cards/validator.py`; `runtime/target_resolver.py`;
`rules/`; `state/`; `effects/`; `content/`; every card file.


## 4. What is preserved, measured

The prototype was served and its `/api/capabilities` compared with today's.

**`used_by` — preserved, and one entry stops being discarded.**

```
loot           on_play        (as today)
treasure       on_activate    (as today)
starting_item  on_activate    ← declared in USED_BY, thrown away until now
```

`USED_BY` has always held `starting_item`; `CARD_KINDS` did not offer that kind,
so the answer was computed on every request and dropped. Measured in the live
prototype, creating a starting item now reaches *"What should this card do?"*
instead of falling through to the expert editor. **This is the only behaviour
change in the whole migration, and it is `USED_BY` finally being obeyed.**

**Order — preserved, by declaring the labels in the order kinds are offered.**

```
offered:  loot, treasure, monster, character, room, curse,
          bonus_soul, event, starting_item, soul, token, other
```

The first six are `CARD_KINDS`' order exactly — "the order they are most often
made" — with the other six after them. Measured: `order of the old six
unchanged: True`.

This is worth being explicit about, because it means the label mapping carries
**two** facts: what each kind is called, and the order an author meets them.
The alternative is to iterate `CardType` and accept its declaration order
(character, treasure, loot, …), which loses the curation. Reordering `CardType`
itself is the option to avoid: its order feeds `CARD_TYPES` in
`target_resolver.py:1005`, which is the option order of two search filters, so
the enum's order is not free.

**Names — preserved exactly for all six.** Measured: `names kept for the old
six: True`. `Loot card`, `Treasure`, `Monster`, `Character`, `Room`, `Curse`.

**The existing UI — preserved structurally.** `author.html` needs no edit. The
`?.name || kind || "card"` fallback stays and simply stops firing, because
every kind now has a name.

### The one thing not preserved

The six `about` sentences change wording, because they stop being
`CARD_KINDS`' re-written copies and start being `TYPE_WORDS`. Measured on the
opening screen of the prototype:

| | today | prototype |
|---|---|---|
| **Loot card** | Played from your hand, then discarded. | a loot card, played from hand and discarded |
| **Treasure** | An item you keep in play. | an item kept in play |
| **Monster** | Something to fight. | a monster to fight |
| **Bonus soul** | *(no button)* | a soul earned for doing something |
| **Event** | *(no button)* | an event |
| **Starting item** | *(no button)* | a character's own starting item |

The six new ones read well. Of the six old ones, `Loot card / a loot card,
played from hand and discarded` is redundant — the subtitle repeats the title —
and all six read as fragments rather than sentences, because that is what
`values_mean` is for: completing "type: an item kept in play" in the editor's
select.

**This is a decision, not a defect, and it should be made deliberately:**

- **(a)** accept the fragments — they are the model's own words, and the
  duplication goes away completely;
- **(b)** sentence-case them on display — cheap, still redundant for `loot`;
- **(c)** move `CARD_KINDS`' six sentences *into* `TYPE_WORDS`, replacing the
  fragments — but that changes what the editor's type select reads, from
  "type: an item kept in play" to "type: An item you keep in play.";
- **(d)** declare an offering sentence beside the label — which puts the
  sentence back in two places, and is the thing this whole stage exists to
  remove.

**(a) is the recommendation.** (d) should be refused for the same reason
`CARD_KINDS.about` is being deleted.


## 5. Guarding against a new hardcoded list

The new declaration is a mapping keyed by `CardType`, which is the same shape
as `TYPE_WORDS` and `PRINTED_NUMBERS` — a declaration, not a copy of one. What
makes it safe is not its shape but two checks, and one of them is worth having
regardless:

1. **Totality.** *Every member of `CardType` has a label.* Note that
   **`TYPE_WORDS`' own completeness is unenforced today** — it is a plain dict
   literal with no exhaustiveness check and no test — so this test is worth
   writing for both mappings at once. Without it, a thirteenth member gets its
   raw identifier as a name, silently, which is exactly the failure this stage
   is fixing.
2. **No second list downstream.** *The ids the desk offers equal
   `{str(k) for k in CardType}`.* This is what actually forbids a future
   hand-written subset — it fails the moment anyone filters, reorders into a
   literal, or re-adds a curated tuple.

A stronger form, if wanted: assert `capabilities.py` contains no card-type
literal at all, in the manner of `test_architecture.py`. The measurement that
makes this feasible: after the migration, `capabilities.py` imports nothing
from `fsme.cards` and names no kind.


## 6. The mandatory checks, run against the prototype

A desk was served with the prototype `catalogue()`, and every check below is
its output.

**Creating a new card — all twelve.**

| kind | `state.card.fields.type` | where it lands |
|---|---|---|
| loot | `loot` | What should this card do? |
| treasure | `treasure` | What should this card do? |
| **starting_item** | `starting_item` | **What should this card do?** ← new |
| monster, character, room, curse | correct | Your monster / character / room / curse |
| bonus_soul, event, soul, token, other | correct | Your bonus soul / event / soul / token / something else |

**Editing an existing card — all twelve**, heading and card face:

| kind | `<h1>` | card face |
|---|---|---|
| loot | Your loot card | Loot card |
| bonus_soul | Your bonus soul | Bonus soul |
| event | Your event | Event |
| starting_item | Your starting item | Starting item |
| the other eight | correct | correct |

Compare with today, where the same six kinds are reachable in the expert editor
and render as `Your bonus_soul`, `Your starting_item`, and a card face reading
`event`. **The migration fixes an existing defect rather than risking one.**

**Page errors:** none, on any screen, for any kind.

**Card JSON — unchanged.** A card of each newly offered kind was saved through
`/api/cards/save` into a scratch set. All six saved. What was written:

```json
{
  "id": "migration_probe-event-probe_event",
  "name": "Probe event",
  "type": "event",
  "expansion": "migration_probe",
  "schema_version": "1",
  "abilities": [{"trigger": "on_play", "effects": [{"effect": "gain_coins", "amount": 1}]}]
}
```

Same keys, same order, same format as every shipped card. `validate_card`
returns clean. The probe set was deleted afterwards; nothing was written under
`content/`.

**Runtime — unchanged.** Nothing on this path is imported by `rules/`,
`state/`, `stack/` or `runtime/runtime.py`. `runtime/vocabulary.py` gains one
argument to a constructor call and no logic. The only new engine-side artefact
is a mapping of names, read by the desk and by nothing that plays a game.

**Cards — unchanged.** Established in the previous stage and unaffected here:
with `CARD_KINDS` emptied entirely, all 352 rules-carrying cards still read,
mean the same, rewrite stably and check clean. `author.py` has never referenced
it.


## 7. Risks

| risk | severity | what the measurement says |
|---|---|---|
| A card stops reading or round-tripping | **none** | 352/352; `author.py` never touched `CARD_KINDS` |
| Card JSON changes | **none** | six kinds saved; identical format, validator clean |
| Runtime or rules change | **none** | one constructor argument; nothing on a game path |
| `author.html` needs editing | **none** | measured: zero edits, all twelve kinds |
| `used_by` regresses | **none** | preserved for loot and treasure; `starting_item` gains the one it was owed |
| Order changes | **none, if declared in offering order** | measured: the old six keep their order |
| Six button subtitles change wording | **certain** | §4 — a decision, four options, (a) recommended |
| A future kind has no label | **low, and only with the test** | §5.1 — the same exposure `TYPE_WORDS` has today |
| `Your something else` reads oddly | **wording** | true of `Your other` too; inherent to the kind, not the mechanism. Worth choosing the label for how it reads in `Your <label>` |
| Six kinds now ask for printed numbers they may not print | **medium** | out of scope by instruction; `PRINTED_NUMBERS` untouched. Named because offering the kinds is what makes it visible |


## 8. Verdict against the success criterion

The criterion was: prove `CARD_KINDS` is replaced by **moving one missing
field**, not by building a new type system.

**Proven, and the prototype is the proof.**

- **One new declaration** — a mapping of twelve names in `cards/types.py`,
  beside two mappings of the same shape that are already there.
- **One new published field** — beside `used_by`, whose docstring already
  describes exactly this kind of per-kind fact for exactly this consumer.
- **One tuple deleted** and one function put in its place, reading four values
  from four existing sources.
- **No new metadata concept**, no `ParamShape` field, no new import in
  `capabilities.py`, no change to `author.html`, no change to card JSON, no
  change to the runtime, the rules, or any card file.

The system of card types is not extended: `CardType` is untouched, and every
kind the desk will offer is a kind it already declared, already validated,
already published on the card's `type` field, and already drew in the editor.
What moves is one string per kind, from the page's own file into the model the
page reads.

Two decisions remain, and both are the user's:

1. **The six `about` sentences** — §4, option (a) recommended.
2. **The wording of the twelve labels**, in particular `other`, which reads
   badly in `Your <label>` under any spelling.

Stopping here, as instructed, for permission to implement.
