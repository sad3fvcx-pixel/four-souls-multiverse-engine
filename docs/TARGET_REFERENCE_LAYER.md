# Target Reference Layer

> **Status: built.** All five stages are in. 1045 cards load unchanged, 1000
> recorded games are identical, 40 journals replay faithfully, and the nine
> failures below are refused before a game starts.

The last class of card mistake that still reaches a game. No code was changed
for this document; every rule below was dry-run over all 1045 shipped cards
and against the failures it is meant to catch, in both directions.

---

## 1. The problem

An ability may name something it chose earlier. "Choose a player at random —
that player destroys an item they control" is two steps, and the second reads
the first. Five ways of getting that wrong all load cleanly today:

| written | what happens |
|---|---|
| a name read before the target that binds it | resolves to nothing; the ability does nothing |
| the same `as` name bound by two targets | the **second target is skipped entirely** — `resolve_all` leaves a bound alias alone, which is what makes an ability resumable |
| `chooser` naming nothing | falls back to the controller, so the wrong player is asked |
| `exclude` naming nothing | excludes nothing |
| `of` naming a group of the wrong kind | filtered to nothing, and nothing says why |

None raises. None is reported. Each is a card that plays a game other than the
one its author wrote.

## 2. The model

### 2.1 What a reference is — there are two kinds, not one

`AbilityContext` keeps two separate namespaces, and this is the fact the whole
design rests on:

```python
variables: dict[str, Any]        # written by `store`, read by `get`
targets:   dict[str, list[Any]]  # written by `bind`,  read by resolution
```

| | **group** | **value** |
|---|---|---|
| holds | a list of players, cards or monsters | one number |
| bound by | `as`, or a bare target's own name | `store` |
| read by | `of` on a target spec, `chooser`, `exclude`, an effect's `target` / `targets`, `for_each` | `{"from": …}`, `{"from_event": …}`, `{"player_of": …}`, and `of` on the `values_equal` **condition** |

Note the trap in the last row: **`of` means a group on a target spec and a
stored value on `values_equal`.** One word, two namespaces. Any checker that
treats `of` as one thing will be wrong about one of them.

### 2.2 Where the scope lives — one ability

Stated in the engine already:

> Each ability gets its own context and contexts never share variables, so a
> card that stores a dice result cannot be disturbed by another card resolving
> in the middle of it.

Not the effect tree, not the trigger, not the stack resolution: **one ability
resolution**. Two consequences, both measured:

- Branches (`then`, `else`, `may`, a `choose` mode) share the context at
  run time, but *whether they ran* is not knowable when the card is read. A
  name bound inside a branch and read outside it is bound only sometimes.
- **`watch_for` and `promise` open a new scope.** Their effects run later,
  against a fresh `AbilityContext` built by the runtime, so nothing bound
  outside is visible inside. Zero shipped cards cross that boundary today,
  and a card that did would fail silently.

### 2.3 When the check happens — both, answering different questions

**At load**, everything that is a fact about the text: does this name exist in
this ability, is it bound before it is read, is it bound twice, does it cross a
`watch_for` boundary, is its kind right. None of that needs a board.

**At run time**, unchanged: the resolver's own guards stay exactly where they
are. A group can be legitimately *empty* — a player with no items, an empty
monster row — and that is a correct card on a board where it does nothing, not
a mistake. Load-time checking refuses earlier; it never refuses instead.

### 2.4 How a kind is described — two values, not a lattice

What each target hands back was measured by resolving all 46 on a real board:
players, monsters, items, loot, characters, souls, curses, stack items, and
three that pass through whatever they were given.

A full type system over that is tempting and unnecessary, because **only two
distinctions are ever enforced at run time**:

| helper | filters by | so it wants |
|---|---|---|
| `_named_players` (serves `of`) | `isinstance(target, PlayerState)` | players |
| `_chooser` (serves `chooser`) | `isinstance(candidate, PlayerState)` | players |
| `_holder` (serves `of`) | reads `.controller` / `.owner` | cards |
| `_deck_top` (serves `exclude`) | card identity | cards |
| `_group`, `_most_common` | nothing | anything |

So a target declares one of four things — `players`, `cards`, `mixed`,
`passthrough` — on the line where it is already registered, exactly as its
parameters now are. Four values, 46 lines, no new file.

`{"of": "selected_monster"}` where players are wanted is then refused because
`target_monster` yields cards and `_named_players` wants players. Nothing finer
is needed, and nothing finer is enforced anywhere, so nothing finer would be
true.

### 2.5 What stays at run time

| construct | statically checkable | why |
|---|---|---|
| straight-line effects | fully | order is the text's order |
| `if` / `then` / `else` | within each branch | which branch runs needs a board |
| `may` | within the branch | whether the player says yes needs a player |
| `choose` modes | within each mode | which mode is picked needs a player |
| `for_each` | within the body | how many times needs a board |
| `watch_for`, `promise` | as a closed scope | their bodies run later, in a fresh context |
| whether a group is **empty** | never — and it is not an error | an instruction that cannot be carried out is a rule, not a bug |

