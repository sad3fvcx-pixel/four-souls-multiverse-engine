# `field -> change` — an existing structure with no word for it

Analysis only. Nothing in `src/`, `tests/` or `content/` was changed, nothing
was committed. Measured at `08b89a8`.

Runtime execution, event triggers, the event-field rules and step-local
bindings were not touched, and nothing here proposes touching them.

**Classification: B — a new element of the declaration language is required.**
It is one field, it says nothing a card would write differently, and every
other part of the construction is already published. The evidence for B is
measurement, not argument: both existing candidates were run against the real
reader, writer and page, and both were measured to fail — one loudly, one
silently.


## Task 1 — where the concept already exists

Measured from the engine's own structures, not from the shape of the JSON.

### An event field name — published three times

| where | parameter | kind | role | closed set? | sentence |
|---|---|---|---|---|---|
| effect `modify_event` | `key` | text | `names` | no | "which of the event's values" |
| condition `event_value` | `key` | text | `names` | no | "which of the event's values" |
| node `worked_out` | `from_event` | text | `names` | no | "a number the event being answered carries" |

The concept is not missing and not new. Two of the three carry the *same
sentence*, which is as close as the vocabulary comes to saying "these are the
same kind of answer".

### A value read from an event

`event_value` (a condition) and `worked_out.from_event` (a node). Both name a
field and take what is there.

### A value written into an event

Two spellings, both existing:

- `modify_event` — **flat**: `key` beside `value`/`delta`/`factor`, one field
  per call, three of the six operations.
- `Promise.apply_to` — **nested**: `{field: {operation: value}}`, all six.

### A modification of one field — published, as of `08b89a8`

The `change` node: six parameters read from `CHANGES`, in the applier's order.
Stage Promise 1.

### Several modifications grouped — **already a structure in the engine**

This is the finding that decides the classification:

```python
@dataclass(slots=True)
class Promise:
    event: str
    changes: dict[str, dict[str, Any]] = field(default_factory=dict)
```

`changes` is not "JSON that happens to look like a map". It is annotated
`dict[str, dict[str, Any]]` on the dataclass the runtime stores on the game,
and `apply_to` consumes it as one:

```python
for key, change in self.changes.items():
```

Searched across all of `src/fsme`, that annotation shape — a name to a
structure — occurs **twice**: here, and a counter in `cli/main.py`. So there is
exactly one collection of named changes in the engine, and this is it.

### Answers

- **Is `field -> change` already represented somewhere?** Yes —
  `Promise.changes`, as a typed field of the dataclass the runtime keeps.
- **Does the runtime already consume a collection of named changes?** Yes, in
  `apply_to`, by iterating it.
- **Is the missing piece only catalogue publication?** **No.** Publication has
  nowhere to put this. Both halves are published — the key as `role=names`
  text, the value as the `change` node — and nothing in the declaration
  language can say they go together. That is what makes this B rather than A.


## Task 2 — inner and outer

The inner node is enough and is done. What remains is the container, and it is
none of the three things the language can currently describe:

| it might be | is it? | measured |
|---|---|---|
| a list | **no** | `changes` is a mapping; declaring it a list refuses every card that has one — below |
| one node | **no** | `{"source": {"value": "discard"}}` is not a change; it *holds* one |
| free-form data | **no** | `promise` refuses any inner key outside `CHANGES`, statically, at `replacement.py:168` |

It is a fourth thing: **several nodes of one described kind, each under a name
the author chooses.** The names are not from a closed set and are not part of
the node — they are the address the change applies at.


## Task 3 — every existing mechanism, tested

Each candidate was substituted into a copy of the real vocabulary and run
through the real `read_card`, `build_card` and `catalogue()`. Nothing in `src/`
was modified to do it.

### `a_list_of=change` — refused outright

```
compost      UnreadableCard: 'changes' should be a list and is not.
mom_s_bra    UnreadableCard: 'changes' should be a list and is not.
```

