# Two decisions about the card language

Both were left open by `docs/CONTENT_PIPELINE_AUDIT.md` because each needed an
answer about the game rather than about validation. No code was changed for
this document; everything in it was measured.

---

## 1. The domain of `stat`

### What is already there

Two tuples, and they already say what they mean:

```python
STATS = (ATTACK, MAX_HP, ATTACKS, LOOT_PLAYS, PURCHASES, ROLL, SHOP_COST, LOOT_STEP)
MONSTER_STATS = (ATTACK, DIFFICULTY)
```

`difficulty` is not "missing from `STATS`". It is deliberately outside it — a
monster has no seat, and the player statistics are keyed by one. `attack` is in
both because both a player and a monster deal damage.

So neither **A** (merge them) nor **B** (invent a split) is the question. The
split exists. The question is **which of the two applies at a given place in a
card**, and the answer is different at the two places a card writes `stat`.

### Where `stat` is written, measured

| stat | statics | abilities |
|---|---|---|
| `attack` | 12 | 12 |
| `difficulty` | 9 | 2 |
| `loot_plays` | 3 | 31 |
| `max_hp` | 5 | 5 |
| `attacks` | 2 | 9 |
| `loot_step`, `purchases`, `shop_cost`, `roll` | 4 | 1 |

### `add_modifier` — the domain is the union

The engine already guards it, and already decides player-or-monster *later*:

```python
if stat not in STATS and stat not in MONSTER_STATS:
    raise EffectExecutionError(f"unknown stat '{stat}' ...")
...
for player in targets:
    if not isinstance(player, PlayerState):
        # a monster's bonus lives on the card itself
```

The kind of thing a modifier lands on is the *target's* runtime type, and
`{"add_modifier": {"stat": "difficulty", "target": "current_monster"}}` is a
legitimate card. Narrowing the load-time domain below the union would mean
deciding statically what the engine deliberately decides dynamically, and it
would need a second, weaker model of what targets return.

**Decision: the domain is `STATS | MONSTER_STATS`, read from the two tuples the
runtime guard reads.** One fact, two readers — the same arrangement as
`_COMPARISONS` and `_COUNTABLE`.

### A static — the domain is the narrow one

A static's `stat` is checked nowhere today, and unlike `add_modifier` its
landing place **is** known before a game. Two functions read statics and they
never overlap: `bonus()` walks player statics and skips anything whose source
has no controller; `monster_value()` walks a monster's own statics plus those
scoped at monsters. A monster has no controller, so a monster's static can
never reach a player, and the split is automatic.

Which means the domain follows the scope, and every scope in the content is
accounted for:

| scope | lands on | domain |
|---|---|---|
| `all_monsters`, `other_monsters` | monsters | `MONSTER_STATS` |
| `all_players`, `controller`, `opponents` | players | `STATS` |
| `self`, or absent | the card itself — so **the card's type decides** | monster card → `MONSTER_STATS`, otherwise `STATS` |

Measured against the content, this is exactly what is written: `difficulty`
appears only under `all_monsters`, `other_monsters`, or `self` on a monster
card. Nothing has to change.

**Decision: C — keep both tuples where they are and choose by landing place.**
A static's `stat` is checked against the domain its scope and card type imply;
`add_modifier`'s is checked against the union. This is what "the domain should
match the place the value is actually used" means, and it introduces no table.

### Found while measuring

`Static.scope` defaults to `controller` and its docstring lists three values —
`controller`, `opponents`, `all_players`. Content writes **six**: those three
plus `all_monsters`, `other_monsters`, and `self` (24 uses). `self` is not
handled anywhere: `_in_scope` falls through to `source.controller == player_id`,
which is what `controller` does. So `self` works by accident, and **any
misspelled scope works the same way** — `"contoller"` silently means
`controller`. That is decision 2's business.

---

## 2. Unknown fields inside the ability DSL

### The proposed model, and it is right

- **Top level of a card: extensible.** `CARD_SCHEMA.md` §14 promises unknown
  optional fields are ignored, and that promise is worth keeping: it is what
  lets a set carry `rarity`, an artist credit, or a field a later engine will
  read.
- **Inside an ability: strict.** There is no forward-compatibility argument
  here, because the interpreter reads a closed set of keys and hands the rest
  to an effect that does not want them. `{"effect": "gain_coins", "amount": 1,
  "scopee": "self"}` is not a card using a field a later engine will
  understand. It is a card that is wrong now.

### Does it break anything? No — measured

Every key written at every level of the DSL across all 1045 cards, against
what the engine reads:

| level | engine accepts | content writes | unknown |
|---|---|---|---|
| ability | `trigger`, `conditions`, `targets`, `effects`, `optional`, `cost`, `replacement`, `scope`, `zone`, `description` | 9 of those 10 | **0** |
| static | `stat`, `amount`, `forbids`, `per_counter`, `scope`, `conditions`, `description` | all 7 | **0** |
| control `if` | `if`, `then`, `else` | all 3 | **0** |
| control `may` | `may`, `prompt`, `as` | all 3 | **0** |
| control `choose` | `choose`, `as`, `prompt` | all 3 | **0** |
| control `for_each` | `for_each`, `effects` | both | **0** |
| effect | the effect's own parameters plus `target`, `targets`, `store`, `as`, `optional`, `prompt`, `description` | — | already refused |

The effect level is already strict for every effect that describes itself; the
two dozen written with `**kwargs` stay open because they would accept anything.

### The rule

> Inside an ability — the ability object, a static, a control node — a key the
> engine does not read is an error. At the top level of a card it is not.

The accepted sets come from `Ability.from_data` and `Static.from_data`, so a
key added to the language widens the rule automatically. No second table.

### Two domains fall out of the same rule

- **Ability `scope`**: `self`, `any`, `controller` — the three the content
  writes and the three `runtime` branches on.
- **Static `scope`**: `controller`, `opponents`, `all_players`, `all_monsters`,
  `other_monsters`, `self`.

Giving `scope` a domain is what actually closes the audit's worst quiet
failure. A misspelled scope currently falls through to "controller" and the
ability fires under rules its author did not write.

### Conflict with a future DSL? No

The opposite. Because the accepted set is read from the code that consumes it,
a new key is accepted the moment it is read and refused until then — which is
the correct order. Writing the sets out by hand is what would conflict, and is
what the registries did before `tools/make_reference.py`.

---

## Cost

Both decisions refuse content that is already wrong and accept everything that
is already right: **0 complaints across 1045 cards** for every rule above.
Neither can change a game.