The rule that follows: **a name is visible from its binder onwards, inside the
branch that bound it and everything nested in that branch.** Reading it from
outside is not visible.

That is the strictest reading available, and it costs nothing: dry-run over all
1045 cards, **0 complaints**. Eight cards do bind a name inside a `may` — and
every one of them reads it inside the same `may`, on the same effect node.

## 3. The rules, as language

1. A name used by `of`, `chooser`, `exclude`, `for_each`, or an effect's
   `target` must either be a registered target or a group bound earlier in the
   same ability.
2. A group is bound by `as`, or by a bare target's own name. Only `as`
   introduces a name that is not already a target.
3. A name is visible from its binder onwards, within the branch that bound it.
4. Two targets in the same scope may not bind the same name.
5. `watch_for` and `promise` begin a new scope. Nothing outside is visible in.
6. A group's kind must suit its reader: `chooser` and `of`-that-names-players
   want players; `exclude` and `of`-that-names-cards want cards.
7. `of` on `values_equal` is not a group at all. It names stored values, and
   those are bound by `store`.
8. An empty group is not an error.

## 4. Examples

**Right** — bound, then read, kinds agreeing:

```json
{"targets": [{"random_player": {"as": "unlucky"}},
             {"target_treasure": {"of": "unlucky", "chooser": "unlucky",
                                  "as": "doomed"}}],
 "effects": [{"effect": "destroy_treasure", "target": "doomed"}]}
```

**Right** — bound and read inside the same branch, which eight shipped cards do:

```json
{"may": [{"effect": "recharge",
          "targets": [{"target_treasure": {"as": "revived"}}],
          "target": "revived"}],
 "prompt": "Recharge an item?"}
```

**Wrong** — read before it is bound:

```json
{"targets": [{"target_loot": {"of": "later"}},
             {"target_player": {"as": "later"}}]}
```

**Wrong** — the second target is silently dropped:

```json
{"targets": [{"target_player": {"as": "who"}},
             {"target_monster": {"as": "who"}}]}
```

**Wrong** — the kind does not suit the reader:

```json
{"targets": [{"target_monster": {"as": "beast"}},
             {"target_loot": {"of": "beast"}}]}
```

**Wrong** — reaching across a new scope:

```json
{"targets": [{"target_player": {"as": "who"}}],
 "effects": [{"effect": "watch_for", "event": "damage_dealt",
              "effects": [{"effect": "kill", "target": "who"}]}]}
```

## 5. Implementation plan

Five stages, each measurable on its own and each leaving the content loading.

1. **`yields` on every target.** One argument on 46 existing registration
   lines, four possible values, declared beside the implementation like the
   parameters already are. Carried across as plain data on `TargetShape`; no
   function crosses the boundary. A test asserts no target may be registered
   without one.
2. **The scope walk, without kinds.** Build the binder/reader graph per
   ability and apply rules 1–5. This alone closes four of the five failures in
   §1. Dry-run says 0 against shipped content, and the six known-bad patterns
   are all caught.
3. **Kinds.** Apply rule 6 using stage 1's declarations, and declare what each
   reader wants beside the helper that filters — `_named_players`, `_chooser`,
   `_holder`, `_deck_top`.
4. **`values_equal`.** Rule 7: the stored-value namespace, bound by `store`.
   Small, and separate on purpose, because conflating it with groups is the
   mistake this stage exists to avoid.
5. **Documentation.** The rules into `CARD_SCHEMA.md`; the reference
   regenerated so `yields` appears beside each target.

Nothing in the resolver's behaviour changes at any stage. This layer refuses
earlier; it never refuses instead.

## 6. Tests

1. Every target says what it yields — none may be registered without it.
2. All 1045 cards still load and play; the thousand recorded games are
   unchanged.
3. Each of the five failures in §1 is refused, naming expansion, file, card
   and path.
4. A name bound and read inside one `may` is accepted — the eight shipped
   cards that do it.
5. A name bound inside a branch and read outside it is refused.
6. A reference across a `watch_for` or `promise` boundary is refused.
7. A bare target name still binds under its own name and is still a target.
8. `of` on `values_equal` reads stored values, not groups, and a `store` name
   is not confused with a group name.
9. An empty group is not an error — a card that can find nothing still loads
   and still plays.
10. A target registered without a declared kind is not judged, and that silence
    is not read as permission.

## 7. Not in this layer

- Whether a group will find anything on a board.
- How many objects it returns, or their exact card type beyond players-or-cards.
- Any new target, parameter or spelling. The language does not grow here.
- Changing a shipped card. Nothing measured requires one.
