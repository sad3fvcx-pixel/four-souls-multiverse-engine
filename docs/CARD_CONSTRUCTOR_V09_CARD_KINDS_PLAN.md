# `CARD_KINDS` — unifying the model of card types

Analysis only. Nothing in `src/` was changed, no test was written, nothing was
committed.

The stage brief names `bcf7b4a` as HEAD. `bcf7b4a` is Stage 1C, two commits
back; HEAD is `188e36f`, and `b021e94` and `188e36f` both touched
`lab/desk/author.py` and `static/author.html`. Every measurement below is from
the working tree at `188e36f`.

The stage's success criterion is: *prove `CARD_KINDS` is a redundant copy of an
existing model and can be removed without changing the card language or the
behaviour of the game.*

**It is proven for three of the four things `CARD_KINDS` carries, and refused
for the fourth.** Section 5 states the exception, and section 9 keeps it
separate as Task 7 requires.


## 1. Every source of card type

| source | role | duplicates? |
|---|---|---|
| `cards/types.py` — `CardType` | **declaration.** Twelve members, the only place a card type comes into existence. | no |
| `cards/types.py` — `TYPE_WORDS` | **declaration.** What each of the twelve is, in a person's words. One entry per member. | no |
| `cards/types.py` — `PRINTED_NUMBERS` | **declaration.** Which numbers each kind carries printed on it. Describes six of the twelve, deliberately. | no |
| `cards/definition.py:195,228` | **consumer.** `type: CardType`, and `CardType(data["type"])` on load. | no |
| `cards/validator.py:63` | **consumer.** `CardType(data["type"])` — the enum is the check. | no |
| `runtime/vocabulary.py:389` | **publication.** `values=tuple(str(kind) for kind in CardType)` on the card's `type` field. | no — derived |
| `runtime/vocabulary.py:401` | **publication.** `values_mean=TYPE_WORDS`. | no — derived |
| `runtime/vocabulary.py:354` | **publication.** `_printed_on` turns `PRINTED_NUMBERS` into `unless_when`. | no — derived |
| `runtime/vocabulary.py:285` — `USED_BY` | **declaration.** How a card of a kind does its thing, read from beside `play_loot` and `_activatable`. Three entries. | no |
| `runtime/target_resolver.py:1005` | **publication.** `CARD_TYPES = tuple(str(kind) for kind in CardType)`. | no — derived |
| `rules/`, `database/`, `content/`, `lab/bot/` | **consumers.** Compare against enum members. | no |
| `lab/desk/capabilities.py:102` — **`CARD_KINDS`** | **hand-written list.** Six of twelve ids, a short label, and a sentence. | **yes — for the ids and the sentence. See §5 for the label.** |
| `lab/desk/capabilities.py:133` | **publication.** Zips `CARD_KINDS` with `vocabulary.used_by` into `catalogue()["kinds"]`. | partly |
| `static/author.html` — `can.kinds` | **display,** four sites. | — |
| `lab/desk/author.py` — reader, writer, checker | **nothing.** Measured: not one reference to `CARD_KINDS` or to `capabilities`. | — |

Every row except one either declares a fact once or derives a published copy
from a declaration. `CARD_KINDS` is the only row that restates a fact by hand.


## 2. The real source of truth

```
CardType             ← the twelve exist here, and nowhere else
  ├── TYPE_WORDS         what each one is, one entry per member
  ├── PRINTED_NUMBERS    which numbers six of them print
  └── USED_BY            how three of them are used, read from the rules
        ↓
runtime/vocabulary.py::_card_field
        the card's `type` field: values ← CardType, values_mean ← TYPE_WORDS
        the printed numbers: unless/unless_when ← PRINTED_NUMBERS
        ↓
cards/validator.py           CardType(data["type"]) — the enum is the check
        ↓
lab/desk/capabilities.py::catalogue()
        "cards"  → the card node, carrying the twelve and their words   ✅ model
        "kinds"  → CARD_KINDS, six ids re-worded by hand                ❌ copy
        ↓
static/author.html
        the editor's type control  ← "cards"   → twelve, correct
        the opening screen         ← "kinds"   → six
```

