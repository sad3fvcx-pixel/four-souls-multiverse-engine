# `card.rewards` — three known names inside a deliberately open map

Analysis only. Nothing in `src/`, `tests/` or `content/` was changed, nothing
was committed. Measured at `f2c028e`.

Runtime execution, `content/`, `when`, step-local bindings, the guided walk and
`DRAWS` were not touched, and nothing here proposes touching them.

**Classification: B — a declaration missing for a concept the engine already
has** — with one honest cost, stated in §5, and one correction to the premise
this stage was set up on.


## 0. A correction to the premise

I told you last turn that `rewards`' names are **closed**, on the strength of
`_pay_rewards` reading three of them by name. That was half right and the
missing half matters. `CardDefinition.rewards` says so itself:

> What defeating this card pays out, beyond its printed souls.
>
> Keys the engine understands are ``cents``, ``loot`` and ``treasure``.
> **Unknown keys are ignored rather than rejected, so a future reward type does
> not invalidate existing content.**

The set is **open by design**, with three currently understood. So `rewards` is
not the closed-key case I described, and the hypothesis this stage was framed
to test — *"a lost structural node like `cost`"* — is **not** what the
measurement supports. What it supports is smaller and still worth doing.


## 1. Where the source of truth is

Three places, each saying a different part, and none of them the shipped
content:

| fact | where | how it is stated |
|---|---|---|
| **which names the engine understands** | `runtime.py::_pay_rewards` | read by name: `rewards.get("cents")`, `("loot")`, `("treasure")` |
| **that unknown names are kept and ignored** | `CardDefinition.rewards` docstring | stated outright, with the reason |
| **that every value is a whole number** | `definition.py:209` annotation `Mapping[str, int]`, **and** `validator.py:75` | the validator enforces it for *every* key, understood or not: `reward '{key}' must be an integer` |

The payout itself is four-part, and only three of the four live in `rewards`:

```python
payload={
    "souls":    int(definition.souls),        # a card field of its own
    "cents":    int(rewards.get("cents", 0)),
    "loot":     int(rewards.get("loot", 0)),
    "treasure": int(rewards.get("treasure", 0)),
}
```

`souls` is a top-level card field, not a reward key. Measured: **no shipped
card writes `souls` inside `rewards`.**


## 2. What an unknown key does

Measured against all four possibilities the stage listed:

| | answer |
|---|---|
| forbidden? | **no** |
| ignored? | **yes** — `_pay_rewards` reads three by name and looks at nothing else |
| kept for the future? | **yes, and that is the stated reason** |
| a content error? | **no** — the validator accepts it, provided the value is a whole number |

So the value type is enforced across the whole mapping and the key set is not
constrained at all. That combination is the whole finding.


## 3. Shipped content

| | |
|---|---|
| cards carrying rewards | **255** |
| keys used | `loot` ×96, `cents` ×94, `treasure` ×68 |
| keys outside the three | **none** |
| value types | `int` ×258 |
| `souls` written inside `rewards` | **none** |

Content uses exactly the three, and only integers. The openness has never been
exercised.


## 4. Against `cost` and `change`

This is where the hypothesis fails, and the reason is a single line.

```python
# rules/costs.py::unpayable
for kind in cost:
    if kind not in KINDS:
        return f"unknown cost '{kind}'"
```

`cost` **refuses** an unknown key at the boundary. That is why `_COST` could be
published as a node with five described keys: the set is closed and something
enforces it.

`changes` is the same story — `replacement.py:168` refuses any inner key
outside `CHANGES`, which is what made Stage Promise 1 a publication rather than
an invention.

`rewards` has no such line, deliberately. So:

| | key set | enforced? | value kind | published as |
|---|---|---|---|---|
| `ability.cost` | closed, 5 | **yes**, `unpayable` refuses | mixed, per key | a node — `shaped_like: cost` |
| `promise.changes` | open names, **closed inner set** | **yes**, `promise` refuses | per operation | `each_shaped_like: change` |
| **`card.rewards`** | **open by design**, 3 understood | **no** — ignored on purpose | **`int`, enforced for every key** | **nothing said** |
| `promise.when` | open | no | open — depends on the event | nothing said |
| `card.metadata` | open | no | open — `str`/`int`/`bool` measured | nothing said |

`rewards` is not `cost`. It sits between `changes` and `when`: **the names are
open like `when`'s, and the value kind is closed like `cost`'s.** No existing
declaration says that combination, because no existing parameter has it.


## 5. What publishing it would cost — measured, not argued

