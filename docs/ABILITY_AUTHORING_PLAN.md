# Authoring complete abilities

How FSME exposes the whole card ability model to authors without losing
anything the engine can already do.

The renderer problem is solved. Effects, conditions and targets are described
by metadata, drawn by one generic renderer, and 60 of 63 effects, 41 of 41
conditions and 46 of 46 targets can be built in the form, validated and played.
What remains is not a parameter problem — it is that the layer *above* the
effects has never been described at all.

This document says what that description should look like. It proposes no new
DSL, no second editor architecture and no change to gameplay rules. Everything
below is the existing pipeline — runtime knowledge → capability metadata →
generic renderer → card DSL — carried one level up.

Measured at `d43786c` against 1014 shipped cards.

---

## A. Current state

### What the form can make today

One card, one ability, made of:

- a **trigger**, chosen from all 66;
- a list of **effects**, each with its parameters drawn from metadata by role;
- an **aim** per effect, over all 46 targets, with each target's own
  parameters drawn recursively;
- **`whom` pickers** for the five effect parameters that name a player;
- **one `if` branch** per step, with one condition and a `then` / `else` body;
- **structures** (`promise.changes`, `watch_for.effects`) in a parsed editor.

`build_card` writes exactly three ability keys: `trigger`, `effects`,
`targets`. Nothing else on `Ability` is reachable, and `statics` is never
written at all.

### What that costs

**The form can reproduce 101 of the 329 shipped cards that carry rules — 31%.**

### Where the engine already knows more than the metadata says

`engine_vocabulary()` builds `NodeShape`s for `ability`, `static` and all
seven control nodes. Two things stop them being usable:

1. **`capabilities.catalogue()` never returns them.** It hands the page
   `kinds, triggers, effects, conditions, targets` and nothing else. Every
   blocker in this document is behind that one omission.
2. **Every node-shape parameter is typed `text`.** `runtime/vocabulary.py`
   builds them with `ParamShape(field.name, TEXT)` regardless of what the
   field holds. `optional` and `replacement` are booleans, `cost` is a mapping
   with five known keys, `conditions` / `targets` / `effects` are lists of
   nodes, a static's `amount` is a number. Only `scope` carries a domain.

Exposing the shapes as they stand would give the renderer *wrong* metadata,
not thin metadata. The shapes have to describe what they hold first.

---

## B. Missing ability-layer capabilities

| Feature | Engine support | Metadata support | UI support | Difficulty |
| --- | --- | --- | --- | --- |
| `ability.scope` | Full — `in_scope`, `ability_scope`, `ABILITY_SCOPES` | Domain only, on a shape the page never sees | None | **Low** |
| `ability.conditions` | Full — evaluated before the effects, `counting_conditions` splits out `nth_time_this_turn` | Typed `text`; the condition vocabulary itself is complete | None | **Low** |
| `ability.replacement` | Full — `_apply_replacements`, `MAX_REPLACEMENT_DEPTH` | Typed `text` (it is a bool) | None | **Low** |
| `ability.cost` | Full — `rules/costs.py`, `KINDS = (tap, coins, discard, counters, hp)`, refuses unknown keys | Typed `text` (it is a five-key mapping) | None | **Medium** |
| `ability.optional` | Full | Typed `text` (it is a bool) | None | **Low** |
| `ability.zone` | Full — an ability outside play is only looked at if it names its zone | Typed `text`, no domain (12 zones exist) | None | **Low** |
| `ability.description` | Cosmetic | Typed `text` | None | **Low** |
| More than one ability | Full — `abilities_for`, `ability_index` | n/a (a list, not a field) | None — `build_card` writes `[ability]` | **Medium** |
| Statics | Full — `rules/statics.py`, `rules/restrictions.py` | `NodeShape` exists, all `text`; `stat` domain depends on `scope` | None | **Medium** |
| `and` / `or` / `not` | Full — `evaluate`, `{"of": [...]}`, validator recurses | **None** — no `ConditionShape`, so never in the catalogue | None | **Low** |
| `may` | Full — `_expand_may`, binds the answer like a target | `NodeShape` exists, all `text` | None — silently dropped by the builder | **Medium** |
| `choose` | Full — `_expand_choose`, modes are `{description, effects}` | `NodeShape` exists, all `text` | None — silently dropped | **High** |
| `for_each` | Full — `_expand_for_each`, `of` is a target spec | `NodeShape` exists, all `text` | None — silently dropped | **Medium** |
| `repeat` | Full — `_expand_repeat` | `NodeShape` exists, all `text` | None — silently dropped | **Medium** |
| `sequence` | Full | `NodeShape` exists | None — silently dropped | **Low** |
| `stop` | Full — a leaf, no body | `NodeShape` exists | None — silently dropped | **Very low** |
| Effect → target kind | Enforced by 33 handler guards | **None** | Picker offers all 42 aims for every effect | **Medium** |
| Dynamic heads (`from`, `count`, `from_event`, `last_result`) | Full — `_resolve_params`; **the builder already passes them through** | None | No control writes one | **Medium** |
| `store` | Full — a `_MODIFIER_KEYS` key on any node | None | None | **Medium** |
| `Static.forbids` domain | Enforced by `!=` against `ACTIONS` | None | Text box | **Very low** |
| `cost` key domain | Enforced — "unknown cost '…'" | None | n/a | **Very low** |

