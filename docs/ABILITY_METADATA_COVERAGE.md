# Does the engine tell the whole truth about the cards it can run?

A coverage audit of the ability metadata exposed at `8563871`, measured by
walking all 1014 shipped cards the way the engine reads them and asking the
catalogue, at every key, whether it can describe what is written.

The short answer: **structurally, yes.** Of every key those cards write at
every level, the metadata now describes all of them, and no value falls outside
a domain it declares. One thing is wrong, in one way, in 13 cards — and it is
one missing concept rather than thirteen missing facts.

---

## The measurement

| Question | Answer |
| --- | ---: |
| Keys written by shipped cards that the metadata does not mention | **0** |
| Values written outside a domain the metadata declares | **0** |
| Values whose kind the metadata gets wrong | **15**, in **13 cards** |

Every one of the fifteen is the same thing: a card writing *a way of working a
value out* where the metadata says a number.

```
loot_deck-…-ii_the_high_priestess   deal_damage.amount = {"from": "dice"}
treasure_deck-…-bum_bo              add_counter.amount = {"from": …}
loot_deck-…-viii_justice            draw_loot.count    = {"count": "loot", "of": …}
starting_items-…-forever_alone      transfer_coins.source_player = {"player_of": …}
```

The metadata says `deal_damage.amount` is a whole number. It is — or it is a
dynamic head that produces one, and `_resolve_params` resolves **every**
parameter of every effect that is not held literally. So the truthful statement
is "a whole number, or a way of working one out", and the shape system has no
way to say *or*.

---

## A. Coverage summary

| Area | Engine knowledge | Metadata coverage | Missing |
| --- | --- | --- | --- |
| **trigger** | 66 events; 14 of them self-scoped | 66 values, each with the scope it defaults to | — |
| **scope** | `in_scope` reads 3 values; default derived from the trigger | 3 values, and the derivation published per trigger | Nothing for the metadata. The *renderer* must still use it |
| **zone** | `getattr(state, ability.zone)`; 12 zones exist | 12 values, and now refused at load time | — |
| **optional / replacement** | booleans on `Ability` | `true or false`, role `switch` | The **checker** does not read the kind: `optional: "yes"` still loads |
| **cost** | `KINDS = (tap, coins, discard, counters, hp)`; unknown keys refused at payment time | a node shape of its own, 5 keys, correct kinds | Nothing descends into it — `cost: {"spaghetti": 1}` still loads. `counters` is a union. `hp` must leave the payer alive; no floor says so |
| **conditions** | evaluated before the effects; `and`/`or`/`not` nest arbitrarily | a body of condition nodes | `and`/`or`/`not` still have no `ConditionShape`, so a body of conditions has no combinator to hold |
| **targets** | a list of target specs bound by `as` | a body of target nodes | — |
| **effects** | a list of effect or control nodes | a body of effect nodes | The list may hold a control node; the metadata calls it a list of effects |
| **static rules** | `stat` domain depends on scope *and* on the card being a monster; `forbids` from `ACTIONS` | 7 fields, correct kinds, `forbids` and `scope` domains, `conditions` a body | `stat` carries no domain, deliberately — the layer cannot say "it depends" |
| **control structures** | 7 nodes, `CONTROL_KEYS` + `CONTROL_BODIES` | all 7 published with bodies, plus `mode`; every own key drawable | Head keys modelled as parameters; six undeclared alias pairs; modifier keys accepted everywhere and read only somewhere |
| **more than one ability** | `abilities_for`, `ability_index` | n/a — a list, not a field | Ordering is meaningful and nothing says so |

### What the shipped content needs, and whether it is described

329 of the 1014 cards carry rules.

| Feature | cards | share | described? |
| --- | ---: | ---: | --- |
| trigger | 314 | 95.4% | yes, with its default scope |
| effects | 314 | 95.4% | yes — a body of effect nodes |
| scope | 170 | 51.7% | yes — 3 values |
| targets | 83 | 25.2% | yes — a body of target nodes |
| conditions | 76 | 23.1% | yes — a body of condition nodes |
| `if` | 47 | 14.3% | yes — a node shape with bodies |
| more than one ability | 38 | 11.6% | n/a — a list |
| statics | 29 | 8.8% | yes — a node shape of its own |
| `may` | 26 | 7.9% | yes |
| replacement | 23 | 7.0% | yes — a switch |
| `choose` | 21 | 6.4% | yes, with `mode` |
| **a value worked out at play time** | **13** | **4.0%** | **no — declared as a whole number** |
| cost | 12 | 3.6% | yes — a node shape of its own |
| `for_each` | 1 | 0.3% | yes |
| zone | 1 | 0.3% | yes — 12 values |

---

## B. Missing metadata inventory