A prototype was built in the scratchpad: a `rewards` node of three whole
numbers, and the card's `rewards` field declared `shaped_like: rewards`.
Nothing in `src/` was modified; the vocabulary was replaced in a copy and the
real desk served from it.

**Through the reader and writer**, with the declaration in place:

| card writes | written back | kept |
|---|---|---|
| `{"cents": 3, "loot": 1, "treasure": 1}` | identical | yes |
| `{"loot": 2}` | identical | yes |
| `{"loot": 1, "eggs": 2}` | identical | **yes** |
| `{"eggs": 2}` | identical | **yes** |

**Through the page**, editing a card carrying an ignored key:

```
rewards is drawn as: nested, shaped_like "rewards"
controls: setField('state.card.fields.rewards','cents',   …)   ""
          setField('state.card.fields.rewards','loot',    …)   "1"
          setField('state.card.fields.rewards','treasure',…)   ""
after typing 5 into the cents box:  {"loot":1,"eggs":2,"cents":5}
```

Three labelled number boxes instead of a JSON blob, filled from the card, **and
`eggs` survives the edit** — `setField` writes into the mapping without
clearing it.

So describing the three does **not** close the set, and does not break the
promise the docstring makes. That was the risk worth testing and it did not
materialise.

### The one real cost

An unknown key becomes **invisible in the form**. Today the JSON box shows
`eggs` and lets an author remove it; with three boxes it is on the card and not
on screen. No shipped card has one, and the engine ignores them, so the cost is
hypothetical — but it is the honest price of the trade and should be decided
rather than discovered.

### What does not change

- **Card JSON**: measured identical for every case above.
- **Runtime**: `_pay_rewards` untouched; it reads the same three keys.
- **The validator**: still accepts any key with a whole-number value.
- **Cards**: 1045 readable, 352 with rules, 352 checker-clean, unchanged.


## 6. Classification — **B**

**Not A.** Nothing published says which names the engine understands, or that
the values are whole numbers. Measured, `rewards` publishes as `kind: "a set of
named values"`, `role: structure`, `values: ()`, nothing about the inside, and
is drawn as `advanced`.

**Not C.** No new element of the language is needed. `shaped_like` already
means "this mapping is one node of that kind", which is exactly what
`ability.cost` uses it for and exactly what is true here. The prototype used it
unchanged.

**Not D.** This is not the editor's business. Which names the engine
understands and what type their values are are facts about the engine, held in
`_pay_rewards`, the annotation and the validator — the model's side of the
line, not the page's.

**B, then**: a concept the engine already has, stated in three places, and
declared in none. One qualification on the wording, which matters: the
declaration would say *"these three are what the engine understands"*, not
*"these three are all a card may write"*. The first is true and already
written down in the docstring; the second is false and the docstring says so.


## 7. Recommended next stage

**Worth doing, and small.** It is the same shape as the `promise` stages — a
fact the engine holds, enforced where it is used, published nowhere — and the
prototype shows the whole change is a node shape plus one `shaped_like`.

Two things to settle first, both decisions rather than measurements:

1. **The invisible-key trade** (§5). Accept it, or keep a way to see keys the
   engine does not understand. My recommendation is to accept it: no shipped
   card has one, the engine ignores them, and the alternative is a JSON box
   beside three boxes, which is worse than either alone.
2. **Whether `souls` joins them.** It is the fourth part of the same payout and
   the only one that is a card field rather than a reward key. It is already
   published as its own field and is already a whole number, so nothing is
   missing — but a form that shows three of the four numbers a monster pays out
   and puts the fourth elsewhere is worth a deliberate answer rather than an
   inherited one.

**What this stage does *not* settle**, and should not be stretched to: the
three-way split of `A_MAPPING`. Publishing `rewards` moves it from "nothing
said" to `shaped_like`, which leaves `when` and `metadata` as the two that say
nothing — and those two are genuinely open, for two different reasons already
measured. That is a tidier end state than today's three-way silence, and it
arrives as a consequence rather than as a goal.


## 8. Files that would theoretically change

Named, not touched.

| file | what it would carry |
|---|---|
| `src/fsme/runtime/vocabulary.py` | a `rewards` node shape beside `_COST`, and `_card_field` saying the card's `rewards` is one |
| `src/fsme/content/vocabulary.py` | `rewards` added to `NODES` |
| `src/fsme/lab/desk/capabilities.py` | published among the small shapes, and a sentence in `ABOUT_NODES` |
| `tests/` | the three names come from where the runtime reads them; an unknown key survives an edit |

Unchanged: `runtime.py::_pay_rewards`, `cards/definition.py`,
`cards/validator.py`, `content/`, and every card file.
