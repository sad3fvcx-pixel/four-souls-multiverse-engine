# Capability metadata: a systemic audit

The Author UI renders a form from what the engine says about itself. It does
that well for a dozen parameters and badly for the rest, and the reason is not
that a dozen strings are missing. **Nothing obliges a parameter to describe
itself, so most do not.**

This asks what layer would make that impossible, checked against all 63
registered effects rather than the loot cards the interface was built on.

---

## 1. What the engine says today

74 parameters across 63 effects.

| | |
|---|---|
| carry words a person could read | **14** |
| carry none — the UI shows the bare name | **60** |
| declare a closed domain | 6 |
| declare a floor | some |
| the UI cannot render from `kind` alone | 14 |

The 60 are why an author is shown `what`, `area`, `key`, `until`, `trigger`.

## 2. The interesting half: the engine already knows, and does not say

Not a documentation gap. A **drift** between what a handler enforces and what
its registration declares — the same class of fault found in the registries,
the scopes and the stats, each time with the same cause.

### 2.1 Domains enforced in the body, declared nowhere

```python
def lift_limit(ctx, targets, what: str = "loot_plays"):
    if what != "loot_plays":
        raise EffectExecutionError(f"there is no limit called '{what}'…")
```

`what` has exactly **one** legal value, and the UI offers a free text box.

Six parameters are provably like this — the handler raises on a bad value and
the declaration knows no domain: `copy_card.until`, `lift_limit.what`,
`pass_hands.direction`, `promise.event`, `require_attack.what`,
`watch_for.event`. Two of those (`promise.event`, `watch_for.event`) have a
domain the vocabulary *already carries* — the trigger list.

The scan only catches guards that raise. `expand_slots.area` branches on
`if area == "monster"` without raising, so the real number is higher; six is
the floor, not the count.

### 2.2 Requirements enforced in the body, declared optional

```python
if not key:
    raise EffectExecutionError("modify_event requires a key")
```

Five parameters raise when left out and are declared `required=False`:
`add_counter.counter`, `add_modifier.stat`, `modify_event.key`,
`promise.event`, `watch_for.event`. A form built from the declaration lets
somebody submit a card that cannot run.

**Both are one fault**: the guard is the fact, and the declaration is a second
copy that was never written. The fix is the one this project has used four
times — declare it *at the guard*, from the same constant.

## 3. Two rules that look right and are not

Worth recording, because both were tested and both would have made things
worse.

**"Hide what no card uses."** 24 parameters are written by none of the 1045
shipped cards — but `roll_dice.sides` is among them (every card takes the
default six) and it is exactly the sort of thing an author wants. Frequency
does not separate internal from optional.

**"Hide what the layer cannot check."** The 14 parameters of kind *"anything
the engine can only judge during a game"* are not one thing. They are three:

| | parameters | what the UI should do |
|---|---|---|
| a card or player the engine hands over | `deal_damage.dealt_by`, `gain_soul.earned_from`, `attach_curse.card`, `give_treasure.to`, `take_card.player`, `require_attack.who`, `claim_soul.card`, `gain_soul.card`, `divide_damage.dealt_by` | **not a field at all** — this is aiming, which the form already does |
| the effect's own structured data | `promise.changes`, `promise.when`, `watch_for.conditions`, `watch_for.effects` | a nested form, not a box |
| a value compared against an event | `modify_event.value` | genuinely free — any type |

Only the middle group is distinguishable today, by `literal`. The first group
is nine parameters that should never appear as text boxes and currently would.

## 4. Dependencies, which are recorded nowhere

Read out of the handlers:

| effect | the dependency |
|---|---|
| `heal` | `full` makes `amount` meaningless — `hp if full else amount` |
| `add_counter` | `clear` makes `amount` meaningless |
| `modify_event` | `delta` and `factor` are alternatives — `if delta … elif factor` |
| `move_cards` | `depth_from` only means something for some values of `position` |

A form that shows all of them together invites a card that says two things at
once, and the engine silently picks one.

## 5. The layer

Five facts about a parameter. Three have a mechanism already; two do not.