---

## 1. Ability metadata model

### What an ability should expose

The same eleven facts every effect parameter already exposes, per field:
`kind`, `role`, `values`, `least`, `required`, `default`, `describes`,
`unless`, `unless_when`, `refers_to`, `written_as`. Nothing new is needed for
the leaf fields:

| Ability field | kind | role | domain |
| --- | --- | --- | --- |
| `trigger` | text | `which` | all 66 triggers |
| `scope` | text | `which` | `self`, `controller`, `any` |
| `optional` | true or false | `switch` | — |
| `replacement` | true or false | `switch` | — |
| `zone` | text | `which` | the 12 zones on `GameState` |
| `description` | text | `names` | — |

Three fields are *not* leaves, and they are where the model has to grow.

### Growth one: bodies

`conditions`, `targets` and `effects` are lists of nodes. So are `if.then`,
`may.effects`, `choose.modes`. The metadata calls all of these `structure`
today, and `structure` means "opaque nested data, edit it as JSON" — which is
the right answer for `promise.changes` and the wrong answer here, because the
editor already knows how to draw a list of effects and a list of conditions.

A body is not opaque; what is missing is *what kind of list it is*.

**Proposal: `ParamShape.a_list_of: str`**, over a plain-data vocabulary
`LISTS = ("effects", "conditions", "targets", "modes")`.

- `role` becomes `body` (an eighth role) when it is set.
- The renderer gains one component per member of `LISTS`. It already has two
  of the four: the step list is a list of effects, and the branch's condition
  control is one condition.
- Nesting is then free: a `then` body holds effects, an effect may be an `if`
  whose `then` body holds effects.

`structure` stays exactly as it is, for data the editor genuinely cannot draw.
The distinction is the point: **`structure` means "we do not know what is in
here", `body` means "we do, and it is more of the same".**

### Growth two: named sub-shapes

`cost` is a mapping with five known keys and known kinds:

| key | kind | notes |
| --- | --- | --- |
| `tap` | true or false | the default when nothing is written |
| `coins` | a whole number | |
| `discard` | a whole number | loot cards |
| `counters` | a whole number, or `{counter, amount}` | defaults to the `charge` counter |
| `hp` | a whole number | must leave the payer alive |

That is a `NodeShape`, not a structure. **Proposal:
`ParamShape.shaped_like: str`**, naming another node shape. The renderer draws
a nested group with the same field renderer it uses everywhere.

This also gives `choose`'s modes a home: a mode is
`{description: text, effects: a list of effects}` — a node shape named `mode`,
referenced by `choose.modes` as `a_list_of: "modes"`.