Its meaning is "a list of nodes", the reader enforces that meaning, and a
mapping is not a list. **Cannot be reused. Fails loudly, which is correct.**

### `shaped_like=change` — accepted, and wrong

This one is the dangerous candidate, because `A_MAPPING` + `shaped_like` is not
hypothetical: it is exactly how `ability.cost` is declared today.

```
ability.cost      kind='a set of named values'  role='nested'  shaped_like='cost'
```

There it means **"this mapping *is* one node of that kind"** — `{"tap": true,
"coins": 2}` is a cost, whose own field names are `tap` and `coins`. That is a
live meaning with a live user.

Putting it on `changes` says the same thing, and the same thing is false:
`{"source": {"value": "discard"}}` is not a change. Measured consequences:

- **The reader ignores it.** Author state is unchanged, so nothing is gained.
- **The page changes what it asks.** `shown` flips from `advanced` to `nested`
  the moment `shaped_like` is set. Rendered in the real page, serving the real
  card:

  ```
  questions drawn:  "What to put there instead?"
                    "Read it from the other side: this less what it was?"
  a box for the field name 'source'?   False
  the JSON box that used to hold it:   gone
  ```

  The form asks the six operations directly, at the top level, with **nowhere
  to put the field name** — and the textarea that could previously express the
  card has been removed. `compost` becomes unwritable through the form, with no
  error.

**Cannot be reused. It would overload a meaning `ability.cost` depends on, and
it fails silently, which is worse than failing.**

### `A_MAPPING` alone — the situation today

Says *that* it is a map and, by its own docstring, that the inside cannot be
judged. True of the field name; false of the change, which `promise` judges
statically. This is why `changes` is a JSON box.

### `ParamShape` — all 27 fields enumerated

`name`, `kind`, `required`, `nullable`, `values`, `least`, `values_mean`,
`default`, `role`, `unless`, `describes`, `asks`, `asked`, `unless_when`,
`also`, `defines`, `one_of`, `domains`, `domain_from`, `allows`,
`names_the_node`, `a_list_of`, `shaped_like`, `instead_of`, `written_as`,
`refers_to`, `names_at_least`.

The near misses, and why each is not it:

- **`names_the_node`** — the key *is* the node's kind: `{"if": [...]}`. Here the
  key is a field name the author chose; the kind is the same for all of them.
- **`names_at_least`** — how many names one answer holds, for a list of words
  (`values_equal.of`). Cardinality, not shape, and not a map.
- **`also`** — other ways *the same* parameter may be written. Each `Written`
  carries `shaped_like`, so it inherits the wrong meaning above.
- **`domains` / `domain_from`** — a closed set that depends on another answer.
  Nothing to do with nesting.
- **`refers_to` / `allows` / `defines`** — what a *name* points at. They
  describe the key's referent, never a collection.

**No existing field says "several nodes of kind X, each under a name". The
mechanisms are exhausted.**


## Task 4 — the four shipped cards

| card | event | field | operation | field proposed? | field read back? | operation described? |
|---|---|---|---|---|---|---|
| `compost` | `before_loot_draw` | `source` | `value` | **NO** | yes | yes |
| `mom_s_bra` | `before_damage` | `amount` | `cap` | yes | yes | yes |
| `two_of_clubs` | `before_loot_draw` | `count` | `factor` | yes | yes | yes |
| `polycephalus` | `roll_modified` | `value` | `flip` | yes | yes | yes |

**Current declaration status is the same for all four:** the operation is
described (Stage Promise 1); the field name is described only as "text naming
one of the event's values", with no closed set; the container is described only
as "a set of named values". The Constructor represents all four correctly and
draws all four as a JSON textarea.

### `compost` and the field nothing proposes

Asked specifically, because it is the case any derivation has to survive.

`before_loot_draw` is proposed with `count` and nothing else:

```python
proposal = ctx.propose(EventType.BEFORE_LOOT_DRAW,
                       controller=player.player_id, targets=[player],
                       count=count, source=DECK)
```

