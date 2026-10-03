# Validating custom content

A design, written before any code and offered for agreement. The problem is one
sentence: **the pipeline checks that an effect's name exists and never checks
what it was given**, so an author's first mistake surfaces as a traceback out
of the interpreter, four hundred moves into a game, naming nothing.

Everything below that says "does" or "does not" was run.

---

## 1. What the pipeline checks today, and where

`ContentLoader.load_root` runs six stages over a directory, collecting problems
rather than stopping at the first, and refuses the whole batch at the end:

```
read JSON            → FORMAT     the file could not be parsed
manifest             → SCHEMA     a set that does not say what it is
card schema          → SCHEMA     missing id, name, type; a field of the wrong kind
card semantics       → SEMANTIC   an effect, trigger, condition or target the engine has no name for
references           → REFERENCE  a character whose starting item is not in the library
registration         → DUPLICATE  the same expansion twice
```

Execution happens somewhere else entirely: `EffectExecutor` resolves a card's
parameters and calls the registered handler, at the moment the card is played.

The seam between the two is deliberate and documented. `Vocabulary` is **plain
names** — four frozensets of strings — and `engine_vocabulary()` builds it by
asking the live engine. The loader checks spelling against strings and never
imports an effect. Its own docstring says why: content loading happens before a
game exists and must never touch one.

That seam is the thing to extend. It is also the thing not to break.

---

## 2. Where it stops holding

Five classes of mistake, all measured on custom cards written for the purpose.

| What the author wrote | Caught | When | What they are told |
|---|---|---|---|
| `{"effect": "summon_a_dragon"}` | **yes** | at load | file, card, ability, and the effect name |
| unknown `trigger` / `condition` / `target` name | **yes** | at load | the same |
| `{"effect": "gain_coins", "amount": "lots"}` | **no** | mid-game | `TypeError: '<' not supported between instances of 'str' and 'int'` |
| `{"amount": {"frmo": "dice"}}` — a misspelled dynamic head | **no** | mid-game | `TypeError: '<' not supported between instances of 'dict' and 'int'` |
| `{"effect": "shuffle_deck", "deck": "spaghetti"}` | no | mid-game | `EffectExecutionError: unknown deck 'spaghetti'; the decks are loot, treasure, monster, room` |
| `{"effect": "move_cards", "position": "sideways"}` | no | mid-game | `EffectExecutionError: unknown position 'sideways'; use 'top', 'bottom' or 'discard'` |
| `{"effect": "draw_loot", "count": -3}` | no | mid-game | `EffectExecutionError: draw_loot count must be non-negative` |

Two things are worth separating out of that table.

**The bottom three are not the emergency.** They arrive late, but they arrive
as sentences naming the effect and often the valid values. Somebody can act on
them. They should move earlier; they are not what makes custom content unsafe.

**The middle two are.** A raw `TypeError` from inside the interpreter names no
card, no file, no ability and no field. It is indistinguishable from an engine
bug, and the honest reading of it — for the author — is that FSME crashed.

**The misspelled dynamic head deserves naming on its own.** The DSL lets a
parameter be a value the ability learns while running:

```json
{"effect": "deal_damage", "amount": {"from": "dice"}}
```

`EffectExecutor` recognises five heads — `from`, `count`, `from_event`,
`last_result`, `player_of` — and anything else falls through to the final
`else`, which hands the raw dictionary to the effect. So `{"frmo": "dice"}` is
not a rejected typo; it is a dictionary passed where an integer was expected.
This is a closed set of five names and checking it is nearly free.

---

## 3. The minimal extension point

**Widen the vocabulary; do not widen the coupling.**

`Vocabulary.effects` is `frozenset[str]` today. Give the vocabulary a second
field — a mapping from effect name to a plain-data description of what that
effect takes — still built by `engine_vocabulary()` from the live registry,
still handed to the loader as inert data. The loader gains a check and no new
import. Nothing about the seam changes: the pipeline still never touches an
effect implementation, and a caller with no engine still gets schema validation
and no semantics, exactly as now.

### The descriptions are derived, not written

This is the part that makes the design safe to maintain, and it was measured
rather than hoped for.

Every effect is registered with a Python callable, and **all 63 of them have
fully annotated signatures — zero unannotated parameters**. The annotations
that appear are few and plain:

```
int ×26   str ×20   bool ×8   Any ×8   Any | None ×6   int | None ×6
```

`inspect.signature` on the registered handler therefore already yields the
parameter names, their types and their defaults. **24 of the 63 take no named
parameters at all** — `kill`, `recharge`, `end_turn` and the like work on
targets — and for those the correct check is that the card passed no parameters
beyond the ones every effect accepts.

Deriving rather than declaring matters because a second, hand-written table of
effect parameters is a table that drifts from the effects. The signature cannot
drift from the function it belongs to.

### Domains have to be declared, and there are few of them

Types do not catch `deck: "spaghetti"` — a string where a string was expected.
What is wrong with it is its *domain*: there are four decks.

Those domains exist in the code already, as the constants the runtime checks
against — `decks.DECKS`, the three positions `move_cards` accepts, the two
destinations `take_card` accepts. The proposal is to name them where the other
facts about an effect are already named, in the `register(...)` call beside
`primary` and `literal`:

```python
registry.register(
    "move_cards", move_cards,
    needs_target=True, primary="deck",
    values={"deck": DECKS, "position": ("top", "bottom", "discard")},
)
```

The same constant, referenced once, used by the runtime check and the load
check. There is no second list to keep in step.

Ranges are the same shape and even smaller: a handful of counts that must not
be negative. `values={"count": NON_NEGATIVE}` or an explicit minimum, declared
in the same place.

### What v1 should not attempt

**Target parameters.** Targets take one opaque `params: Mapping[str, Any]` —
all 46 of them — so their keys (`count`, `as`, `minimum`, `from_top`,
`prompt`) cannot be derived from a signature. Checking them means declaring
them, 46 times, by hand. That is a real piece of work with a real payoff and it
is not this one: unknown target *names* are already caught at load, which is the
larger half.

**Conditions.** 41 registered and annotated, so the same derivation would work.
They take fewer arguments and go wrong less often. Worth doing second.

---

## 4. Errors

**The accumulating report already exists and must not be duplicated.**
`ValidationReport` collects `ValidationIssue`s and `raise_if_failed` raises one
`InvalidContentError` holding all of them. A `ValidationIssue` already carries
`category`, `message`, `file`, `identifier` and `location`.

So the answer to "is an exception enough, or is a report needed" is: the report
is there, it is used by every stage, and the new checks are new issues in it.
An exception per problem would mean an author fixes one typo per run.

What the requested fields map onto:

| asked for | today | needed |
|---|---|---|
| expansion | implied by `file` | the manifest id, as its own field |
| file | `file` | — |
| card | `identifier` | — |
| ability | part of `location` | — |
| path | `location`, coarse | a finer path: `ability 0 → effects[1] → amount` |
| message | `message` | — |
| severity | `category` | — |

Two changes, both additive: an `expansion` field, and a `location` built as a
path rather than a phrase. Everything that prints an issue keeps working,
because `__str__` already joins whatever parts are set.

The message this produces for the case in the brief:

```
[schema] example_expansion example.json Dark Coin ability 0 → effects[0] → amount:
  gain_coins takes a whole number here, and the card gives text ("lots")
```

One line, because the report prints one line per issue and an author with six
mistakes wants six lines. The fielded form is in the issue for anything that
wants to render it differently.

---

## 5. Compatibility

Three things must not move, and each has a way to prove it.

**Official content must pass unchanged.** 1045 cards, 352 with rules, are the
regression suite for this: if any of them fails the new check, either the check
is wrong or the card was. Either way it is caught before anything ships. This
is the single most valuable test in the plan.

**Behaviour in a running game must not change.** The layer adds checks at load
and touches no executor and no effect. The runtime checks stay exactly where
they are — a validator is not a reason to remove a guard, and content can reach
the engine by paths that never went through the loader.

**A caller with no engine keeps working.** `Vocabulary.is_empty` means "schema
only, no semantics", and that must stay true when the vocabulary grows a field:
an empty vocabulary checks structure and nothing else, as now.

The one visible change is that content which used to load and fail later will
now fail to load. That is the point, and it means a set somebody has already
written may stop loading — correctly, but abruptly. Since no custom set exists
outside this repository yet, the cost is zero today and rises with every week it
is deferred.

---

## 6. Test plan