**Declared:** `CardType`, `TYPE_WORDS`, `PRINTED_NUMBERS`, `USED_BY`.
**Derived and published:** everything in `runtime/vocabulary.py`.
**Copied by hand:** `CARD_KINDS`, and only `CARD_KINDS`.

Both branches of the last fork are already in the same HTTP response. The page
receives the correct twelve and the hand-written six together, and draws the
six on the screen where a card is created.


## 3. What `CARD_KINDS` is for

It bundles four things, and they have four different answers.

**(a) Which kinds to offer — a duplicate.** Six of twelve. `TYPE_WORDS`'
docstring already settles the policy and hands the choice on:

> The engine accepts all twelve. Six of them are what an author usually makes,
> and the rest exist because the shipped content has them — so they are
> described rather than hidden, and **whatever offers them decides how
> prominent to be.**

Prominence and absence are not the same thing. Six of the twelve are not less
prominent in the desk; they are not offered.

**(b) `about`, the sentence — a duplicate.** Re-worded, not re-derived:

| id | `CARD_KINDS.about` | `TYPE_WORDS` |
|---|---|---|
| loot | "Played from your hand, then discarded." | "a loot card, played from hand and discarded" |
| treasure | "An item you keep in play." | "an item kept in play" |
| monster | "Something to fight." | "a monster to fight" |
| character | "Somebody to play as." | "a character somebody plays as" |
| room | "A place that changes the table." | "a room that changes the table" |
| curse | "Something unpleasant that sticks to a player." | "a curse that sticks to a player" |

Same six facts, said twice, in two registers.

**(c) `name`, the short label — not a duplicate.** See §5.

**(d) `used_by` — not in `CARD_KINDS` at all.** `catalogue()` looks it up from
`vocabulary.used_by` by id. It is already model-driven and survives any change
to the list. One measured consequence of the drift: `USED_BY` declares
`starting_item`, `CARD_KINDS` does not offer it, so the engine's answer for
`starting_item` is computed on every request and thrown away.

### Is it used for logic?

Four sites in the page, measured:

| line | use | logic or display |
|---|---|---|
| 302 | `chooseKind()` draws one button per entry | **logic** — this list *is* the offer |
| 312 | `pickKind()` reads `used_by` to skip the trigger question | **logic** — but the value comes from the model |
| 239, 892, 1830 | `kindName` in three headings | display |

Nothing in `author.py` reads it. Nothing in `runtime/`, `rules/`, `cards/` or
`effects/` can — `capabilities.py` is a leaf that imports the vocabulary and is
imported only by `server.py`.

### Difference from the real list

| | `CARD_KINDS` | `CardType` |
|---|---|---|
| members | 6 | 12 |
| order | loot, treasure, monster, character, room, curse | character, treasure, loot, monster, room, bonus_soul, event, curse, starting_item, soul, token, other |
| missing | — | bonus_soul, event, starting_item, soul, token, other |

136 shipped cards are of a missing kind (56 event, 71 starting_item, 9
bonus_soul; 38 of them carry rules). `soul`, `token` and `other` have no
shipped cards at all.


## 4. Can the page take its kinds from the model?

Measured by overriding `can.kinds` in the live page with a list derived only
from the card node's own `type` field — `choices` and `means`, nothing else —
and then walking the flow.

| step | result |
|---|---|
| opening screen | draws twelve buttons, no error |
| `pickKind('event')` | `state.card.fields.type = "event"`, editor opens |
| existing cards | unaffected — the editor's type control already came from the model, and `viewing()`/`mine()` only read a label |
| saving | unaffected — `save_card` has no kind gate; `check_card` accepts all twelve, measured one by one |
| page errors | none |

**Structurally the page needs nothing it is not already sent.** Two things it
would lose, both measured, neither structural:

1. **`used_by` must still reach it.** With `used_by: ""` on every entry,
   `pickKind('loot')` fell through to the expert editor. With it, the same call
   reaches *"What should this card do?"*. This is not an obstacle — `USED_BY`
   is already a declaration and `catalogue()` already zips it in by id — but
   whatever replaces the list must keep doing so.
2. **The headings read wrongly.** `"Your an event"`. See §5.