### Should ability metadata reuse the parameter role system?

**Yes, and it must.** Three reasons, in order of weight:

1. **The renderer is the asset.** It reads `shown`, then `role`, and draws
   from `choices`, `many`, `least`, `required`, `unless`, `default`. An
   ability's `scope` is a `which` with three values; `optional` is a `switch`.
   Those are drawn correctly today by code that exists. A second vocabulary
   would mean a second renderer, and a second renderer is the thing this whole
   line of work removed.
2. **The audit's findings were role findings.** `required` visible, `unless`
   respected, a domain rendered as a choice — every one of them applies to an
   ability field as much as to an effect parameter, and re-earning them in a
   separate ability editor is re-earning them wrong.
3. **The roles already cover it.** Seven roles fit every leaf field.
   Only the two container ideas above are genuinely new, and both are
   descriptions of *shape*, not of *question* — `a_list_of` and `shaped_like`
   sit beside `refers_to` and `written_as`, which are the same kind of fact.

### Where the facts should come from

`_node_shapes()` derives ability and static fields from the dataclasses, and
that property is worth keeping: "adding a field to the language widens this the
moment it exists". So:

- **Kind comes from the annotation**, exactly as `parameters_of()` already
  derives an effect's kinds from its handler signature — `_KINDS` maps
  `int → a whole number`, `str → text`, `bool → true or false`. Extend it with
  `tuple[Any, ...] → a list` and `Mapping[str, Any] → a set of named values`.
  This is a derivation, not a table.
- **Everything the annotation cannot say is declared beside the code that
  enforces it** — the project's existing rule, applied five times already
  (`DECKS`, `POSITIONS`, `ABILITY_SCOPES`, `STATS`, `CONTROL_BODIES`). The
  declarations needed: `zone` domain from `GameState`'s zone fields,
  `forbids` domain from `restrictions.ACTIONS`, `cost` key domain from
  `costs.KINDS`, `a_list_of` per body from `CONTROL_BODIES`' neighbours, and
  the `describes` words.

---

## 2. Scope

### The evidence

Of the 25 triggers used by shipped content:

- **two** rely on the unwritten default (`on_activate` 103 abilities,
  `on_play` 73) — both self-scoped triggers, both correct;
- **every other trigger has cards that write scope explicitly**, and 18 of
  them write a scope that *disagrees* with the default.

| trigger | engine default | what real cards write |
| --- | --- | --- |
| `on_activate` | self | 103 unwritten |
| `on_play` | self | 73 unwritten |
| `monster_killed` | any | self ×36, any ×3 |
| `turn_end` | any | controller ×16 |
| `damage_dealt` | any | self ×10, any ×4 |
| `before_damage` | any | self ×8, controller ×4 |
| `after_damage` | any | controller ×8, self ×7 |

So the silence in the form is not merely risky — it is the opposite of what
every hand-written card does. A card built as "when you take damage, gain 1¢"
comes out as `trigger: damage_dealt` with no scope, defaults to `any`, fires on
damage to anybody at the table, and validates clean.

### Where scope should live

**Where it is.** `Ability.scope`, defaulting to `None`, resolved by
`ability_scope()` from `SELF_SCOPED_TRIGGERS`. Do not move it, do not make it
mandatory in the DSL, and do not change the default: 176 shipped abilities
depend on it and are all correct, and content written by hand must keep
loading.

### How it should be validated

**Not by a new error.** Requiring `scope` in the validator would refuse 176
correct cards. Adding a warning severity to a checker that has never had one
is a larger change than the problem justifies, and a warning nobody must act
on is a warning nobody reads.

The right fix is upstream of validation: **make it impossible for the form to
produce a card whose scope nobody chose.** The metadata already has the
mechanism — `_fields` emits `otherwise`, the effect's own default, and the page
shows it as the placeholder. Scope needs the same thing, with one difference:
its default depends on the trigger.

