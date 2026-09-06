# Card Constructor v0.9 — Stage 1: what is only unpublished

Three cases were put in one class by the last analysis: `store`, `group`,
`watch_for`. The claim was that the engine already understands each of them and
only the published model is silent. This tests that claim, one case at a time,
on four questions:

1. does the runtime already understand the construction?
2. does the metadata already describe the concept, in part?
3. can the builder already write correct JSON?
4. where exactly is the information lost?

Analysis only. Nothing was changed. Every answer below was measured — the
doctored vocabularies used to test "what if this were declared" were built in
memory, in the scratchpad, and no file in the repository was touched.

**The claim held for one of the three.** The other two are smaller than a new
concept and larger than a declaration, and one of them fails dangerously if
treated as a declaration.

---

## 1. The table

| | runtime understands | metadata describes | builder writes | lost where | verdict |
|---|---|---|---|---|---|
| **`store`** | yes — any step | in three places, not on effects | **yes, already** | page offers no box; reader refuses | **publication only** |
| **`watch_for`** | yes | `a_list_of` unstated on two answers | only by passing raw JSON through | **the reader** — it keeps the lists raw | publication **+ one reader line** |
| **`group`** | yes | singular only | **yes, already** | model cannot say "several"; page picks one; reader refuses | **new statement**, then reader and page |

---

## 2. `store`

### Runtime

Accepts it on **any** step. `store` is in `_MODIFIER_KEYS` in
`runtime/interpreter.py`, beside `target`, `as`, `optional`, `description`,
`prompt` — read around an effect rather than by it.

### Metadata

Already says three of the four things:

- **what an effect stores.** `EffectShape.stores` — `roll_dice` publishes
  `'dice'`, `reroll` publishes `'dice'`, and `capabilities.py:291` sends it to
  the page. Those two are the only effect shapes that store anything.
- **that a step may store.** All seven control nodes declare a `store`
  answer — `sequence`, `if`, `repeat`, `for_each`, `stop`, `may`, `choose`.
- **how to read one back.** `worked_out.from` — `refers_to='values'`, written
  as *"the name of a value an earlier step stored"*.

What it never says: that an **effect** may store. **0 of 63** published effect
shapes declare a `store` answer.

### Builder

Writes it correctly **today, with no change**. Measured — an author state whose
step carries `store` in its fields produces:

```json
[{"effect": "roll_dice", "sides": 6, "store": "first_die"},
 {"effect": "roll_dice", "sides": 6, "store": "second_die"}]
```

and `check_card` reports no problems. This works because `_without_the_moot`
drops only what another answer settles and what the engine writes itself — a key
the shape does not describe passes straight through.

### Where it is lost

Two places, both author-facing:

- the page offers no box, because nothing declares one;
- the reader refuses at `author.py:1568`.

### What happens if it is declared

Measured, with `store` declared on the two shapes that say they store:

| | shipped | with `store` declared |
|---|---|---|
| readable | 331 | **332** |
| refused | 21 | **20** |
| means the same after a round trip | 331 of 331 | 332 of 332 |
| idempotent | 331 of 331 | 332 of 332 |
| checker clean | 331 of 331 | 332 of 332 |

`the_bloat` opens, and comes back meaning the same thing:

```
was  [{"roll_dice": 6, "store": "first_die"}, …]
once [{"effect": "roll_dice", "store": "first_die", "sides": 6}, …]
```

— the short spelling written long, which reading is allowed to do. **No other
card changes at all.**

### The smallest change

Declare `store` on the shapes whose `stores` is not empty — `roll_dice` and
`reroll` — and nowhere else. Not on all 63: the other 61 store nothing, and a
box asking an author to name a result that does not exist is exactly the thing
the model already warns against, *"an interface offering a box for reading a
name nothing can create."* The fact is already declared as `stores`; the new
answer should be read off it rather than listed a second time.

**Only one card depends on it.** `the_bloat`, twice, both on `roll_dice`.