Five tests read `can["kinds"]`: `test_constructor_walk.py:157`,
`test_constructor_equivalence.py:89` and `:251`,
`test_constructor_sequences.py:64`, and `test_author_ui.py:141` asserting the
list is non-empty. All look entries up by `id` and read `used_by`. None asserts
the length, the order, or that a kind is absent. A twelve-entry list built from
the model satisfies all five as written.


## 5. Hidden dependencies — one, and it is real

**Order.** `CARD_KINDS` is ordered "in the order they are most often made";
`CardType` is ordered by nothing the engine reads. Nothing depends on either —
no test, no logic. Deriving from `CardType` changes the order of six buttons on
one screen and nothing else.

**Localisation.** None. There is no localisation layer; every word is written
once in English beside the thing it describes.

**Special types.** `soul`, `token` and `other` exist for shipped content that
does not exist. Offering them costs nothing structurally; whether they should
be offered is a judgement, not a measurement.

**`type name != display name` — yes, and this is the exception.**

`CARD_KINDS` carries two strings per kind. The model carries one. The short one
has no source anywhere else in the repository — measured: `capabilities.py`
lines 103–104 are the only occurrences of `"Loot card"` and `"Treasure"` as
labels in `src/`.

Substituting the sentence for the label produces, measured in the live page:

```
after pickKind('event')          heading: "Your an event"
what 'Your <label>' would read:  "Your a loot card, played from hand and discarded"
```

`TYPE_WORDS` is written as a fragment — *"an item kept in play"* — because it
is a `values_mean` entry, meant to complete a sentence about a choice. The page
needs a noun phrase that stands alone: *"Treasure"*, *"Your loot card"*.

So the short label is not a copy of anything. It is a fact about each of the
twelve kinds that the model does not yet hold, currently stored in the place
that displays it, for six of the twelve.

**A second, quieter dependency: the six-and-six coincidence.**
`PRINTED_NUMBERS` describes six kinds. Measured, they are *exactly* the six
`CARD_KINDS` offers:

```
PRINTED_NUMBERS describes : character, curse, loot, monster, room, treasure
CARD_KINDS offers         : loot, treasure, monster, character, room, curse
```

`_printed_on` says an absence, so a kind nobody has described is refused
nothing — and today nobody can reach such a kind from the opening screen, so
the silence is invisible. Offering the other six makes it visible: a `soul`
card would be asked for hit points, attack, roll **and** cost. That is the
documented behaviour working as written, and it is a content question — which
kinds print which numbers — not a tooling one. It is named here because
removing `CARD_KINDS` is what makes it observable.


## 6. Effect on cards

`CARD_KINDS` was emptied in a scratch simulation and all 352 rules-carrying
cards were put through `read_card` → `build_card` → `read_card`:

```
with CARD_KINDS emptied:  352 held, 0 broken
catalogue kinds now:      []
card type choices still:  12
```

- **read** — unchanged. `author.py` never referenced it.
- **order** — no card holds an order; the list orders buttons only.
- **round-trip** — means-the-same, stable on a second write, and checker-clean
  for all 352, identically to HEAD.

The page keeps offering all twelve on the card's `type` field with the list
gone entirely, because that field never came from the list.


## 7. Boundaries

Confirmed unchanged by anything this analysis proposes:

| | changed? | why |
|---|---|---|
| schema | no | `CardType` already has twelve; nothing is added to it |
| content | no | no card file is read differently or written differently |
| runtime | no | `_card_field` already publishes the twelve |
| rules | no | `USED_BY` is read from the rules and stays read from them |
| effects | no | untouched |
| card JSON | no | `"type"` already accepts all twelve and always has |
| card language | no | nothing gains a construct |
| game behaviour | no | nothing in `rules/`, `state/` or `stack/` is on this path |

**One new field is required**, and per the stage's own instruction it is
described separately rather than folded in — see §9.


## 8. Plan for removing the duplication

Not implemented. Stated so the shape can be judged.

1. **Publish the twelve as the kinds.** `catalogue()["kinds"]` derives its
   entries from the card node's `type` field — the same `choices` the editor
   already draws — rather than from a tuple. `used_by` continues to be looked
   up by id from `vocabulary.used_by`.
2. **Delete `CARD_KINDS`** once nothing reads it.
3. **The sentence** comes from `TYPE_WORDS` through the existing `means`
   publication. No new declaration.