The eight asked for, plus what the analysis adds.

1. a good custom card loads and plays — **passes today**;
2. an unknown effect is refused — **passes today**;
3. `amount: "lots"` is refused at load, naming the field and both types;
4. `deck: "spaghetti"` is refused at load, listing the four decks;
5. the issue carries the file name;
6. the issue carries the card name;
7. six mistakes in one file produce six issues in one refusal;
8. **the whole of `content/` loads unchanged** — 1045 cards, no new issue.

And:

9. a misspelled dynamic head — `{"frmo": "dice"}` — is refused, and the five
   real heads are all accepted;
10. an effect taking only targets rejects a parameter it does not take, and one
    of the 24 such effects is used as the case;
11. a parameter marked `literal` is **not** type-checked, because its value is
    the effect's own structured data;
12. `Vocabulary()` with nothing in it still validates structure and refuses
    nothing semantic;
13. the runtime guards still raise — the validator does not replace them;
14. every effect in the registry yields a parameter description without
    raising, so a newly registered effect cannot silently opt out.

Every custom fixture builds its content in `tmp_path`. A test in this project
has written into `content/` before.

---

## 7. Files, order, risks

### The order

**Step 1 — describe an effect.** `EffectSpec` gains a derived parameter
description; `EffectRegistry` exposes it. No validation yet, no loader change.
Tests 14 and the descriptions themselves.

**Step 2 — carry it.** `Vocabulary` gains the mapping; `engine_vocabulary()`
fills it. Still no check. Test 12.

**Step 3 — check it.** `cards/validator.py` grows argument checking; issues
gain `expansion` and a path-shaped `location`. Tests 3, 5, 6, 7, 9, 10, 11 —
and 8, which is the one that says whether the design was right.

**Step 4 — domains.** `values=` on `register(...)` for the effects that have
one, drawn from the constants the runtime already uses. Tests 4 and 13.

**Step 5 — the message.** A worked example in the documentation and one
deliberately broken set under `tmp_path` that produces it.

Conditions and target parameters are step 6 and step 7, and are not part of
this agreement.

### Files

| File | Change |
|---|---|
| `src/fsme/effects/registry.py` | `EffectSpec` describes its parameters; `values=` on `register` |
| `src/fsme/effects/builtin/*.py` | domains named on the effects that have them — decks, positions, destinations |
| `src/fsme/content/vocabulary.py` | a field for the descriptions; `is_empty` unchanged in meaning |
| `src/fsme/runtime/vocabulary.py` | fills it from the live registry |
| `src/fsme/cards/validator.py` | the new checks |
| `src/fsme/content/report.py` | `expansion` on an issue |
| `src/fsme/content/loader.py` | passes the expansion through |
| `tests/test_validation.py` | new |
| `docs/CARD_SCHEMA.md`, `docs/CONTENT_PIPELINE.md` | what is now checked |

### Risks

**A check that is wrong refuses good content.** The mitigation is test 8 and it
is not optional: 1045 cards, 352 with rules, every one of them a case somebody
already decided was correct. Run it before writing the second check.

**`Any` is most of the annotations for a reason.** Eight parameters are `Any`
and six `Any | None`, because they genuinely take a card, a player or a
structured value. `Any` must mean *no type check*, not *anything goes wrong
quietly*. A design that treated `Any` as a failure would fail on official
content immediately — which is, again, what test 8 is for.

**Dynamic values must not be type-checked as literals.** `{"from": "dice"}`
resolves to an integer at run time and is a mapping at load time. The rule is:
a mapping whose head is one of the five known dynamic names is accepted where a
number is wanted, and a mapping whose head is anything else is the typo the
check exists to catch.

**`literal` parameters are exempt by construction.** `EffectSpec.literal`
already names the parameters handed over as written, and those must skip the
check entirely — they are the effect's own data and the executor never touches
them.

**The seam is worth more than the feature.** If this ends up importing effects
into the loader, it has failed even if every test passes: the pipeline's
independence from a live engine is what lets content be checked by a tool with
no game in it. The vocabulary is data. It must stay data.

### What this is not

No card editor. No UI. No change to the card format — the checks are about what
the format already allows. No rule that mentions a card by name, ever: every
check is derived from the DSL's own description of itself, which is what makes
it work for cards nobody has written yet.