`source=DECK` binds to `propose`'s own named parameter — `propose(event_type,
*, source=None, controller=None, targets=None, **payload)` — so it becomes
`Event.source`, a top-level field, and **never enters the payload**. What
`compost` writes is the payload key of the same name, read one line later by

```python
source = str(proposal.get("source", DECK))
```

`Event.get` reads the payload only. So `source` is a real, load-bearing part of
this event's contract that:

- appears in **no** `propose` payload,
- appeared in **0** of 105,936 events measured across 30 played games,
- exists only when a replacement has written it.

**A declaration of event fields derived from proposals, or from observed
payloads, would lose `compost` and nothing would say so.** That is the concrete
reason to keep the field name free text — which is also what this stage
proposes, and what keeps it out of scope.

**What would be lost by publishing the container: nothing.** The field name
stays free text, the operations stay the six, the JSON stays byte for byte.
What is gained is that the four cards stop being a textarea.


## Task 5 — classification and the minimal next step

### B — a new element of the language is required

**Why the existing declarations cannot express it:** `a_list_of` means list and
refuses a mapping; `shaped_like` means one node and is already spoken for by
`ability.cost`, and using it here silently produces a form that cannot express
three of the four shipped cards; `A_MAPPING` says only that a mapping is there;
no other `ParamShape` field is about nesting at all.

**The smallest new concept:** one field on `ParamShape`, the map analogue of
`a_list_of` — *this parameter holds several nodes of one described kind, each
under a name the card chooses*. Nothing more. In particular it should **not**
carry which names are allowed: that is the event-fields question, it is
separate, and `compost` shows why it is not derivable.

**Why it belongs in the language model:** because the thing it describes is
already in the engine. `Promise.changes` is a typed field of a stored
dataclass and the applier iterates it; the element kind is published as
`change`; the key kind is published three times as `role=names` text. Every
part of the construction is a fact the engine already holds. The only thing
missing is the sentence that puts them together, and that sentence belongs
where `a_list_of` and `shaped_like` live, beside the two other ways one part
of the language holds another.

### One thing it would deliberately not close

`when` is a **third** shape: `{field: literal}`, checked by `Promise.about`
with `payload.get(key) == value`. It is a map from a name to a bare value, not
to a node. A word for "a map of nodes" does not describe it, and it should not
be stretched to. `when` stays a JSON box after this, and that is the honest
outcome rather than a gap discovered later.

### Recommended next stage

**Stage Promise 3 — declare and read a map of a described kind.** One new
`ParamShape` field; `promise` uses it to say `changes` holds `change`s; the
reader, writer and one control follow. The stage should be scoped so that it
lands the declaration *and* the reader together — Stage 1B measured what
happens when a declaration ships without the reader that honours it: two cards
were silently emptied and the checker passed them.

It should **not** be started until this analysis is accepted, and it should not
be merged with any question about which fields an event has.


## Files that would theoretically change

Named, not touched.

| file | what it would carry |
|---|---|
| `src/fsme/content/vocabulary.py` | the new `ParamShape` field and its docstring |
| `src/fsme/effects/registry.py` | a way for an effect to say it, beside `holding=` |
| `src/fsme/effects/builtin/replacement.py` | `promise` saying `changes` holds `change`s |
| `src/fsme/runtime/vocabulary.py` | publishing it, as `a_list_of` is published |
| `src/fsme/lab/desk/capabilities.py` | publishing it in `_fields` |
| `src/fsme/lab/desk/author.py` | reading and writing a map of nodes |
| `src/fsme/lab/desk/static/author.html` | one control: several named entries, each a node form |
| `tests/` | the map round-trips; the four cards go on meaning what they mean |

Unchanged by anything proposed here: `state/promises.py`, every runtime
execution path, the event list, the triggers, `PRINTED_NUMBERS`, `content/`,
and the format of every card file.
