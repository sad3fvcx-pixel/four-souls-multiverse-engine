# `promise` — what is missing, and what is only unpublished

Analysis only. Nothing in `src/`, `tests/` or `content/` was changed, no test
was fixed, nothing was committed. Measured at `ae595fb`.

Two premises the stage was given turned out to need correcting before anything
else could be answered, and both change the shape of the question:

1. **The Constructor does not refuse the four cards.** All four read, mean the
   same, rewrite stably and check clean, today. What `promise` is excluded from
   is the *guided walk*, for one measured reason.
2. **The fields of an event are not free text in fact, only in the language.**
   Only six events in the whole engine can ever be replaced or promised
   against, and between them they carry eleven fields. The set is small, closed,
   and statically visible — and declared nowhere.


## Task 1 — the existing model of change

### Where the six live

`state/promises.py` declares them and applies them in one place:

```python
VALUE  = "value"   # Replace what the event carries outright.
DELTA  = "delta"   # Add to a number the event carries.
FACTOR = "factor"  # Multiply a number the event carries.
CAP    = "cap"     # Lower a number to at most this.
FLOOR  = "floor"   # Raise a number to at least this.
FLIP   = "flip"    # Read a number from the other side: flip less what it was.

CHANGES = (VALUE, DELTA, FACTOR, CAP, FLOOR, FLIP)
```

`Promise.apply_to` is the applier, and it applies them **in that order** —
`value` short-circuits; otherwise delta, factor, cap, floor, flip compose on
one number. The order is behaviour, not presentation.

### Where they are enforced

`effects/builtin/replacement.py:168`, inside `promise` itself:

```python
if not isinstance(change, Mapping) or not set(change) <= set(CHANGES):
    raise EffectExecutionError(
        f"promise cannot change '{key}' by {change!r}; "
        f"a change is one of {', '.join(CHANGES)}"
    )
```

So the closed set is **already imported from beside the applier and enforced at
the boundary**. This is the project's own pattern, done correctly. The one step
missing is the third: it is not published.

### What is published

| operation | named anywhere in `catalogue()`? |
|---|---|
| `value` | yes — a `modify_event` parameter (and `set_roll`) |
| `delta` | yes — a `modify_event` parameter |
| `factor` | yes — a `modify_event` parameter |
| `cap` | **nowhere** |
| `floor` | **nowhere** |
| `flip` | **nowhere** |

And the three that are published are published as something else. `modify_event`
is the *flat* spelling of a change — separate `value`, `delta`, `factor`
parameters beside a `key` — and it implements **three** of the six. `promise`
is the *nested* spelling — `{key: {op: value}}` — and honours all six. Two
spellings of one idea, of different sizes, and only the smaller one described.

Of the four shipped promises, **three use an operation that is declared
nowhere.**

**Answer to Task 1: this half is a missing publication, not a missing concept.**
The concept exists, is closed, is enforced, and is a single tuple away from the
guard that enforces it.


## Task 2 — the event payload

The stage said not to assume the fields are a fixed set. They are not fixed in
the language. They are much narrower in fact than the language allows, and the
measurement is what makes that sayable.

### Only six events can be replaced at all

Read from every `ctx.propose(...)` call in `src/`. A promise waits for an event;
an event a card can change is an event the engine *proposes* before making it
happen. There are six:

| event | payload it is proposed with | payload the engine reads back |
|---|---|---|
| `before_coins_gained` | `amount` | `amount` |
| `before_damage` | `actor`, `amount`, `combat`, `roll`, `target_kind` | `amount` |
| `before_destroy` | *(none)* | — |
| `before_heal` | `amount` | `amount` |
| `before_loot_draw` | `count` | `count`, **`source`** |
| `roll_modified` | `attack`, `natural`, `sides`, `value` | `value`, `sides` |

Eleven distinct field names. `promise.event` meanwhile offers all **66** triggers
as its `values`, so sixty of them name a moment no promise can ever change.

### `source`, `controller` and `targets` are not payload

A correction to my own first measurement, and it matters. `propose` is:

```python
def propose(self, event_type, *, source=None, controller=None,
            targets=None, **payload) -> Event
```

`source`, `controller` and `targets` bind to named parameters and become
top-level `Event` fields. Only `**payload` becomes `Event.payload`, and
`Event.get/set/has` read and write **payload only**. So `ctx.propose(...,
source=DECK)` does *not* put `source` in the payload, and a promise changing
`source` is changing a different thing from the `Event.source` of the same name.

### Three kinds of field, measured