No new semantics: the runtime's behaviour is unchanged, the card language is
unchanged, and the only new thing in the world is a box.

---

## 3. `watch_for`

### Runtime

Understands it fully. `crystal_ball` and `host_hat` play. `watch_for.effects`
holds ordinary steps and `watch_for.conditions` holds ordinary conditions —
`{"draw_loot": 3}`, `{"dice_equals": 1}`, `{"event_value": {…}}`.

### Metadata

Says everything except what the two lists hold:

```
effects     kind='a list'                                   a_list_of=''
conditions  kind='anything the engine can only judge …'     a_list_of=''
```

Ten answers elsewhere already declare `a_list_of='step'`; four declare
`a_list_of='condition'`. The concept exists and is used; these two answers do
not use it.

### Builder

Writes the right JSON today **only because it never touches it**. The lists
arrive as raw card JSON and are copied through. Hand it author-shaped nodes —
what the page would actually hold if it could edit them — and it writes:

```json
"conditions": [{"id": "dice_equals", "fields": {"value": 1}}]
```

which the checker rejects: *"condition must be a name or an object"*, *"unknown
effect 'id'"*. With `a_list_of` declared, `_written_inside` routes both through
`_written_body`, which already knows `step` and `condition`.

### Where it is lost — and this is the finding

**The reader.** It keeps these two answers exactly as the card wrote them:

```json
{"id": "watch_for",
 "fields": {"event": "after_roll",
            "conditions": [{"dice_equals": 1}],
            "effects": [{"draw_loot": 3}]},
 "groups": {}}
```

Raw card JSON, sitting inside author state where every other step is
`{"id", "fields", "groups"}`. It survives a round trip only because nothing
looks at it, and the page cannot show it because the nodes have no `id`.

The cause is an asymmetry in the reader. `_read_value` handles `a_list_of` and
already knows `STEP` and `CONDITION`. It is called from two places:

- `author.py:1360` — the part reader, for abilities, statics, cards, modes and
  control nodes: **always**.
- `author.py:1721` — the control-node reader: **whenever `a_list_of` is set**.

The **effect** reader has no such call. It stores every non-pointing value raw.
So the two halves disagree: the writer would honour `a_list_of` on an effect,
and the reader would never produce anything for it to honour.

### What happens if it is declared alone

**It silently empties both cards.** Measured, declaring `a_list_of='step'` on
`effects` and `a_list_of='condition'` on `conditions` and nothing else:

```
crystal_ball   was   "conditions": [{"dice_equals": 1}], "effects": [{"draw_loot": 3}]
               once  "conditions": [],                   "effects": []
               twice "effect": "watch_for", "event": "after_roll"      ← both keys gone
```

`host_hat` the same. Both stop meaning what they meant, both stop being
idempotent, **and `check_card` passes the emptied card** — the checker has
nothing to object to, because an empty list is a legal answer.

The walk is unmoved as well: **325 editable before, 325 after**, both cards
still view-only, because the page still sees nodes with no `id`.

So on the round-trip contract the declaration alone scores **330 of 332** where
the shipped tree scores **331 of 331**. It is not a safe one-line change.

### The smallest change

Declare the two lists **and** route the effect reader's values through
`_read_value` the way the control-node reader already does. `_read_value`
needs nothing new. After that the writer and the page's walk both work off
`a_list_of` with no further change.

`watch_for` is the **only** effect in shipped content whose answers hold lists
of objects — 7 uses of `conditions`, 7 of `effects`, and nothing else anywhere.
So the reader change has exactly one subject, and the risk of it is bounded by
that.

`host_hat` would still not be editable afterwards: its inner step chooses its
own target, which is the step-scope class. `crystal_ball` would be.

---

## 4. `group`

### Runtime

Understands it fully. `group` is a published target — *"several things chosen
earlier, together"* — aimable, and `decoy` plays.

### Metadata

Describes the reference concept, in the singular:

```
group.as   role='names'  written_as='FSME writes this one for you'   asked='never'
group.of   role='names'  written_as='the name of something the ability chose'
           refers_to='any'  a_list_of=''  shown='group'  many=false
```

`group.of` says it names **something the ability chose** — one thing. Its real
value in `decoy` is `["mine", "theirs"]`.

### Builder

Writes it correctly **today, with no change**. Measured — given author state
holding three targets, it produces `decoy` exactly:

```json
[{"target_treasure": {"owner": "opponents", "exclude_eternal": true, "as": "theirs"}},
 {"self": {"as": "mine"}},
 {"group": {"of": ["mine", "theirs"], "as": "decoy_pair"}}]
```

identical to the shipped card, checker clean. The card language, the loader and
the runtime all accept it. Only the reader refuses, at `author.py:1876`.

### Where it is lost

Three places, and the first is the one that matters:

- **The model has no way to say it.** Across every published effect, node,
  target and condition shape, **not one parameter combines `refers_to` with
  `a_list_of`.** The two fields that might look like the answer are not:
  `a_list_of` means *a list of nodes of a named kind* — the builder routes it to
  `_written_body`, which builds nodes, not names — and the published `many` is
  derived as `kind == 'a list' and bool(values)`, meaning a multi-select of
  literal values. Neither says "several of the things this refers to".
- **The page picks one.** `groupHtml` renders a single `<select>`, so
  `groups[of]` holds one target.
- **The writer and reader carry one.** `_given` writes `written[key] = name`,
  one name per answer; `_as_chosen` reads one binding per answer.

### Verdict

This is **not publication only**. Everything below the author — language,
loader, checker, runtime, builder — already supports it, which is why `decoy`
ships and plays. What is missing is a sentence the model cannot currently say,
and then a reader and a page that can hold two names where they hold one.

It is a small new concept, not a large one, and it is worth naming rather than
smuggling in: reusing `a_list_of` for it would make one field mean two things —
a list of nodes here, a list of names there — and the builder branches on that
field. That is how a fact comes to be enforced in one place and declared in
another.

**One card depends on it**: `decoy`.

There is a second answer of the same shape already in the tree, which is worth
knowing before choosing a spelling: `values_equal.of` carries
`refers_to='values'`, `a_list_of=''`, and holds `["first_die", "second_die"]` in
`the_bloat`. It is not refused today — the group refusal deliberately excludes
`refers_to == 'values'` — but it is the same "several names" idea pointing at
stored values instead of chosen things. Whatever is said about `group.of`
should be able to say this too.

---

## 5. What this changes about the last analysis

The previous document called all three declaration gaps. One is:

| | previous | measured |
|---|---|---|
| `store` | declaration gap | **confirmed** — publication only, one card, nothing else moves |
| `watch_for` | declaration gap | publication **plus** a reader that reads what it declared; declaration alone silently empties two cards |
| `group` | declaration gap | **a new statement in the model** — nothing published can say "several of what this refers to" |

The count of refused cards is unaffected by this correction — 21 stands, and so
does the split of 19 implementation and 2 declaration. What changes is the cost
of the second number.

---

## 6. Suggested order within Stage 1

1. **`store`.** Publication only, proven safe by measurement, one card, no
   reader change, no page change. It is also the honest proof that a
   declaration gap can be closed by a declaration.
2. **`watch_for`.** Declaration plus the reader line, together in one change —
   never the declaration on its own, and the round-trip contract must be run
   over it, because the checker will not catch the failure.
3. **`group`.** Only after a decision about how the model says "several", taken
   with `values_equal.of` in view. Not a declaration; do not do it as one.

Each stops on its own, and each is worth its own gate.

---

## 7. What remains intentionally refused

Unchanged by this analysis. `promise` and its four cards stay view-only until
the event-payload question is answered, and the nineteen implementation-gap
cards stay refused until the stages that address them. Nothing here brings the
step-scope question forward, and nothing here should be taken as starting it.