### Critical — changes what a card means

**1. A value worked out at play time has no way to be described.**
*Location:* `effect_executor.py::_resolve_params`, `DYNAMIC_HEADS`.
*Affects:* 13 cards (4.0% of carded content); *potentially every one of the
215 effect parameters*, because the executor resolves them all.
*Why critical:* a renderer built on this metadata would draw a number box for
`deal_damage.amount` and an author could never write "damage equal to the
roll" — a card whose printed text is common in Four Souls. Worse, the metadata
*claims* the parameter is a number, so anything trusting it would refuse a
card the engine runs today.
*Recommended representation:* the shape system needs a union — see §C.

**2. `store` writes a name and nothing says so.**
*Location:* `_MODIFIER_KEYS`, `effect_executor.py` (`op.store`), read back by
`values_equal.of` (`refers_to: values`).
*Affects:* 1 shipped card, but it is the only way to compare a value across
steps.
*Why critical:* the metadata describes the *reading* end (`values_equal.of`
names a stored value) and not the *writing* end. A renderer can offer a box
asking for a name that nothing in the interface can create.
*Recommended representation:* the inverse of `refers_to` — a parameter that
*defines* a name others may point at, alongside the `as`/`BY_BINDING` pair
which already models exactly this for targets.

### Important — blocks authoring, or lets a wrong card through

**3. Nothing checks what is written inside a cost.**
`cost: {"spaghetti": 1}` and `cost: {"coins": "two"}` both load. The `cost`
node shape now describes the truth; `_one_node` checks a node's *keys* and its
*string domains*, never its kinds and never a nested shape. Measured on all
four cases: only `zone`, `scope` and `forbids` are caught, and those only
because they are string domains.

**4. Node field kinds are declared and unread.** `optional: "yes"`,
`replacement: "true"`, a static `amount: "lots"`, `cost: 3` — all accepted.
Two list-ness rules exist (`'effects' must be a list`, `conditions must be a
list`) as hand-written checks beside the shape rather than read from it, which
is the same duplication this project has removed five times elsewhere.

**5. `and` / `or` / `not` still have no shape.** `ability.conditions` is now
declared a body of condition nodes, and the only condition nodes the catalogue
publishes are the 41 leaves. A body of conditions that cannot hold a
combinator is a body that can hold exactly one test.

**6. `static.stat` has a domain the metadata cannot state.** The validator
knows it — `_static_stat` picks `MONSTER_STATS` or `STATS` from the scope and
the card type, and the constant naming the problem (`STATIC_STAT_BY_SCOPE`) is
already in the file. The metadata publishes no domain rather than a wrong one,
which is right, and leaves `stat` looking like free text, which is not.

**7. An ability's `effects` may hold a control node.** Declared
`a_list_of: effect`. True of most entries and wrong for the 47 cards with an
`if`. The list is really "effect nodes or control nodes" — another union, and
a smaller one than #1.

### Minor — a renderer would work, a person would be misled

**8. Six control heads are two spellings of one question, undeclared.**
`if`/`conditions`, `may`/`effects`, `choose`/`modes`, `repeat`/`times`,
`for_each`/`of`, `sequence`/`effects`. `instead_of` exists and says exactly
this; none of the twelve uses it.

**9. A control node's head is not a parameter.** `{"if": [...]}` names the node
*and* carries its conditions. The metadata models the head as a field of the
node it names, which is truthful about the JSON and misleading about the shape.
`stop` shows it plainly: `stop.stop` is published as a switch, and the
interpreter never reads the value.

**10. The six modifier keys are accepted everywhere and read somewhere.**
`target`, `as`, `optional`, `description`, `prompt`, `store` appear on all
eight structures. `store` and `target` are read on any node; `prompt` only by
`may` and `choose`; `optional` on a control node is read by nothing at all —
`Ability.from_data` is the only reader. The metadata says "accepted", which is
true, and cannot say "and does anything".

**11. 23 parameters share a name with a dynamic head.** `count` is a head in
`_resolve_params` and an ordinary parameter on 12 targets and 7 effects. No
ambiguity at runtime — a head is a mapping, a count is a number — and none the
metadata can express either, once #1 is solved.

**12. Ability order is meaningful and unsaid.** `ability_index` indexes a
card's *activated* abilities; three shipped cards have two.

---

## C. Shape system evaluation

> **Is the current metadata model sufficient for building the next generation
> Author UI?**

**For the structure of a card: yes.** `a_list_of` and `shaped_like` were the
two missing pieces and they are enough to describe every nesting the language
has. 83 ability-layer parameters, all of them landing somewhere a renderer can
use: 49 form, 17 body, 10 nested, 7 given. All eight structures have every own
key drawable. Nothing about an ability, a static or a control node is opaque
any more.