- **Proposed and read** — `amount`, `count`, `value`, `sides`. Real, present
  from the start, and the engine acts on what it reads back.
- **Proposed and never read back** — `actor`, `combat`, `roll`, `target_kind`,
  `attack`, `natural`. Carried so a listener can judge the event; changing one
  changes what other cards see, not what happens.
- **Written only by a replacement** — `source` on `before_loot_draw`. It is
  never proposed into the payload; `loot.py:87` reads
  `proposal.get("source", DECK)`, so it exists only when a card has put it
  there. This is a real field of the event's contract and it appears in no
  payload, no propose call, and no declaration. It is the field `compost` uses.

There is no fourth kind. Nothing measured is a user-chosen name or a free
string: every field an author would ever write is one of the eleven, and which
eleven depends on the event.

**Answer to Task 2: the field names are free text in the language and a closed
per-event set in fact. Nothing declares that set, and it is not derivable from
one place — it is implied by `propose` calls in five files plus `get` calls in
six.**


## Task 3 — the form of the language

`changes` is a two-level thing and the two levels have different answers.

```
changes : { <field name> : { <operation> : <value> } }
             ^ outer                ^ inner
```

### The inner level — describable today, undescribed

A change is a small node with six optional fields, exactly the shape of the
things `NODES` already describes:

```python
NODES = (EFFECT, CONDITION, TARGET, MODE, COST, STEP,
         WORKED_OUT, NAMED_COUNT, ABILITY, STATIC, CARD)
```

`mode`, `cost`, `worked_out` and `named_count` are all in that list precisely
because they are small shapes a card writes inside something else and nobody
writes on their own. A `change` is the same kind of thing. Adding one to `NODES`
is not a new language element — it is the mechanism `named_count` and
`worked_out` already used.

### The outer level — the one thing the language cannot say

The language has two words for nesting, and neither fits:

| word | what it says |
|---|---|
| `a_list_of` | this parameter holds a **list** of nodes of kind X |
| `shaped_like` | this parameter holds **exactly one** node of kind X |

`changes` holds neither. It holds a **map from a name to a node** — several
nodes, each under a name the author chooses. There is no word for that, so
`promise` says only `holds={"changes": A_MAPPING}` — the kind — and nothing at
all about what is inside.

`A_MAPPING`'s own docstring gives the reason, and the reason is now false for
this case:

> What is *inside* one of these cannot be judged before a game exists; that it
> is one can, and the handler already refuses anything else.

For the outer level that is true — a field name is a name. For the inner level
it is not: `replacement.py:168` judges the inside statically, before any game
exists, and refuses anything else. The docstring describes a limitation that the
`promise` handler itself does not have.

`when` is a third shape again — `{field: literal}`, a map from a name to a bare
value, checked by `Promise.about` with `payload.get(key) == value`. Not the same
as `changes`, and not a list or a single node either.

### Could an existing element express it?

Three ways were considered and two are refused on measurement:

- **`shaped_like` on the mapping** — means "exactly one node", so it would say
  `changes` *is* a change rather than *holds* changes. Semantically wrong, and
  the reader would build the wrong thing.
- **`a_list_of` a node carrying its own field name** — `[{"field": "amount",
  "cap": 1}]`. This expresses everything, and it **changes the card JSON**,
  which is out of scope and would break four shipped cards.
- **A word for "a map of X"** — the map analogue of `a_list_of`. One new
  `ParamShape` field, in the same family as the two that exist, saying the same
  kind of thing.

**Answer to Task 3: one missing element of the declaration language — "a map
whose values are shaped like X" — and everything else is publication of facts
that already exist.** The missing element is a declaration word, not a card
language word: no card would be written differently.


## Task 4 — the four cards

**None of them is refused.** Measured through `read_card` → `build_card` →
`read_card` at `ae595fb`:

| card | reads | means the same | stable | `check_card` |
|---|---|---|---|---|
| `compost` | yes | yes | yes | clean |
| `mom_s_bra` | yes | yes | yes | clean |
| `two_of_clubs` | yes | yes | yes | clean |
| `polycephalus` | yes | yes | yes | clean |

Author state holds each one verbatim:

```
compost       {"event": "before_loot_draw", "changes": {"source": {"value": "discard"}}}
mom_s_bra     {"event": "before_damage",    "changes": {"amount": {"cap": 1}}}
two_of_clubs  {"event": "before_loot_draw", "changes": {"count": {"factor": 2}},
               "unlimited": true}
polycephalus  {"event": "roll_modified",    "when": {"attack": true},
               "changes": {"value": {"flip": 7}}}
```