**Proposal: expose the default with the trigger, not with the scope.**
`catalogue()["triggers"]` already lists all 66; give each entry a `scope` field
holding what `ability_scope()` would return for an ability with no scope and
that trigger. The metadata stays a statement of engine knowledge — this *is*
`SELF_SCOPED_TRIGGERS`, published rather than hidden — and the renderer gains a
rule it can apply generically: a parameter whose default depends on a sibling
reads that sibling's entry.

The general shape of that rule (`ParamShape.default_from: str`, naming the
sibling whose catalogue entry carries the default) is worth defining once,
because scope is not the only dependent fact in the engine: `Static.stat`'s
domain depends on `Static.scope` in exactly the same way, and the validator
already carries a constant named `STATIC_STAT_BY_SCOPE` saying so.

### How the UI should display it

Three named choices in card language, never a blank:

- *only when it is about this card* (`self`)
- *only when it is about the player holding it* (`controller`)
- *whenever it happens to anyone* (`any`)

Pre-selected to what the engine would do for the chosen trigger, and re-read
when the trigger changes — the same mechanism `unless` already uses to redraw
a form when the answer it depends on changes.

### How missing scope should be handled

It should not be reachable from the form. Everywhere else — a hand-written
card, a card imported from a file — the current default stands unchanged.

---

## 3. Conditions

### The limitation is one missing shape

`and`, `or` and `not` are fully implemented (`ConditionEvaluator.evaluate`),
normalised (`{"not": [...]}` → `("not", {"of": (...)})`), and already walked
recursively by the validator. They are absent from the catalogue for exactly
one reason: they have no `ConditionShape`, so `_conditions()` skips them.

### Should conditions use the same structure renderer?

They should use the **body** renderer proposed in §1, not the structure one. A
condition list is a list of nodes the editor knows how to draw — it draws one
of them today, in the branch. The three combinators become:

```
ConditionShape("and", params={"of": ParamShape("of", A_LIST, a_list_of="conditions")})
ConditionShape("or",  ...)   # same shape, different meaning
ConditionShape("not", ...)
```

### How nested conditions should be represented

As they are in the DSL, and drawn as they read:

```
if  ┌ all of ─────────────────┐
    │ the player is alive     │
    │ ┌ any of ─────────────┐ │
    │ │ the roll is 6       │ │
    │ │ the player has 3¢   │ │
    │ └─────────────────────┘ │
    └─────────────────────────┘
```

One component — "a list of conditions, joined by *and* / *or* / *none of*" —
used in three places: an ability's `conditions`, a branch's `if`, and inside
another combinator. Depth is not special-cased; it is the same component
inside itself, which is what makes it worth building once.

### How validation should work

It already does. `_check_condition_nodes` recurses through `_BOOLEAN_NAMES`,
and `evaluate` handles arbitrary depth. The only new validation worth adding is
the one this project keeps rediscovering: a combinator whose `of` is empty is
a condition that quietly answers *true* (`and`, `not`) or *false* (`or`), which
reads exactly like one that works — the same class of mistake as the empty
control branch already refused.

---

## 4. Multiple abilities

### Should the card editor support an ability list?

Yes. 38 shipped cards need it, and 15 more have statics and no ability at all,
so "a card is one ability" is not a simplification the model can keep.

### How abilities should be added and removed

The card editor becomes a list of ability panels over the same shared card
fields (name, kind, printed text, numbers). Each panel is the editor that
exists today plus its ability-level fields. Add and remove are per panel.

`build_card` changes from `card["abilities"] = [ability]` to a list, and
`_ability` from one description to many. The `aimed` collection that binds
targets must become **per ability**, not per card: `_pick_out` names groups
`chosen_1`, `chosen_2`, and two abilities must not share a numbering, because
`targets` is an ability-level key and a name bound in one ability does not
exist in another.

### How ordering should work

**Order is meaningful and must be author-visible.** `abilities_for(trigger)`
preserves file order, and an activation command carries `ability_index` — the
position among the card's *activated* abilities, not among all of them. So:

- reordering two `on_activate` abilities changes which one a saved command
  activates (3 shipped cards have more than one);
- reordering an activated ability past a triggered one does not;
- for triggered abilities, order decides only the sequence in which two
  abilities of the same card react to one event.

The editor should therefore offer explicit up/down movement rather than
implicit ordering, and should not renumber anything on its own.

### How shared card data interacts with abilities

Card-level data (id, name, type, expansion, printed text, `health`, `attack`,
`cost`, `roll`) stays where it is: it belongs to the card, not to any ability.
The only coupling worth designing for is the **printed text**, which is one
sentence describing what several abilities do together — it stays a single
card-level field, and the editor should not try to derive it from the
abilities or attach a piece of it to each.

---

## 5. Statics

### Are statics just another ability type?

**No.** A static has no trigger, no effects, never reaches the stack and never
resolves. `Static` shares exactly two fields with `Ability` — `scope`, with a
*different* domain (6 values against 3), and `conditions`, with the same
meaning. Modelling a static as an ability with an empty trigger would put a
falsehood into the metadata and give the editor a panel whose fields are mostly
disabled.

### Should they share metadata?

They share the **model**, not the shape: the same `NodeShape`, the same
`ParamShape` fields, the same seven roles, the same renderer. What they do not
share is a node type.

| Static field | kind | role | domain |
| --- | --- | --- | --- |
| `stat` | text | `which` | **depends on `scope`** — `MONSTER_STATS` (2) when the scope reaches monsters, `STATS` (8) otherwise |
| `amount` | a whole number | `amount` | — |
| `forbids` | text | `which` | `restrictions.ACTIONS` — 4 values, currently undeclared |
| `per_counter` | text | `names` | open |
| `scope` | text | `which` | `STATIC_SCOPES` — 6 values |
| `conditions` | a list | `body` | `a_list_of: "conditions"` |
| `description` | text | `names` | — |

### What is different about the authoring model

Three things, and all three are reasons to keep it a separate node type:

1. **A static is a sentence about a number, not about a moment.** The editor's
   whole vocabulary — "when does it happen", "what happens" — does not apply.
   The question a static asks is "what does this card change, for whom, while
   it is in play".
2. **`stat` has a dependent domain.** The list of stats an author may pick
   changes with the scope they picked, and again with whether the card is a
   monster. This is the same dependent-metadata problem as scope's default,
   and it is the second reason to solve that problem generically rather than
   once for scope.
3. **`forbids` is an alternative to `stat`, not a companion.** A static either
   changes a number or forbids an action. That is `unless` — the mechanism
   already in the metadata — applied to a pair the engine reads exclusively.

---

## 6. Control structures, classified

### Simple future UI additions

Buildable with the body component of §1 and nothing else.

| Node | What it needs | Notes |
| --- | --- | --- |
| `stop` | Nothing — a leaf | Cheapest item in this document. Its absence is accidental |
| `sequence` | One body | Rarely useful; the effect list is already a sequence |
| `may` | One body, plus `prompt` (text) | 26 cards. The `as` key is engine plumbing — `written_as: BY_BINDING`, exactly like a target's |
| `repeat` | One body, plus a number | The number should accept a dynamic head, which is why this waits on §D phase 3 |

### Structures requiring a visual tree editor

| Node | Why |
| --- | --- |
| `for_each` | A body *plus a target picker* — the target control exists, but the node is the first place a target is chosen for something other than an effect's aim |
| `choose` | A list of modes, each a description and a body. Two levels of list, and the only node needing a sub-shape (`mode`) as well as a body |
| Nested conditions | One component inside itself; see §3 |

### Features requiring DSL changes

**None.** Every control node is already implemented, validated and
interpreted; `CONTROL_KEYS` and `CONTROL_BODIES` describe them; the checker
walks into them. The gap is entirely in `capabilities.catalogue()`,
`author.py::_effects` and the page.

Two items elsewhere in this document do brush against the DSL, and neither is
a control structure:

- **Dynamic heads** need no DSL change either — `_written_fields` already
  passes a mapping through unaltered, and `{"amount": {"from": "dice"}}`
  builds and validates today. What is missing is a control.
- **`store`** is a `_MODIFIER_KEYS` key accepted on any node. Also no DSL
  change; also missing a control, and missing a reader — `values_equal.of`
  asks for a stored name in a text box because there is nothing to pick from.

---

## C. Proposed metadata model

### New plain data

```
LISTS = ("effects", "conditions", "targets", "modes")
```

### New `ParamShape` fields

| Field | Meaning | Set by |
| --- | --- | --- |
| `a_list_of: str` | This parameter holds a list of nodes of a named kind. Implies `role = body` | Declared beside the node that reads it — `CONTROL_BODIES` is already the place |
| `shaped_like: str` | This parameter holds a node described by another `NodeShape` | Declared beside the shape it names |
| `default_from: str` | The sibling whose catalogue entry carries this parameter's default | Declared where the derivation lives (`ability_scope`) |

Each is a fact about *shape*, sitting beside `refers_to` and `written_as`,
which are facts of the same kind. None is a new question type; the eighth role
(`body`) is added because a body is drawn by a component, not by a control.

### New node shapes

| Shape | Fields | Referenced by |
| --- | --- | --- |
| `cost` | `tap`, `coins`, `discard`, `counters`, `hp` — from `costs.KINDS` | `ability.cost` via `shaped_like` |
| `mode` | `description`, `effects` | `choose.modes` via `a_list_of` |
| `and` / `or` / `not` | `of`, `a_list_of: "conditions"` | The condition catalogue |

### Node shapes made honest

`_node_shapes()` keeps deriving `ability` and `static` from their dataclasses,
and gains:

- kind from the annotation, via an extended `_KINDS`;
- the four undeclared domains (`zone`, `forbids`, `cost` keys, and `stat`'s
  dependent pair);
- `a_list_of` for `conditions`, `targets`, `effects` and every control body;
- `describes` for every field.

### What `catalogue()` returns

Three new keys beside the five it has:

```
"abilities"  the ability node shape, its fields already described
"statics"    the static node shape
"structures" the control nodes and the sub-shapes they reference
```

### Renderer reuse

| Metadata | Component | Exists? |
| --- | --- | --- |
| `role: which/switch/amount/names/open` | The controls in `valueHtml` | ✅ |
| `role: whom`, `written_as` | The group picker | ✅ |
| `role: structure` | The parsed JSON editor | ✅ |
| `shown: given`, `spelling` | Not asked | ✅ |
| `shaped_like` | A nested group of the same controls | New, ~20 lines |
| `a_list_of: "effects"` | The step list | ✅ — it *is* the step list |
| `a_list_of: "conditions"` | A condition list with and/or/not | New component |
| `a_list_of: "targets"` | The target picker | ✅ |
| `a_list_of: "modes"` | A list of `mode` sub-shapes | New, composed of the two above |

Four of the nine already exist, one is trivial, and the remaining four are one
recursive component each.

---

## D. Implementation roadmap

### Phase 1 — correctness

Nothing new to author; the cards the form already makes stop being wrong.

1. **Honest node shapes.** Derive kinds from the dataclass annotations; declare
   the four missing domains (`zone`, `forbids`, `cost` keys, `promise` change
   keys) beside the code that enforces them.
2. **Publish the trigger's default scope** in `catalogue()["triggers"]`.
3. **Hand ability metadata to the page** and render `scope` as a pre-selected
   choice that follows the trigger. This alone reaches 51.7% of carded content
   and removes the silent contradiction between a card's text and its
   behaviour.
4. **Declare what kind of target each effect accepts**, beside the 33 handler
   guards, and filter the aim picker on it. Turns a play-time crash into a
   picker that only offers what fits.
5. **Refuse an empty condition combinator**, the way an empty branch already
   is.

Phase 1 adds one control to the form.

### Phase 2 — common card authoring

The cards a real expansion author will actually want to write.

