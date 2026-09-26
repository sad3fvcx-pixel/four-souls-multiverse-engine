# The card-type display model — where a short label belongs

Analysis only. Nothing in `src/` or `tests/` was changed, nothing was
committed. Measured at `188e36f`.

This follows the `CARD_KINDS` analysis, which ended by refusing to fold the
short label into a removal plan. This document is about that one fact: what it
is, where it should live, and what it costs to put it there.

One correction to the stage brief before anything else, because it changes
which variant is in trouble. The brief says deriving `event → Event` produces
*"Your an event"*. It does not — measured, deriving from the enum gives
**"Your event"**. *"Your an event"* comes from using `TYPE_WORDS`, the sentence,
as if it were a label. The two candidates fail differently, and only one of
them fails badly.


## 1. Every source of `CardType`

| where | what it holds | data or derived |
|---|---|---|
| `cards/types.py::CardType` | the twelve members | **data** — the only place a card type exists |
| `cards/types.py::TYPE_WORDS` | a sentence per member, all twelve | **data** |
| `cards/types.py::PRINTED_NUMBERS` | which numbers a kind prints, six members | **data** |
| `runtime/vocabulary.py::USED_BY` | how three kinds are used | **data**, but read from beside `play_loot` and `_activatable` |
| `runtime/vocabulary.py:389` | `values` on the card's `type` field | derived from `CardType` |
| `runtime/vocabulary.py:401` | `values_mean` on that field | derived from `TYPE_WORDS` |
| `runtime/vocabulary.py:354` | `unless_when` on the printed numbers | derived from `PRINTED_NUMBERS` |
| `runtime/target_resolver.py:1005` | `CARD_TYPES` | derived from `CardType` |
| `cards/definition.py:195,228` | the field, and `CardType(...)` on load | consumer |
| `cards/validator.py:63` | `CardType(data["type"])` — the enum is the check | consumer |
| `rules/`, `database/`, `content/`, `lab/bot/` | comparisons against members | consumers |
| `lab/desk/capabilities.py::CARD_KINDS` | six ids, a short label, a sentence | **hand-written copy, plus one fact found nowhere else** |
| `static/author.html` | four display sites | consumer |

**Data:** four declarations, all in two files.
**Derived:** everything in `runtime/vocabulary.py` and `target_resolver.py`.
**Neither:** `CARD_KINDS`.

`TYPE_WORDS` is read in exactly one place — `runtime/vocabulary.py:401` — and
by no test. That single reader is what makes the variants below cheap to
compare.


## 2. The gap, measured

`TYPE_WORDS` is written as a sentence fragment because it is a `values_mean`
entry, meant to complete a sentence *about a choice*: "type: an item kept in
play". The page needs something else in three places — a noun phrase that
stands on its own.

The page's expression is the same at all three sites:

```js
const kindName = can.kinds.find(k => k.id === kind)?.name || kind || "card";
```

Note the fallback. When a kind is not in the list — which is the case for six
of the twelve **today** — `kindName` becomes the raw identifier. This is not
hypothetical and is not caused by any change proposed here. Measured in the
current build, by switching a card's type in the expert editor, which already
offers all twelve:

| kind | `<h1>` today | card face today |
|---|---|---|
| loot | `Your loot card` | `Loot card` |
| event | `Your event` | `event` |
| bonus_soul | `Your bonus_soul` | `bonus_soul` |
| starting_item | `Your starting_item` | `starting_item` |
| token | `Your token` | `token` |

**An author can already reach `Your bonus_soul` in the shipped desk.** The
short-label gap exists now; `CARD_KINDS` masks it for six kinds and for six
only.


## 3. The three variants, measured

All twelve kinds, through the actual heading templates.

| kind | today | **A / C** (declared) | **B** (derived) | from the sentence |
|---|---|---|---|---|
| character | Your character | Your character | Your character | Your a character somebody plays as |
| treasure | Your treasure | Your treasure | Your treasure | Your an item kept in play |
| loot | Your loot card | Your loot card | **Your loot** | Your a loot card, played from hand and discarded |
| monster | Your monster | Your monster | Your monster | Your a monster to fight |
| room | Your room | Your room | Your room | Your a room that changes the table |
| bonus_soul | **Your bonus_soul** | Your bonus soul | Your bonus soul | Your a soul earned for doing something |
| event | Your event | Your event | Your event | Your an event |
| curse | Your curse | Your curse | Your curse | Your a curse that sticks to a player |
| starting_item | **Your starting_item** | Your starting item | Your starting item | Your a character's own starting item |
| soul | Your soul | Your soul | Your soul | Your a soul |
| token | Your token | Your token | Your token | Your a token |
| other | Your other | Your other | Your other | Your something else |