And each does what its printed text says — put through `Promise.apply_to` with
the payload its event really carries:

```
compost       {'count': 1}                 ->  {'source': 'discard'}
mom_s_bra     {'amount': 3}                ->  {'amount': 1}
two_of_clubs  {'count': 1}                 ->  {'count': 2}
polycephalus  {'value': 2, 'attack': True} ->  {'value': 5}
```

### What the Constructor actually does, and what it does not know

`promise` is **drawable** and **not finishable**, and the reason is one field:

```
unfinishable: ['promise', 'watch_for']
why:          [['changes', 'advanced']]
```

`finishable()` offers only effects whose every required field is `shown ==
"form"`. `changes` is `shown: "advanced"`, so the guided walk cannot ask for it.
The expert editor draws it — as a JSON textarea, under an honest label:

> **What it does to the event?** *this one is required*
> Not a single answer: this one is a piece of the card's own rules, so it is
> written the way a card file writes it.

So the facts the Constructor does not know are exactly three, and they are the
three sections above:

1. that a change is one of six named operations (`cap`, `floor` and `flip`
   appear in no published thing at all);
2. that `changes` is a map whose values are those;
3. which fields the chosen event actually has — it offers 66 events where six
   can be promised against, and asks for a field name in a JSON blob.

**Every one of the four cards is expressible by the model as it stands.** They
are expressed by it, and saved by it. What is missing is not expression but
description: a person writing a fifth one has to already know the answer.


## Task 5 — the answers

### 1. Can `promise` be closed by publishing existing facts?

**Mostly, and not entirely.** Three of the four things needed already exist as
facts in the engine:

| fact | exists? | published? |
|---|---|---|
| the six operations, closed | yes, `CHANGES`, enforced | no |
| a change is a small node of optional fields | implied by `apply_to` | no |
| which events can be promised against | yes, six, statically | no |
| which fields each of those carries | yes, eleven, statically | no |
| **a map whose values are shaped like X** | **no** | — |

The last line is the one thing that is not a publication.

### 2. Is a new element of the language needed?

**Yes — one, and it is in the declaration language, not the card language.**

The map analogue of `a_list_of`: a word saying that a parameter of kind
`A_MAPPING` holds, under each name, one node of a named kind. Nothing a card
writes changes; the four shipped cards would be written byte for byte as they
are now; no runtime code changes.

### 3. Why not an existing field?

- `a_list_of` says *list*, and `changes` is not one. Making it one changes the
  card JSON.
- `shaped_like` says *exactly one*, and `changes` holds several.
- `kind == A_MAPPING` says *that* it is a map and, by its own docstring, that
  the inside is unjudgeable — which is true of the outer level and false of the
  inner one, since `replacement.py:168` judges it statically today.
- `values` / `values_mean` describe the choices for *this* parameter, not for
  the parameters of the things inside it.

### 4. The minimal next step

Not `promise` in one go. The measurement suggests three separable pieces, in
this order, each defensible alone:

1. **Publish the six operations as a node.** A `change` shape beside the other
   small shapes, read from `CHANGES` and from `apply_to`'s own composition
   order, so nothing is listed twice. This is Stage 1A/1B's exact pattern and
   needs no new language word. It makes `cap`, `floor` and `flip` sayable for
   the first time.
2. **Say what a map holds.** The one new declaration word, so `promise` can
   state that `changes` is a map of `change`. Only after (1), because until
   there is a `change` node there is nothing for the word to point at.
3. **Narrow `promise.event` to the events that can be promised against**, and —
   separately, and only if it survives its own analysis — publish each one's
   fields. This is the largest and least certain piece: the six events are
   visible in `propose` calls today but declared in no one place, and
   `before_loot_draw`'s `source` is written by replacements and proposed by
   nobody, so a naive derivation would miss it. It should not be attempted
   inside this stage.

**Recommendation: (1) alone as the next stage.** It is the only piece that is
pure publication, it is where the unpublished facts are worst (`cap`, `floor`,
`flip` are invisible and three of four shipped cards use them), and it is a
precondition for (2). Whether (2) then follows should be decided after (1) is
measured, not now.

`promise` does not need to stay view-only. It is not view-only today — it is
edited and saved through the expert editor, correctly, by all four cards. What
it needs is to stop being a JSON box.


## Not touched

Runtime execution, `content/`, step-local bindings, `PRINTED_NUMBERS`. No card
was changed and no card would be.


## Files changed by this stage

`docs/CARD_CONSTRUCTOR_V09_PROMISE_PLAN.md` — this document. Nothing else.