| fact | today | what is needed |
|---|---|---|
| **purpose** | `ParamSpec.asks` exists, 14 of 74 filled | an obligation, not a field |
| **input** | `kind` — but that is a *validation* kind, not a widget | a role (below) |
| **values** | `values` — 6 drift from their guards | declare at the guard |
| **dependency** | nothing | new, small |
| **audience** | `literal` covers one case of three | a role (below) |

### 5.1 A role, not sixty sentences

The largest realisation from the audit: the 74 parameters fall into a handful
of **roles**, and a role settles the label, the widget and the visibility
together. It is one word per parameter, not a sentence, and it is what stops
this being sixty pieces of hand-written prose:

| role | means | the form does |
|---|---|---|
| `AMOUNT` | how many of the effect's own thing | a number box, floor applied |
| `WHICH` | one of a closed set | a dropdown from `values` |
| `SWITCH` | on or off | a checkbox |
| `NAMES` | free text naming something — a counter, a label | a text box |
| `WHOM` | a card or player the ability picks out | **no field** — offered through aiming |
| `STRUCTURE` | the effect's own nested data | a sub-form |
| `OPEN` | genuinely any value | a text box, last resort |

`asks=` then refines the wording where the role's default is not enough —
"how many cents" rather than "how many". Most parameters need only the role.

`WHOM` is the one that matters most: it turns nine parameters that would be
bare text boxes into the thing the form already knows how to do.

### 5.2 The obligation

A field nobody has to fill in is a field most people will not. So:

> **A registered effect whose parameter has no role fails a test.**

The same sentence already holds for targets (`yields`), conditions
(`describes`) and effect parameters' domains. It is the only mechanism in this
project that has actually prevented drift, and it is why the 61st parameter —
added next month by somebody who has not read this — cannot arrive silent.

### 5.3 Dependencies

Two shapes cover every case found:

```python
asks={"amount": "how much health"},
roles={"amount": AMOUNT, "full": SWITCH},
unless={"amount": "full"},          # `full` makes `amount` moot
one_of=("delta", "factor"),         # alternatives
```

Declared beside the guard that implements them, like everything else.

## 6. What this does not do

**Nothing is removed.** Every parameter stays exactly as expressive as it is;
this describes them, and a role that the current form cannot render (`OPEN`,
`STRUCTURE`) is shown in the advanced view rather than dropped. The engine's
expressiveness and the form's ambition are separate questions, and the meta
layer is what keeps them separate — the form renders what it can and says
plainly what it cannot, instead of showing a box nobody can fill.

**No second table.** Roles, domains and requirements are declared at the
registration, next to the guard that enforces them, and the two domains that
already exist elsewhere (`EventType` for `watch_for.event` and `promise.event`)
are read from there rather than restated.

## 7. What implementing it means

In order, each measurable on its own:

1. **Fix the drift** — 6 domains and 5 requirements, each declared from the
   constant its guard already checks. Smallest, and it makes 11 parameters
   renderable immediately.
2. **`roles=` on `register`, and the test that makes it compulsory.** The
   mechanism plus one word per parameter, 74 of them — mechanical, and the
   test is what makes it complete rather than mostly complete.
3. **`WHOM` routed to aiming.** Nine parameters stop being text boxes and
   start being the question the form already asks.
4. **`unless` and `one_of`** for the four dependencies found.
5. **`asks=` for the rest**, which after 1–4 is the only part that is genuinely
   sixty pieces of prose — and by then most of them are already legible from
   role plus domain, so it is polish rather than a prerequisite.

Steps 1–3 are what stop the UI showing a bare name. Steps 4–5 make it read
well.

## 8. The measure

Not "every parameter has a description". These:

1. No parameter is rendered as a bare identifier — every one has a role, and
   a role always yields a label.
2. No parameter is rendered as a box that cannot be filled correctly — `WHOM`
   and `STRUCTURE` are never text.
3. Every domain the engine enforces is a domain the form offers; a scan of
   handler guards against declarations finds nothing.
4. Every requirement the engine enforces is one the form insists on.
5. A new effect cannot be registered without saying what its parameters are
   for.
6. Nothing the engine can express has become unexpressible.