And on the card face, where the label stands alone:

| kind | today | derived |
|---|---|---|
| loot | Loot card | **Loot** |
| bonus_soul | **bonus_soul** | Bonus soul |
| event | **event** | Event |
| starting_item | **starting_item** | Starting item |
| the other eight | correct | identical |

### What this says about each variant

**Variant B — derive `Event` from `EVENT`.** Against the six hand-written
labels it reproduces five exactly and differs on one: `loot` becomes *"Loot"*,
losing the word *"card"*. Against today's behaviour it is **strictly better for
six kinds and worse for one**. No new declaration, no totality to maintain, and
a kind the engine gains gets a label without anyone writing one.

Its cost is that it cannot be corrected. *"Loot card"* is not a
transformation of `LOOT`; it is a judgement about how people say it. Accepting
B means accepting that the desk says *"Your loot"*, and accepting in advance
whatever the thirteenth member's name happens to title-case to.

`Your other` reads oddly under every variant including the hand-written one —
that is the kind, not the mechanism.

**Variants A and C — declare the label.** Identical in what they produce;
they differ only in shape.

- **A** — one entry per member holding both strings, replacing `TYPE_WORDS`'
  value with a pair. Cost measured: `TYPE_WORDS` has exactly one reader, so the
  change is `vocabulary.py:401` picking the description out of the pair.
  Benefit: label and sentence cannot drift apart, because they are one entry —
  a kind added without a label fails at the type level rather than silently.
- **C** — a second mapping, `TYPE_LABELS`, beside `TYPE_WORDS`. **Does this
  make a new copy of the model?** No, on the measured evidence: the file
  already holds three separate mappings keyed by `CardType` — `TYPE_WORDS`,
  `PRINTED_NUMBERS` — and each says a different thing about the same members.
  A fourth is the same pattern, not a duplication of it. But it inherits the
  same exposure: **`TYPE_WORDS`' own completeness is unenforced today** —
  it is a plain dict literal with no exhaustiveness check and no test asserting
  it covers all twelve. A second such mapping doubles the number of unenforced
  totality claims from one to two.

### The comparison that matters

| | B (derived) | A (one entry, two strings) | C (second mapping) |
|---|---|---|---|
| new declaration | none | restructures one | adds one |
| files changed | 2 | 2 | 3 |
| reproduces today's six | 5 of 6 | 6 of 6 | 6 of 6 |
| a new kind gets a label | automatically | must be written, and the type says so | must be written, silently |
| unenforced totality claims | 0 | 1 (as today) | 2 |
| the label can be corrected | **no** | yes | yes |

**A is the recommendation.** It is the only option that both keeps every word
the desk says today and cannot silently omit a kind, and its cost was measured
to be one line, because `TYPE_WORDS` has one reader and no test. B is the
cheapest and is genuinely defensible if *"Your loot"* is acceptable — that is a
judgement about words, and it is the user's, not this document's. C works and
buys nothing A does not, at the price of a second unenforced claim.

Whichever is chosen, the same test is worth writing once: **every member of
`CardType` has a label**. That claim is unenforced for `TYPE_WORDS` today and
would be worth having either way.


## 4. The twelve types

Offering all twelve is not blocked by anything measured. `check_card` accepts
all twelve; `save_card` has no kind gate; the editor's type control already
draws all twelve; the page walked the flow for `event` with no error.

The open question is what to do about the six kinds `PRINTED_NUMBERS` does not
describe. The stage asks whether that is (1) a limitation on creating cards,
(2) missing UI, or (3) content policy.

**It is (3), and the measurement is unambiguous.** The engine refuses nothing:

```
loot  + health 3                      -> clean
loot  + cost 2                        -> clean
soul  + health 3, attack 1, roll 4, cost 2 -> clean
event + cost 5                        -> clean
```

`PRINTED_NUMBERS` is not enforced anywhere. It decides which questions a form
puts, and nothing else. `_printed_on` says its answer as an absence on purpose,
and its docstring says why: *"a kind nobody has described is not in the list, so
nothing is refused to it — silence about `starting_item` is silence, not a
claim that it has no cost."*

So the six kinds are not limited and no control is missing. What is missing is
somebody's statement about the physical cards: does a starting item print a
cost, does an event print anything. That is content policy, it is not this
document's to make, and it should be made deliberately rather than inherited
from the fact that the same six kinds happened to be hidden.