4. **The short label** needs a home in `cards/types.py`, beside `TYPE_WORDS` —
   §9.
5. **Prominence, if wanted**, is decided from the model rather than by absence:
   the desk already knows which kinds shipped content uses and which `USED_BY`
   settles. This is the one place a judgement is genuinely open, and it should
   be made explicitly rather than by leaving six kinds out of a tuple.
6. **`PRINTED_NUMBERS`** — decide separately whether the six undescribed kinds
   print numbers. Not required for removal; made visible by it.

### Files touched

| file | change |
|---|---|
| `src/fsme/lab/desk/capabilities.py` | `CARD_KINDS` deleted; `catalogue()["kinds"]` derived |
| `src/fsme/cards/types.py` | one short label per member — §9 |
| `src/fsme/runtime/vocabulary.py` | publishes that label, as it already publishes `TYPE_WORDS` |
| `src/fsme/lab/desk/static/author.html` | nothing structural; possibly which field `kindName` reads |
| `tests/` | new coverage that the offer equals the model; the five existing readers pass unchanged |

Untouched: `cards/definition.py`, `cards/validator.py`, `rules/`, `state/`,
`effects/`, `content/`, every card file.


## 9. The one thing that is not a duplicate — stated separately

Task 7 asks that a needed new field be described on its own rather than folded
into the plan. This is it.

**What is missing:** a short name for each card type — *"Loot card"*,
*"Treasure"*, *"Bonus soul"* — a noun phrase that stands alone in a heading.

**Why it is not a duplicate:** `TYPE_WORDS` is a fragment that completes a
sentence about a choice, and reads wrongly on its own — measured: *"Your an
event"*. No other short label exists anywhere in `src/`.

**Why it is small:** it is not a new model. It is one more word per member of a
model that already describes all twelve, in the file that already describes
them, published the way `TYPE_WORDS` is already published.

**What is open, and is not decided here:**

- whether the label is declared per member or derived from the member name
  (`BONUS_SOUL` → *"Bonus soul"*), which would change six displayed strings —
  *"Loot card"* becomes *"Loot"*;
- whether it belongs beside `TYPE_WORDS` or as a second word in it.

Neither should be settled by this document, and nothing should be written until
it is.


## 10. Risks

| risk | severity | what the measurement says |
|---|---|---|
| A card stops reading or round-tripping | **none** | 352/352 held with the list emptied; `author.py` never touched it |
| Game behaviour changes | **none** | nothing on this path is imported by `rules/`, `state/` or `stack/` |
| Card JSON or content changes | **none** | `"type"` already accepted twelve |
| An existing test breaks | **low** | all five readers look entries up by `id`; none asserts length or order |
| `used_by` stops reaching the page | **medium** | measured: the loot shortcut is lost. Must be kept, and `starting_item` gains one it did not have |
| Headings read wrongly | **certain, if the label is dropped** | *"Your an event"*. §9 is a precondition, not a follow-up |
| Six kinds start asking for printed numbers they may not carry | **medium** | measured; a content decision, made visible rather than caused |
| Offering `soul`, `token`, `other` confuses an author | **judgement** | no shipped card uses them; §8 step 5 |


## 11. Expected effect

- One hand-written list gone; the desk's offer becomes a function of
  `CardType`, so a kind the engine gains appears without anyone remembering to
  add it.
- Six kinds become reachable when creating a card, matching the twelve the
  editor and the checker already accept — the kinds of 136 shipped cards among
  them.
- One duplicated set of six sentences gone.
- `USED_BY`'s `starting_item` entry stops being computed and discarded.
- No change to the card language, the card files, the runtime, the rules, or
  the behaviour of a game.


## 12. Verdict against the success criterion

**Proven:** the six-of-twelve subset and the six `about` sentences are copies
of `CardType` and `TYPE_WORDS`, and removing them changes no card, no test's
premise, and no game behaviour — 352/352 measured.

**Refused:** the short label is not a copy. `CARD_KINDS` cannot simply be
deleted; three quarters of it can, and the remaining quarter has to be moved
into the model first.

So the honest form of the finding is: **`CARD_KINDS` is a hand-written list
holding one fact the model lacks, and using it as an excuse to hold three the
model already has.** Move the one, delete the three.
