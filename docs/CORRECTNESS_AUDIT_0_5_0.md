# Correctness audit — Author UI ↔ validator ↔ runtime (0.5.0)

The question this audit answers:

> Can a person, using the Author UI as it ships, build a card the engine calls
> valid but cannot execute — or executes differently from what its structure
> says?

Yes. In two general ways, not one, and the example the UX audit found
(`steal_soul` aimed at a treasure) is one of **582** instances of the smaller
of the two.

Everything below was measured by driving the real path — build a card the way
the page builds it, validate it with the same validator, then play it in a real
game — not by reading handlers.

---

## Executive summary

| | count |
|---|---|
| **Critical** | 2 |
| **High** | 1 |
| **Medium** | 1 |
| **Low** | 1 |
| **Architecture gaps (flagged, not fixed)** | 2 |
| **False positives investigated and cleared** | 3 |

**Shipped content is clean.** 1045 definitions, 342 aimed effects, 85 aims at
bound groups, 1 dynamic value read: **zero** affected by any finding. Every fix
below can be made without touching a single existing card.

The two Critical findings are different in character and the second is worse:

- **C1 — silent.** A card can read a value that nothing stores. It validates,
  it plays, and it quietly does nothing. There is no error, ever.
- **C2 — loud, but late.** A card can aim an effect at a kind of thing the
  effect refuses. It validates and then throws when played.

C1 is the more dangerous because the author is never told. C2 is bigger in
surface area.

### Where the divergence begins, in one sentence

`EffectSpec` describes what an effect **takes as parameters** and never what it
**accepts as targets**, and `references.py` checks the namespaces inside
conditions and never inside effect parameters. Both are gaps in what metadata
is able to say, so the validator cannot check what nobody told it.

---

## Confirmed bugs

### C1 — Critical — a value read that nothing stores is silently zero

```
Effect / feature:  any effect parameter written {"from": "<name>"}
Reproduction:      gain_coins {amount: {from: "dcie"}}   (a typo for "dice")
                   — also: reading "dice" before roll_dice runs
                   — also: reading "dice" stored by a different ability
Expected:          refused at validation, the way a condition already is
Actual:            validates clean, plays clean, gains 0¢, and the page says
                   "P was played and nothing changed. That may be right…"
Root cause:        validate_references walks conditions for parameters whose
                   metadata says refers_to=VALUES. A dynamic head inside an
                   effect parameter is a different syntax and the walker never
                   descends into it.
Affected layer:    validator (cards/references.py)
Fix strategy:      validator-only — descend into effect parameters and treat a
                   dynamic head as the reference it is. The namespaces, the
                   ordering rule and the ability boundary are all already
                   implemented there; only the walk is missing.
Regression test:   metadata ↔ validator ↔ runtime: a card reading an unstored
                   name is refused; the same card with the roll first is not.
```

Proof that the checker sees one and not the other:

| written | `validate_references` says |
|---|---|
| `conditions: [{values_equal: {of: "never_stored"}}]` | *'never_stored' is not a value this ability stores* |
| `effects: [{effect: "gain_coins", amount: {from: "never_stored"}}]` | *(nothing)* |

Three distinct authoring mistakes all land here, and all three are things the
new multi-ability editor makes easy to do:

1. a misspelled name;
2. reading a value before the step that stores it;
3. reading a value stored by a **different ability** — the engine builds one
   context per ability and shares nothing, so this can never work.

### C2 — Critical — the UI offers every target to every effect

```
Effect / feature:  the aim question, for all 43 effects that need a target
Reproduction:      steal_soul aimed at target_treasure
Expected:          the treasure is not offered, or validation refuses it
Actual:            validates clean; playing raises
                   "'steal_soul' expects player targets"
Root cause:        EffectSpec has needs_target: bool and nothing about kind.
                   The real contract lives inside handler bodies as
                   _players(...) / _cards(...) guards, which no other layer
                   can read. capabilities.py therefore publishes
                   "aimable": True for all 46 targets, and aimHtml filters on
                   nothing else.
Affected layer:    metadata (the gap) → validator → UI
Fix strategy:      declare the kind at registration, beside the guard, and have
                   the guard read the declaration so the two cannot drift.
                   Then metadata publishes it, the validator checks it, and the
                   UI filters — one concept, no per-effect special cases.
Regression test:   an invariant test — for every registered effect, every
                   target the UI offers for it is one the runtime accepts.
```

Measured: **27 of 43** effects that take a target restrict its kind.

