# `when` — a mapping whose inside really cannot be judged

Analysis only. Nothing in `src/`, `tests/` or `content/` was changed, nothing
was committed. Measured at `f2c028e`.

Runtime execution, the event model, event fields, step-local bindings,
`promise`'s behaviour and the guided walk were not touched, and nothing here
proposes touching them.

**Classification: C — an intentionally opaque structure — with one thin B
inside it that is about presentation, not about the language.** The reasoning
is in §5, and it is the opposite of the `changes` result on purpose: the same
argument that made `changes` describable makes `when` not.


## 1. What `when` is

### Where it is declared

One parameter in the whole vocabulary is called `when` — measured, not
assumed. `promise` alone:

```python
holds={"changes": A_MAPPING, "when": A_MAPPING},
literal=("changes", "when"),
asks={"when": "the conditions it waits for"},
```

`kind` is `A_MAPPING`, `role` is `structure`, `required` is False, and nothing
is said about the inside.

### Where the runtime consumes it

`Promise.about`, and nowhere else:

```python
def about(self, payload: Mapping[str, Any]) -> bool:
    """
    Return whether an event is the kind this promise was made about.
    """
    return all(payload.get(key) == value for key, value in self.when.items())
```

Called from `runtime.py::_keep_promises`, as the **third of three filters**,
all of the same kind:

```python
if promise.event != str(event.type):      continue   # which kind of event
if not promise.concerns(player_id, kept): continue   # whom it is about
if not promise.about(event.payload):      continue   # what it carries
```

### What question it answers

Not *"run this if X"* and not *"assign X to Y"*. It answers **"is this the
event I meant?"** — a selector on the event's payload, by exact equality,
deciding whether a stored change applies at all.

The card's own words say the same thing. `polycephalus` reads *"each time the
attacking player misses an attack roll"*: `roll_modified` fires for every roll,
and `{"attack": true}` is what separates the attack rolls from the rest.
`Promise.when`'s docstring puts it plainly — *"The next attack roll' and 'the
next roll' are different promises, and the only thing that tells them apart is
a value the event carries."*

### Why it is not a condition, structurally

`watch_for` answers a similar-sounding question with `conditions` — a real
`a_list_of: condition`. The difference is where each is evaluated.

A watcher **builds an ability** when it fires (`runtime.py:1141`,
`conditions=tuple(watcher.conditions)`), and an ability's conditions go through
the ordinary evaluator with a context. A promise builds nothing: it is stored
state applied inline in the event loop, and `_keep_promises` has no
`AbilityContext` at all.

That is not a detail. The one condition that would express `when` —
`event_value` — begins:

```python
def _event_value(state, context, params) -> bool:
    if context.event is None:
        return False
```

It needs a context with an event on it. There is none where promises are kept.
So "just use conditions" is not a modelling choice that has been overlooked; it
would require building an ability context inside the event loop, which is a
runtime execution change and out of scope by instruction as well as by
judgement.


## 2. Every use, measured

Every card in `content/`, walked for `when` at any depth, on `promise` or
anywhere else:

| card | `when` | event | changes |
|---|---|---|---|
| `monster_deck-bosses-alt_art-polycephalus` | `{"attack": true}` | `roll_modified` | `{"value": {"flip": 7}}` |

**One card. One shape. One field, of type bool.** No non-`promise` use of the
key exists anywhere in the shipped content.


## 3. Existing concepts, tested one by one

| candidate | why it might fit | why it does not |
|---|---|---|
| `conditions` (`a_list_of: condition`) | `watch_for` answers the same-sounding question this way, and `event_value` expresses equality on an event field | no `AbilityContext` exists where promises are kept; `_event_value` returns False without one. Adopting it is a runtime change, not a declaration |
| `each_shaped_like` | the outer shape is identical — a map from a field name to something | it points at a kind in `NODES`, and a bool is not a node. Making one would change the card JSON: `{"attack": true}` → `{"attack": {"is": true}}` |
| `shaped_like` | `ability.cost` is a mapping that says what shape it is | it means *the mapping is one node*, which is false here, and was measured in the `changes` stage to draw the node's own questions with nowhere to put the names |
| `a_list_of` | — | `when` is not a list; the reader refuses a mapping outright |
| `refers_to` | the keys are event field names, the same thing `modify_event.key` names | it describes what one *name* points at, never a container |
| `names_at_least` | it is about how many names an answer holds | it is cardinality over a list of words, not a map, and nothing here has a floor |
| `change` | the sibling parameter uses it | a change is one of six operations; a `when` value is whatever the event carries |
| `A_MAPPING` alone | it is already this | see §5 — for `when` this is arguably the correct and complete answer |

### The mappings the language has, side by side

Measured — five parameters have `kind == A_MAPPING`:

| parameter | what distinguishes it | what it holds |
|---|---|---|
| `ability.cost` | `shaped_like: cost` | the mapping **is** one node |
| `promise.changes` | `each_shaped_like: change` | field → a node of six closed operations |
| `promise.when` | **nothing said** | field → a value the event carries |
| `card.rewards` | **nothing said** | measured: `loot`, `cents`, `treasure` — **three names, all int** |
| `card.metadata` | **nothing said** | measured: 12+ names, `str`/`int`/`bool` — genuinely free |

Three say nothing about their inside, and they are three different things.
`when` sits between the two extremes; `metadata` is documented as free-form
data the engine keeps and does not read.

**An observation this stage did not go looking for:** `card.rewards` is the one
of the three that looks describable — a closed set of three names, all whole
numbers, which is the shape `cost` already has a node for. It is not `when`'s
question and should not be folded into it, but it is worth someone's attention
later.


## 4. Representability, measured

Read → build → read, through the real reader and writer, for the shipped
`when` and six synthetic shapes:

| case | reads | means the same | stable rewrite | kept verbatim | checker |
|---|---|---|---|---|---|
| shipped (`{"attack": true}`) | yes | yes | yes | **yes** | clean |
| two fields | yes | yes | yes | yes | clean |
| a word (`{"source": "discard"}`) | yes | yes | yes | yes | clean |
| a number | yes | yes | yes | yes | clean |
| `false` | yes | yes | yes | yes | clean |
| empty `{}` | yes | yes | yes | yes | clean |
| a nested value | yes | yes | yes | yes | clean |

**Nothing is lost.** Every shape round-trips byte for byte and passes the
checker. The runtime agrees with the reading in each case — `about()` on a
payload of `{"attack": True, "natural": 6}` answers True for the shipped shape
and for the two-field shape, False for the mismatches, True for empty.

So this is not a representation gap. It is a **presentation** one: `when` is
drawn as `advanced`, a JSON box, because `role` is `structure` and nothing says
otherwise.

### One asymmetry found on the way

The two mappings on the same effect are written back differently when empty:

```
empty `when`    ->  {"effect": "promise", …, "changes": {…}, "when": {}}
empty `changes` ->  {"effect": "promise", …, "when": {}}        ← key dropped
                    checker: 'promise' needs 'changes', and the card does not give it
```

`changes` goes through `_written_named`, which drops an entry that says nothing
and lets the checker speak. `when` has no such declaration, so `{}` is written
out — a key that means "any event of this kind", which is what leaving it out
means. Harmless today, and a small inconsistency between two parameters that
look alike.


## 5. Classification — **C, with a thin B about presentation**

**Why C.** `A_MAPPING`'s docstring justifies its silence like this:

> What is *inside* one of these cannot be judged before a game exists; that it
> is one can, and the handler already refuses anything else.

For `changes` that was **false**, and the `promise` stage proved it: the inner
keys are `CHANGES`, a closed set of six, refused statically at
`replacement.py:168`. For `when` it is **true**, and in both halves:

- **The names** are event field names. Stage Promise 2 measured why these
  cannot be a closed set: `compost` changes `source` on `before_loot_draw`, a
  field no `propose` call carries and only a replacement ever writes. The same
  openness applies here.
- **The values** are whatever the event carries, compared by `==`. Measured
  across 30 played games, event payloads hold `bool`, `int`, `str` and `None`.
  There is no kind to declare, because the kind depends on which field, and
  which fields are open.

Nothing about the inside can be said. `A_MAPPING` says the one thing that can
be, and the handler refuses anything that is not a mapping. That is the correct
and complete description.

**The thin B.** A JSON box is not the only honest way to draw "a set of named
values whose values are plain". A row of name/value pairs would be better, and
it needs one thing the model cannot currently say: that this mapping's values
are *plain values* rather than *undescribed data*. Today `when`, `rewards` and
`metadata` are indistinguishable — all `A_MAPPING` + `role: structure` — and
only `metadata` genuinely deserves a JSON box.

That is a real gap and it is **not** the `changes` gap. It would say nothing
about what is inside; it would say only that there is nothing inside to
describe, which is a different claim from saying nothing at all.

**Why this is not D.** There is no publication gap: the runtime knows nothing
about `when` that the model fails to state. `about()` compares payload values
for equality, and "a set of named values" is exactly that. Everything else is
open by nature.


## 6. Safety

Confirmed for anything this analysis proposes — which is, at most, one
declaration about presentation:

| | required? |
|---|---|
| runtime behaviour changes | **no** — `Promise.about` and `_keep_promises` untouched |
| card JSON changes | **no** — measured: every shape already round-trips verbatim |
| event model changes | **no** |
| new renderer branches | **no** — a control for a plain-valued map is one branch **if** it is ever built, and it is not proposed here |
| hardcoded card-specific handling | **no** — one card uses `when`, and nothing would name it |
| card counts | unchanged: 1045 readable, 352 with rules, 352 clean |


## 7. Recommended next stage

**None on `when` itself.** The measurement does not support one:

- one shipped card uses it,
- every shape already round-trips and checks clean,
- the model's description of it is correct and complete,
- and the only improvement available is cosmetic.

Doing it would mean adding a declaration to make one JSON box on one card into
a pair of boxes. That is the wrong trade at this size, and the pattern of the
previous stages — measure, then act where the measurement points — says so.

If a stage is wanted in this area, the honest candidate is **not** `when` but
the question `when` exposed:

> **Three mappings say nothing about their inside, and they are three different
> things.** `metadata` is genuinely free-form and correctly opaque.
> `rewards` is a closed set of three whole numbers and looks describable the
> way `cost` is. `when` is plain values under open names and is correctly
> opaque for a different reason from `metadata`.

Telling those three apart is worth more than drawing `when` better, and it
would give the `when` control its declaration as a side effect rather than as
the point. It should have its own analysis, and it should start with `rewards`,
which is the one with a real closed set behind it.

**Priority: low.** Nothing is broken, nothing is unreachable, no card loses
anything.


## 8. Files that would theoretically change

Nothing, on the recommendation above. Were the presentation stage taken anyway:

| file | what it would carry |
|---|---|
| `src/fsme/content/vocabulary.py` | one declaration distinguishing a plain-valued mapping from undescribed data |
| `src/fsme/effects/builtin/replacement.py` | `promise` saying which `when` is |
| `src/fsme/lab/desk/capabilities.py` | publishing it |
| `src/fsme/lab/desk/static/author.html` | one control, and `DRAWS` gaining a word — which the invariant landed at `f2c028e` would now require |

Unchanged in every case: `state/promises.py`, `runtime/`, the event model,
`content/`, and every card file.