1. **`ability.conditions`** — needs the condition-list component, and gives
   `and` / `or` / `not` at the same time (23.1%).
2. **Several abilities per card**, with explicit ordering and per-ability
   target binding (11.6%).
3. **`ability.replacement`** — one switch, and the three effects that can
   currently be built but never run become usable (7.0%).
4. **`ability.cost`** via `shaped_like` (3.6%), plus `optional` and `zone`.
5. **Statics** as their own node type, with the dependent `stat` domain
   (8.8%, and 4.6% of cards have nothing else).

At the end of phase 2 the form should reach roughly **85%** of the carded
content, on the measured blocker counts.

### Phase 3 — advanced mechanics

Each needs a component that does not exist yet.

1. **`stop` and `sequence`** — leaves, essentially free once bodies exist.
2. **`may`** — one body plus a prompt (7.9%).
3. **`for_each`** — a body plus a target picker.
4. **`repeat`** — a body plus a number, and the number wants a dynamic head.
5. **Dynamic heads** — every number control gains "a number" or "work it out
   from…"; the builder already accepts the result (14.0%).
6. **`choose`** — a list of modes, each a description and a body (6.4%).
7. **`store`**, and a picker for `values_equal.of` over what earlier steps
   stored.

---

## E. Risks

### Architectural

**The ability editor becoming a second architecture.** The largest risk, and
the reason §1 answers "reuse the roles" so firmly. If ability fields get their
own controls, the project ends with two renderers that must be kept in step —
the exact condition the metadata layer was built to remove. The mitigation is
a test of the shape already used: *every* parameter the catalogue publishes,
from any of the eight sections, must land in a known `shown` bucket, and the
page must contain no name from any registry.

**A body component that is not recursive.** If "a list of effects" is written
once for the top level and again for a branch, nesting becomes a special case
and `choose` inside `may` inside `if` will not work. The component must be
defined in terms of itself from the first line of it.

**Ability ordering.** `ability_index` indexes activated abilities. An editor
that reorders, sorts, or renumbers on the author's behalf will silently change
which ability a saved command activates. Ordering must be explicit and never
implicit.

### Where the UI could diverge from the runtime

**Dependent facts.** Scope's default depends on the trigger; a static's `stat`
domain depends on its scope and on the card being a monster. Both are derived
in the engine by a branch. If the metadata copies the answer instead of
publishing the derivation, the copy will drift — this project has found that
same drift five times, and each fix was to have the guard read the
declaration. The `default_from` mechanism must point at engine-derived data,
not at a duplicate table.

**Scope's silence, if only half-fixed.** Publishing the default without making
the form pre-select it leaves the trap in place. Making the form pre-select it
without publishing the default puts `SELF_SCOPED_TRIGGERS` into the page as a
copy.

**Cost, which is checked in two places.** `unpayable` refuses unknown keys at
play time; a `cost` node shape would refuse them at load time. Both must read
`costs.KINDS`.

### Where metadata could become incomplete

**A new `Ability` or `Static` field.** The shapes are derived from the
dataclasses, so a new field appears automatically — with a kind from its
annotation and *no* domain, `describes` or role hint. That is the safe failure
(it renders as a labelled box) but it is still a gap, and it should fail a
test rather than appear quietly: the existing "no parameter reaches the form as
a bare name" test should be extended to the new sections.

**A new control node.** `CONTROL_KEYS` and `CONTROL_BODIES` are read off the
expanders by hand. A node added without an entry gets no shape and is silently
unauthorable — which is exactly today's situation for six of the seven.

**A new effect whose handler guards its target kind.** If the accepted-kind
declaration of phase 1 is optional, the 34th effect to want one will not have
it, and the picker will offer aims that crash. It should be required of every
effect that guards, and the existing AST-based `_guards` test in
`test_capability_metadata.py` is the precedent for enforcing that.

**`describes` on the new sections.** Targets and conditions went from 164 bare
labels to 0 only because a pass was made over them. Ability, static and control
fields start at 100% bare.
