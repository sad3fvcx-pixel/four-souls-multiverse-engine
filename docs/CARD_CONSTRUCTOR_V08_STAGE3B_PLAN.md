# Card Constructor v0.8 — Stage 3B, editing a card with several parts

Stage 3A made a card that exists editable, on one condition: the walk shows one
part and what it does, so it only opened a card that has exactly one. That is
182 of the 248 cards that read.

This is the plan for the rest of them. Measured against the engine at
`03f8961`.

---

## 1. What author state already is

A card in hand is one shape all the way down: a node is `{id, fields, groups}`,
and a list of parts is a list of those. `curved_horn`, which does something
when played *and* changes a number afterwards, reads as

```
fields: name, type, abilities[1], statics[1], metadata, tags
  abilities[0]  id='ability'  fields: trigger, effects, description
  statics[0]    id='static'   fields: stat, amount, scope, conditions, description
```

Order is list order. There is no second model, no per-kind wrapper, and no
place where a part is anything but a node.

The card shape names its part lists and carries a human question for each:

| list | a list of | asked | shown | asks |
|---|---|---|---|---|
| `abilities` | `ability` | first | body | *What does it do?* |
| `statics` | `static` | first | body | *What does it change while it is in play?* |

So the headings a multi-part screen needs are already written, in the card's
own words, and a card that grew a third kind of part would bring its own.

---

## 2. Navigation is available from the metadata

Everything the screens need is published:

| Question | Answered by |
|---|---|
| what lists of parts does a card have | `card.fields[*].a_list_of` naming a published shape |
| what is each list called, to a person | that field's `asks` |
| what does a part hold that happens | the part shape's field with `a_list_of == "step"` |
| what does a part say about itself | that shape's fields with `asked == "first"` |
| what may each answer be | `role`, `choices`, `means`, `least` — unchanged |

Nothing new. The page already reads all five: `whereItActs` finds the first of
them today, and `saidOf` already reads a part's own answers back for both kinds
of part without knowing which it has.

---

## 3. How far it reaches

Over the shipped sets:

| | cards | of those that read |
|---|---|---|
| read at all | 248 | |
| **editable today** (one part) | **182** | 73% |
| **editable with several parts** | **226** | **91%** |
| still view only | 22 | 9% |

All 22 are held back for the same single reason — *an action the walk does not
offer* — which is the rule the walk already applies when making a card. There
is no second exclusion left to explain.

The shapes those 226 take:

| abilities | statics | cards |
|---|---|---|
| 1 | 0 | 199 |
| 2 | 0 | 18 |
| 0 | 1 | 15 |
| 1 | 1 | 8 |
| 0 | 2 | 3 |
| 1 | 2 | 2 |
| 2 | 2 | 1 |
| 3 | 0 | 1 |
| 4 | 0 | 1 |

Thirty-four of the 248 have more than one part; the 199 with a single ability
are the ones already editable.

So the work is worth 44 more cards, and — more to the point — it removes the
last structural reason a card cannot be edited. After it, a card is view-only
because of what it *does*, never because of how many parts it has.

---

## 4. The contract, written first — and it already holds

Six tests are in `tests/test_card_rehydration.py` now, at the level of the card
rather than the page, because editing is mutating author state and whether a
multi-part card *can* be edited is a question about the pipeline:

| Claim | Result |
|---|---|
| there are shipped cards with several parts | 34 of them |
| one rebuilds unchanged after being read | all |
| changing a number in one part moves **only** that part | all — no part ever moved its neighbour, or what either picks out |
| and the change is not quietly dropped | all |
| the card still passes the checker afterwards | all |
| the order of the parts survives | all |

**All six pass against the code as it stands.** The pipeline supports
multi-part editing today; only the screens do not. Stage 3B is therefore the
same shape as Stage 3A was — a way in, and no Python.

---

## 5. What the screens need

Two changes, both generalisations of what exists.

### A screen listing the parts

Between "Change it" and the questions. It draws each part list the card shape
declares, under that list's own `asks`, with each part read back by `saidAs`
and `saidOf` — both of which already handle either kind. Picking one goes to
its questions.

For a card with exactly one part this screen has one row, so it can be skipped
and the walk can go straight where it goes today. Nothing about the current
one-part journey changes.

### The walk points at a node, not at a step list

`walk` holds `list` — a path to *one ability's* effects — and `part`, that
ability's shape. Generalised, it holds which part is open and which node inside
it is being asked about, so the same `ask` / `questions` / `oneByOne` serve:

- an **ability** — its trigger and then its actions, exactly as now;
- a **static** — its own first questions (`stat`, `amount`, `scope`), which are
  already `asked: "first"` and `shown: "form"`, so `oneByOne` draws them with
  no new control.

That second case is the only genuinely new behaviour, and it needs no new
metadata: a static's questions are questions like any other.

---

## 6. Order of implementation

1. **The contract is written and passing** — done, six tests.
2. **Generalise `walkable()`** from "one part" to "every part is one the walk
   can handle", and check the count moves 182 → 226 in a test.
3. **The parts screen**, drawn from the card shape's `body` fields.
4. **Point the walk at a chosen part** rather than at the first one.
5. **A static's own questions** through the existing `ask`.
6. **Gate**: `pytest`, `ruff check .`, `mypy src --strict`, `git diff --check`,
   352/1045, 1000-game replay, expert editor unchanged, no JS errors, and the
   file on disk still untouched.

---

## 7. Deliberately not in Stage 3B

- **Saving.** Still. Everything is offered except writing the card back, and
  that stays true until a stage means to change it.
- **Adding or removing a part.** Editing what is there is a smaller and
  separate thing from changing what a card is made of.
- **Control nodes, `store`, computed values.** Unchanged — those cards do not
  read at all.
- **The 22 that use an action the walk does not offer.** They keep the reading
  screen and are told why.
- **A second card model.** There is one, and it is `state.card`.

---

## 8. Risks

| Risk | Weight | What holds it down |
|---|---|---|
| the one-part journey changes | medium | the parts screen is skipped for a card with one part, and every existing constructor test stays as it is |
| a static's questions need a control that does not exist | low | measured: all of them are `shown: "form"`, which `oneByOne` draws |
| editing one part disturbs another | low | the contract test walks every part of every multi-part shipped card |
| the walk becomes a form | medium | one question per screen holds; the parts screen is a list of words, like `sofar` |
| scope creep into saving | **high** | it is the obvious next thing and it is not this stage |

---

## 9. The invariant, unchanged

```
Constructor ──┐
              ├──→ state.card ──→ build_card ──→ CardDefinition ──→ Validator ──→ Runtime
Expert Editor ┘         ↑
                   read_card
```

One card model, one builder, one checker, one runtime, one reader. A card with
four parts is the same object as a card with one, which is why this stage
needs no Python at all.