| runtime accepts | effects |
|---|---|
| players only (17) | `attach_curse`, `claim_soul`, `discard_loot`, `draw_loot`, `gain_coins`, `gain_soul`, `gain_treasure`, `lift_limit`, `lose_coins`, `lose_soul`, `prevent_next_damage`, `reveal_hand`, `revive`, `set_coins`, `skip_next_turn`, `steal_soul`, `take_extra_turn` |
| cards only (8) | `copy_ability`, `copy_card`, `deactivate`, `duplicate`, `hold_tapped`, `make_eternal`, `place_monster`, `recharge` |
| stack objects only (1) | `cancel_stack` |
| things with hit points (4) | `deal_damage`, `divide_damage`, `heal`, `kill` |
| anything (10) | `destroy_treasure`, `discard_cards`, `discard_monsters`, `give_treasure`, `move_cards`, `remove_curse`, `steal_treasure`, `swap_cards`, `take_card`, `transfer_coins`, `add_counter`, `add_modifier` |

Cross the restrictions with the 40 targets that yield a definite kind:
**582 (effect, target) pairs the UI offers, the validator accepts and the
runtime refuses.**

### H1 — High — `put_into_play` aimed at a player crashes unguarded

```
Effect / feature:  put_into_play
Reproduction:      put_into_play aimed at controller
Expected:          a refusal naming the mistake
Actual:            AttributeError: 'PlayerState' object has no attribute 'owner'
                   shown to the author as
                   "The engine would not play this card: 'PlayerState' object
                    has no attribute 'owner'."
Root cause:        the handler has no kind guard at all — it reaches straight
                   for target.owner.
Affected layer:    runtime (missing guard), and C2's metadata gap above it
Fix strategy:      subsumed by C2: declaring the kind gives it the guard every
                   other card-only effect has.
Regression test:   covered by the C2 invariant test.
```

### M1 — Medium — a group reference in an effect parameter crashes unguarded

```
Effect / feature:  {"player_of": "<name>"} inside an effect parameter
Reproduction:      gain_coins {amount: {player_of: "never_bound"}}
Expected:          refused at validation — nothing binds that name
Actual:            TypeError: '<' not supported between 'NoneType' and 'int'
Root cause:        the same walk C1 is missing. player_of names a group; the
                   reference checker never looks inside effect parameters, so
                   an unbound name reaches the resolver, which answers None.
Affected layer:    validator
Fix strategy:      the same fix as C1 — one walk covers both namespaces,
                   because the metadata already says which head names which.
Regression test:   shared with C1.
```

### L1 — Low — an engine refusal shows the author a dataclass repr

```
Effect / feature:  deal_damage / heal / kill / divide_damage on something with
                   no hit points
Reproduction:      deal_damage aimed at self, on a loot card
Expected:          "a loot card has no hit points"
Actual:            "The engine would not play this card: 'chosen_1'}),),
                    optional=False, cost=mappingproxy({}), replacement=False,
                    scope=None, zone='', description=''), …"
Root cause:        two together. damage.py:_hit_points interpolates the whole
                   CardInstance into the message (848 characters), and
                   author.said_by_the_engine takes the text after the last
                   ": ", which lands in the middle of the repr.
Affected layer:    runtime message + author-facing message
Fix strategy:      name the card, do not repr it. said_by_the_engine's
                   heuristic is then sound again.
Regression test:   the message for this refusal names the card and is short.
```

---

## Runtime ↔ metadata gaps

What the runtime knows and the metadata cannot say:

| Runtime fact | Where it lives | Expressible today? |
|---|---|---|
| "my targets must be players" | `_players()` inside handler bodies | **No** — `EffectSpec` has no such field. This is C2. |
| "my targets must be cards" | `_cards()`, inline `isinstance` checks | **No** — same gap |
| "my targets must be stack objects" | `cancel_stack` inline check | **No** — and `stack` is not one of the two kinds the vocabulary has |
| "my target must have hit points" | `damage.py:_hit_points` | **No** — a third kind, narrower than `cards` |
| "I need an event open in context" | `ctx.event is None` in `replacement.py` | **No, and not statically decidable** — see architecture gaps |
| "reading an unstored value gives 0" | `effect_executor._resolve_params` | Deliberate, documented, and the cause of C1's silence |

## Validator ↔ runtime gaps

Where validation says OK and the runtime disagrees:

| Case | Runtime | Validator |
|---|---|---|
| effect aimed at the wrong kind | raises | silent — C2 |
| effect parameter reads an unstored value | returns 0 | silent — C1 |
| effect parameter names an unbound group | `TypeError` | silent — M1 |
| `cancel_event` / `prevent_damage` with no open event | raises | silent — architecture gap |
| a value stored by another ability | returns 0 | silent — C1 |

## UI ↔ metadata gaps

| Case | Detail |
|---|---|
| aim offers everything | `capabilities._targets` sets `"aimable": True` unconditionally; `aimHtml` filters on that alone |
| the machinery already exists | `groupHtml` **does** filter by kind via `fits(t, f.picks)` — the same idea, applied to parameters and not to the aim |
| `store` unreachable | effect nodes publish no `store` parameter, so a value cannot be named deliberately — a capability gap, not a correctness bug |

## Silent semantic risks

Cases where nothing crashes and the card may not do what its structure says.
**This list is the reason this audit exists.**

1. **Misspelled stored value** → 0. `{"from": "dcie"}` after a roll.
2. **Reading before storing** → 0. `gain_coins {from: dice}` placed above
   `roll_dice`.
3. **Reading across abilities** → 0. Contexts never share; the editor now makes
   several abilities easy to build and gives no sign that they are sealed.
4. **`{"count": …}` domain is checked, `{"from": …}` is not** — the two heads
   of the same choice are enforced unevenly, so an author who gets one right
   learns nothing about the other.
5. **"nothing changed" reads as reassurance.** The try-it message says *"That
   may be right — some cards only matter later"*, which is exactly what a
   silently broken card says too.

## Existing card impact

| Category | Count | Notes |
|---|---|---|
| **A — really wrong today** | **0** | |
| **B — legacy but correct** | 85 | aims at a group bound by `as`; kind is decided at run time and must stay unchecked |
| **C — only the new Author UI can build it** | all of C1, C2, H1, M1 | the reason this audit is worth acting on |
| **D — runtime supports more than the UI offers** | `store` on effect nodes | capability gap, not a correctness bug |

Measurements: 1045 definitions · 342 aimed effects · **0** kind clashes ·
1 dynamic value read · **0** dangling reads.

## Architecture gaps — flagged, not fixed

### G1 — "needs an open event" is not statically decidable

`cancel_event` and `prevent_damage` raise *"may only be used by a replacement
ability"*, but the guard is `ctx.event is None` — which is about the context an
ability resolves in, not about a flag on the card. An ability triggered by an
event legitimately has one without being a replacement. A static check would
produce false refusals for correct cards, so **no check is proposed**. Making
this expressible would mean describing, per trigger, whether an event is in
context — a new concept, and one that belongs with `trigger_scopes` if it is
ever wanted.

### G2 — the kind vocabulary has two words and the runtime uses four

`content.vocabulary` distinguishes `players` and `cards`. The runtime also
distinguishes **stack objects** (`cancel_stack`) and **things with hit points**
(`deal_damage` and its three siblings), both of which are narrower than
`cards`. The fix below therefore checks what is expressible and deliberately
leaves the two narrower kinds unchecked rather than inventing vocabulary for
four effects. Widening the kind words is a separate decision.

## False positives investigated and cleared

- **`may` / `sequence` with the body under the head.** Refused by validation,
  but the builder never writes that shape — it writes the canonical body plus a
  placeholder (`{"effects": [...], "may": []}`). Not reachable from the UI.
- **`add_counter` / `add_modifier` accepting every kind.** Correct: both act on
  players and cards by design.
- **Multiple-ability isolation.** Verified sound — bindings and stored values
  are per ability, exactly as `AbilityContext` promises. The cross-ability read
  in C1 is a missing *check*, not a leak.

---

## Recommended fixes

### Validator only

- **C1 + M1** — descend into effect parameters in `validate_references` and
  treat a dynamic head as the reference it is. No new metadata: `ParamShape`
  already says which head names a value and which names a group, and the
  ordering rule and ability boundary are already implemented.

### Metadata + validator + UI (one declaration, three readers)

- **C2 + H1** — give `EffectSpec` the kind its targets must be, declared at
  registration beside the guard that enforces it, with the guard reading the
  declaration. Publish it through `catalogue()`, check it in the validator, and
  filter the aim list with the `fits()` the UI already has.

### Runtime message only

- **L1** — name the card in `_hit_points` instead of interpolating it.

### Architecture change — not proposed here

- **G1** — "needs an open event".
- **G2** — kinds narrower than `cards`.

### Explicitly not touched

Card JSON format · card schema · the semantics of any existing card · UX
labels, ordering, help, vocabulary — all of that is the next stage.