**For the values inside it: not quite.** Four concepts are missing, in
descending order of weight.

### 1. Union — needed

`amount` is *a number, or a way of working one out*. `cost.counters` is *a
number, or `{counter, amount}`*. `ability.effects` is *a list of effect nodes,
or control nodes*. Three different unions, one missing idea, and the first of
them is the only critical finding in this audit.

This is not "kind should be a list of kinds". A union of a value and a
*derivation* is a different question to ask — "give me a number" versus "tell
me where to get one" — and the roles already model that difference elsewhere:
`whom` is exactly "not a value, a way of naming one".

### 2. Context-dependent domain — needed, twice

`static.stat` depends on `static.scope` and on the card's type.
`ability.scope`'s *default* depends on `ability.trigger` — already solved, and
solved by publishing the derivation rather than by teaching the shape system to
depend. The `stat` case cannot be solved that way: the dependency is on another
answer in the same node, not on a fixed table.

Both are the same shape of problem, and `unless` / `unless_when` is the
precedent — a fact about one parameter that names another and the values that
matter.

### 3. References between nodes — needed once, and half-built

`as` defines a name; `chooser`, `of`, `exclude` read it; `written_as` and
`refers_to` describe the reading. `store` defines a name; `values_equal.of`
reads it; nothing describes the writing. One concept, missing one direction.

### 4. Recursive tree shapes — **not needed**

Already expressible. `if.then` is `a_list_of: effect`, and an effect may be an
`if` whose `then` is `a_list_of: effect`. The recursion is in the data, not in
the vocabulary, which is what makes it free.

### Not needed: conditional shapes

Nothing in the engine changes a node's *shape* based on another value. Only
domains and kinds vary, which are #1 and #2.

### The role system

Nine roles, and one of them is carrying four jobs: `names` covers 33 of the 83
ability-layer parameters, and inside it sit prose (`description`), a question
put to a player (`prompt`), a name defined for later steps (`store`), a name
the metadata cannot enumerate (`per_counter`), and a domain the metadata cannot
state (`stat`). Three of those five are misleading rather than wrong:

- **`stat` as `names`** says free text and means a closed choice.
- **`store` as `names`** says free text and means a definition.
- **`cost.counters` as `open`** says "any value" and means a two-way union.

`amount`, `which`, `switch`, `body`, `nested` and `whom` all fit their ability
-layer members exactly. No new role is needed for *structure*; what is needed
is the union and dependency vocabulary above, after which `stat` becomes a
`which` and `counters` becomes what it is.

---

## D. Recommended next milestone

Not the ability renderer. One more metadata pass first, because building a
renderer on a layer that mistypes 4% of shipped cards would bake the mistake
into the UI, and the missing concept is small.

**Milestone: say what a value may be, not only what it usually is.**

1. **Union of a value and a derivation.** Declare, per parameter, that it also
   accepts a dynamic head. It is true of every non-literal effect parameter,
   so it is one derivation and not 215 declarations — the same shape as
   `parameters_of`. This closes the only critical finding and unblocks 14% of
   carded content for any future renderer.
2. **`and` / `or` / `not` get a `ConditionShape`** whose one parameter is
   `a_list_of: condition`. Without it a body of conditions holds one test, and
   `ability.conditions` — 23.1% of carded cards — is only half described.
3. **Have the checker read the kinds the metadata now declares.** The layer
   has got ahead of the validator: `optional: "yes"` and
   `cost: {"spaghetti": 1}` load today. Descending into a `shaped_like` field
   and checking a declared kind are two small rules that delete two
   hand-written ones.
4. **Declare the six control-head alias pairs** with `instead_of`. The
   mechanism exists; twelve declarations use it.
5. **Name the writing end of a reference**, so `store` and `values_equal.of`
   describe one relationship from both sides.

`static.stat`'s dependent domain and the "what a modifier key actually does per
node" question are worth deciding on but not worth blocking on: one affects 29
cards and fails safely as text, the other affects nothing a card can get wrong.

**After that**, the ability renderer, in the order the earlier plan set out —
scope first, because it is one control over three published values and it is
the difference between a card that does what its text says and one that does
not.

---

## Verdict

> **Can the current capability metadata truthfully describe real FSME cards?**

It describes their **structure** completely: not one key in 1014 cards is
unknown to it, and not one value falls outside a domain it declares. That was
the question this phase set out to answer and the answer is yes.

It does not yet describe their **values** completely. In 13 cards it says
"a number" where the card says "work one out", and it is silent about a name
one step defines for another to read. Both are one idea — *this may be a value,
or a way of getting one* — and until that idea exists, the engine tells the
truth about the shape of every card it can run and slightly overstates what
goes in the boxes.