One coincidence worth keeping in view, since it is what has hidden the question
until now: the six kinds `PRINTED_NUMBERS` describes are **exactly** the six
`CARD_KINDS` offers. Nothing links the two lists; they were written by
different hands for different reasons and agree by accident.


## 5. The fate of `CARD_KINDS`

Not deletion. **Move one fact in, then delete what is left.**

| what it holds | where it goes |
|---|---|
| six of twelve ids | `CardType`, already there |
| `about`, six sentences | `TYPE_WORDS`, already there, published as `means` |
| `used_by` | `USED_BY`, already there — `CARD_KINDS` never owned it |
| **`name`, the short label** | **into `cards/types.py` — the only thing that moves** |

Once the label is in the model, `catalogue()["kinds"]` becomes a function of
`CardType`, and `CARD_KINDS` has nothing left to hold.

The order it encodes — "the order they are most often made" — is the one other
thing it carries, and nothing reads it: no test, no logic. It orders six
buttons. It is a curation, and if it is worth keeping it should be kept as a
statement about prominence rather than as an accident of tuple order.


## 6. Effect on the UI

| site | today | after |
|---|---|---|
| `chooseKind()`, line 302 | six buttons | twelve, drawn identically |
| `pickKind()`, line 312 | reads `used_by` | unchanged — comes from `USED_BY` either way |
| `viewing()`, line 239 | six labelled, six raw ids | twelve labelled |
| `editor()`, line 892 | `Your bonus_soul` | `Your bonus soul` |
| `face()`, line 1830 | `bonus_soul` | `Bonus soul` |
| the editor's type control | already twelve | unchanged |
| saving | no kind gate | unchanged |

No structural change to the page. The `|| kind || "card"` fallback stays — it
is what makes a kind the model has not described degrade to its identifier
instead of to nothing — but with a total label it stops firing.

Five tests read `can["kinds"]`: `test_constructor_walk.py:157`,
`test_constructor_equivalence.py:89` and `:251`,
`test_constructor_sequences.py:64`, `test_author_ui.py:141`. All look entries
up by `id` and read `used_by`; none asserts length, order, or absence. A
twelve-entry list satisfies all five as written.


## 7. Risks

| risk | severity | what the measurement says |
|---|---|---|
| A card stops reading or round-tripping | **none** | 352/352 held with `CARD_KINDS` emptied; `author.py` never referenced it |
| Game behaviour changes | **none** | nothing on this path is imported by `rules/`, `state/`, `stack/` |
| Card JSON or content changes | **none** | `"type"` has always accepted twelve |
| An existing test breaks | **low** | all five readers use `id`; none asserts the list's shape |
| Variant B changes a displayed word | **certain, if B** | `Loot card` → `Loot`, on two screens |
| Variant A/C leaves a kind unlabelled | **low, unenforced** | `TYPE_WORDS`' totality is unenforced today too; one test fixes both |
| Six kinds start being asked for printed numbers | **medium** | §4 — a content decision, made visible rather than caused |
| `used_by` stops reaching the page | **medium** | measured: the loot shortcut is lost. It must keep being published |
| Offering `soul`, `token`, `other` puzzles an author | **judgement** | no shipped card uses them; prominence, if wanted, should be stated rather than achieved by omission |


## 8. Verdict against the success criterion

The criterion was: prove `CARD_KINDS` can be replaced **not by deleting
information, but by moving the single missing fact into the real model**.

**Proven.** Four things are in `CARD_KINDS`; three are already in the model and
one is not.

- The six-of-twelve subset is `CardType`.
- The six sentences are `TYPE_WORDS`.
- `used_by` is `USED_BY`, and always was.
- The short label is nowhere — and the measurement shows it is nowhere *today*,
  for six kinds, visibly, in the shipped build: `Your bonus_soul`.

So the move does not merely preserve what the desk says. **It fixes something
already wrong**: six kinds that an author can reach in the current editor and
that the current editor names with a raw identifier.

Nothing has to be deleted to get there. One fact goes into `cards/types.py`,
`catalogue()["kinds"]` becomes a function of the enum, and what is left of
`CARD_KINDS` is empty.

Two decisions remain, and both are the user's:

1. **Which variant** — A (recommended: keeps every word, one line's cost, one
   reader, no drift) or B (cheapest, self-maintaining, says *"Your loot"*).
2. **Whether the six now-reachable kinds print numbers** — content policy, §4,
   independent of the label and best settled separately.
