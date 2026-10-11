# Target Validation v1 — analysis

No code was changed for this document. What it proposes is written down so it
can be argued with first, and everything it claims was measured against the
engine and against `content/` rather than assumed.

`docs/TARGET_AUDIT.md` asked whether targets could be validated at all and
recommended trying. This asks the narrower question: exactly what, exactly
how, and what breaks.

---

## 1. Where things stand

Targets are the third and last vocabulary a card writes in. The other two are
done:

| | names checked | arguments checked |
|---|---|---|
| effects | yes | yes — read from each handler's signature |
| conditions | yes | yes — described beside the helper that reads them |
| **targets** | **yes** | **no** |

Target *names* have been checked for some time, including the hard part: a
spec may name a group an earlier target bound with `as`, and that name belongs
to one card and is in no registry. `_declared_target_names` and
`_effect_aliases` already gather those. 103 of the 922 target specifications
in `content/` are such aliases.

What is not checked is everything written *inside* a target.

## 2. Measurements

### 2.1 The engine

46 registered names over 42 functions — four are aliases (`self`/`source`,
`active_player`/`current_player`, `current_monster`/`monster`,
`opponents`/`another_player`). One signature for all of them:

```python
TargetFn = Callable[[GameState, AbilityContext, Mapping[str, Any], RNG], list[Any]]
```

Nothing to introspect, exactly as with conditions. Reading the source instead
gives the same picture: parameters are understood by a small number of shared
helpers.

| helper | targets served | reads |
|---|---|---|
| `_ask` | 11 | `count`, `minimum`, `maximum`, `prompt`, and `chooser` via `_chooser` |
| `_all_treasures` | 4 | `owner`, `include_shop`, `exclude_eternal`, `exclude_source`, `counter`, `tag` |
| `_all_monsters` | 5 | `exclude_attacked` |
| `_named_players` / `_holders` | 4 | `of` |
| `_stack_items` | 2 | `kinds`, `triggers` |
| `_with_the_most` | 1 | `most` |
| `_group` | 2 | `of` |

Plus one set that belongs to no helper: **`as` is the resolver's own**.
`resolve` and `resolve_all` both read `params.get("as", name)`, for every
target without exception. Attributing it to `_ask` — which was the first
guess — produced 41 false complaints in the dry run and was the first thing
the measurement corrected.

### 2.2 The content

922 target specifications: 558 bare names, 364 objects, none using the
`{"target": ...}` spelling the resolver also accepts. 23 parameter keys, 103
distinct (target, key) pairs.

Coverage is partial and worth saying plainly: **33 of the 46 targets appear in
`content/` at all, and only 23 have any parameter written on them.** Thirteen
are never used by a shipped card — `all_treasures`, `another_player`,
`current_player`, `event_source`, `monster`, `none`, `owner`,
`player`, `previous_result`, `previous_target`, `source`, `target_soul`,
`top_stack`. Their descriptions would rest on reading the code alone, with no
content to check them against.

### 2.3 What passes the loader today

Eleven deliberately wrong targets, each put through the real validator and
then through a real resolver on a real board:

| written on a card | loader today | what the game does |
|---|---|---|
| `{"target_deck_card": {"deck": "tresure"}}` | accepts | `UnknownTargetError: unknown pile 'tresure deck'` |
| `{"target_deck_card": {"pile": "graveyard"}}` | accepts | `UnknownTargetError: unknown pile 'loot graveyard'` |
| `{"deck_top": {"deck": "loots"}}` | accepts | `UnknownTargetError: unknown deck 'loots'` |
| `{"target_player": {"most": "fingers"}}` | accepts | `UnknownTargetError: cannot count 'fingers'` |
| `{"target_player": {"count": "two"}}` | accepts | `ValueError: invalid literal for int()` |
| `{"target_deck_card": {"from_top": "five"}}` | accepts | `ValueError: invalid literal for int()` |
| `{"target_deck_card": {"card_type": "tresure"}}` | accepts | **nothing — matches no card, silently** |
| `{"target_curse": {"owner": "opponents"}}` | accepts | **nothing — the word is ignored** |
| `{"player": {"value": "one"}}` | accepts | **nothing — returns no player** |
| `{"target_player": {"exclude_dead": true}}` | accepts | **nothing — the key is dropped** |
| `{"target_treasure": {"of": "someone"}}` | accepts | **nothing — the key is dropped** |

Six stop the game mid-study, naming no card and no file. Five never complain
at all: the card simply does something other than what it says, for as long as
anybody plays it.

### 2.4 Two shipped cards are in the second group

The dry run found them, and a live game confirmed them.

`_target_treasure` narrows its list with `owner`. It does **not** read `of` —
that is `_owned_treasure`, through `_holders`. Two cards write `of` on
`target_treasure`:

```
  seat 0 holds: Sibling Rivalry      seat 2 holds: Wooden Nickel
  seat 1 holds: The Real Left Hand   seat 3 holds: Rusty Spoons

  owned_treasure  of=unlucky : [The Real Left Hand@1]
  target_treasure of=unlucky : [Sibling Rivalry@0, The Real Left Hand@1,
                                Wooden Nickel@2, Rusty Spoons@3]
```

**Monstro's Tooth** — "At the start of your turn, choose a player at random.
That player destroys an item **they control**." The random player is asked
(`chooser` works, it is `_ask`'s), but they are offered every item on the
table, including the controller's.

**Finger** — "swap a non-eternal item you control with a non-eternal item
**they control**." The second half offers everything, so the swap can pair a
player's item with their own.

Neither raises. Neither ever has. This is the strongest argument for doing the
work at all, and it is also the reason the work cannot be shipped alone — see
§6.

### 2.5 One parameter, two meanings

The audit flagged `owner`; a full pass found `of` is worse.

**`owner`** — `_all_treasures` reads `controller` and `opponents`.
`_target_curse` tests only `== "controller"` and treats anything else as
"every curse on the table". Two domains for one word, differing by target.

**`of`** — four readings, and one of them is not a reference at all:

| read by | serving | means |
|---|---|---|
| `_named_players` | `target_loot`, `target_soul` | a bound group of players, **or the literal `"all_players"`** |
| `_holders` | `owned_treasure` | a bound group of players, **or the literal `"all_players"`** |
| `_holder` | `holder` | a bound group of cards |
| `_group` | `group`, `most_common` | one bound name, or a list of them |
| `_random_loot` | `random_loot` | a bound group of players |
| — | `target_treasure` | **nothing. Silently dropped.** |

The magic value `"all_players"` alone rules out any generic "`of` is a
reference" rule, and the last row rules out treating `of` as a property of
the word rather than of the target.

**`count`** — `_ask` means "how many to choose"; `_deck_top` means "how many
off the top". Same kind, different floor.

Conclusion, and it is the whole architectural point: **a parameter's meaning
belongs to the target, not to the key.** A table of keys would have been
wrong in three places.

## 3. Classification of the 23 keys

| class | keys | checkable before a game |
|---|---|---|
| flags | `include_dead`, `exclude_controller`, `exclude_attacked`, `exclude_eternal`, `exclude_source`, `include_shop` | yes |
| whole numbers | `count`, `minimum`, `maximum`, `from_top`, `value`, `player` | yes, with floors |
| free text | `as`, `prompt`, `tag`, `counter`, `named` | kind only |
| closed domains | `deck`, `pile`, `card_type`, `exclude_type`, `most`, `owner` | yes |
| lists over a domain | `kinds`, `triggers` | yes |
| **references** | `of`, `chooser`, `exclude` | **no — out of scope, §8** |

### Where each domain comes from

The rule inherited from conditions is that a domain must be read from the code
that enforces it, never written a second time. Five of the six hold:

| domain | source | one fact? |
|---|---|---|
| `deck`, `pile` | the `GameState` attributes `getattr(state, f"{deck}_{pile}")` already reads — `{loot, treasure, monster, room} × {deck, discard}`, all eight present | yes |
| `most` | the keys of `_COUNTABLE`, the table that performs the counting | yes |
| `card_type`, `exclude_type` | `CardType`, the enum the comparison is against | yes |
| `kinds` | `StackItemType` | yes |
| `triggers` | `EventType` — already carried as `Vocabulary.triggers` | yes |
| **`owner`** | two string literals inside two functions | **no** |

`owner` is the exception and must be written by hand — two words, beside the
comparison that performs them, once per target because the two targets differ.
That is the same discipline `_COMPARISONS` follows; it just cannot be iterated.

## 4. Proposed architecture

Identical to conditions, which is the point. Nothing new is introduced.

```
target_resolver.py          content/vocabulary.py        cards/validator.py
  helper reads a param        TargetShape (plain data)      checks a card
  shape declared beside it  →   ParamShape, reused       →   against names
  named on the register line     no functions cross            and shapes
                                        ↑
                            runtime/vocabulary.py
                        the one module that sees both
```

- **`runtime/target_resolver.py`** — a parameter set per helper, declared next
  to the helper; one universal set (`as`) next to `resolve_all`; `register`
  gains a third argument; a `shapes()` accessor. About nine constants and one
  argument on 46 existing lines.
- **`content/vocabulary.py`** — a `TargetShape`, reusing `ParamShape`
  unchanged. One new field on `Vocabulary`, one accessor.
- **`runtime/vocabulary.py`** — carries them across, as it already does for
  effects and conditions.
- **`content/loader.py`** — one more argument threaded through.
- **`cards/validator.py`** — parameters checked where names are already
  checked. A spec whose name is an ability's own alias is skipped, exactly as
  today.

### The boundary (point 7)

**No runtime import is required in the loader, and none is proposed.** The
loader receives `TargetShape` objects: strings, tuples of strings, integers
and booleans. No `TargetFn` crosses. `runtime/vocabulary.py` remains the only
module that holds both sides, which is what it exists for.

Two domains come from outside the resolver — `CardType` from `fsme.cards.types`
and `StackItemType` from `fsme.stack.item`. Both packages import nothing but
`fsme.util.errors`, so neither creates a cycle, and both give up plain strings
at the boundary.

### The one place the resolver's own logic would change

`deck` and `pile` are concatenated into an attribute name and validated by
whether `getattr` found something. Deriving the domain from those same
attributes keeps it one fact and touches no logic — verified: the eight
combinations `{loot, treasure, monster, room} × {deck, discard}` all resolve,
and no others exist. **Recommended: derive, change nothing.** The alternative —
naming the tuples and making the runtime check consult them — reads better but
creates the second table this whole approach exists to avoid.

## 5. Scope of v1

**In.** Parameter names; parameter kinds; closed domains; floors where a
number below them cannot mean anything (`from_top` of 0 is not a search).

**Out, deliberately.** Whether a target finds anything on the table; how many
objects it returns; the type or structure of what it returns; whether a named
card or player exists in the current state. All of those need a board, and a
description that guessed at them would be a second resolver. The resolver's
own guards stay exactly where they are: validation refuses *earlier*, never
*instead*.

**Out, and deferred to a named future stage.** `of`, `chooser`, `exclude` —
see §8.

## 6. Risk: would this refuse content that exists?

This was measured before anything was proposed, on the whole of `content/`:

```
target parameters seen                : 870
values type-checked under the proposal: 385
specs skipped as an ability's own alias: 103
distinct (target, key) pairs exercised : 103
complaints                             : 2
```

The two complaints are Monstro's Tooth and Finger from §2.4. **They are not
false positives. They are the bugs.**

Which produces the one real consequence for planning: **turning on target
validation stops `content/` from loading until those two cards are fixed.**
There is no third option — accepting `of` on `target_treasure` would mean
describing a parameter the engine ignores, which is exactly the lie this layer
exists to prevent.

So the work has to be sequenced, and the middle step is not free:

1. Fix the two cards (`of` → `owner`, or give `target_treasure` `of` through
   `_holders` — a rules question, not a validation one).
2. **Re-take the thousand-game baseline.** Both cards will now offer different
   lists, so any recorded game in which either resolves will legitimately
   diverge. The difference has to be attributed to the fix rather than waved
   through — a diff of "0 of 1000 changed" is not available here and claiming
   it would be false.
3. Then the validator, which must again leave the new baseline untouched.

Second risk, smaller and worth stating: thirteen targets are never used by any
shipped card, so their descriptions rest on reading the code with nothing to
check them against. A description that is wrong there refuses a custom card
for no reason, and no test in `content/` would catch it. Mitigation is to
describe those thirteen conservatively and to resolve each of them once in a
test with the parameters its description claims.

## 7. Test plan

1. **Every target says what it takes.** No target may be registered
   undescribed — the same test conditions have, and for the same reason: if a
   target can be added without a description, the descriptions are a separate
   table again.
2. **Domains are read, not restated.** `most` against `_COUNTABLE`, `deck` and
   `pile` against the `GameState` attributes the resolver reads, `card_type`
   against `CardType`, `kinds` against `StackItemType`. Asserted by identity,
   not by listing the values a second time.
3. **All of `content/` still loads and plays** — the test that matters, after
   the two cards are fixed.
4. **Each of the eleven cases in §2.3 is refused before a game**, and the
   error names the expansion, the file, the card, the ability and the path.
5. **A spec naming a group the ability bound is not looked up** — 103 in
   shipped content, and none of them is a target.
6. **A target whose parameters no shipped card writes still resolves** with
   the parameters its description claims — the mitigation for §6's second
   risk.
7. **A target registered without a description is not judged**, and that
   silence is not read as permission.
8. **The thousand-game baseline is unchanged by the validator itself**, taken
   after the content fix and before the validator, so the two effects cannot
   be confused.

## 8. Deliberately deferred

**Target Reference Layer.** `of`, `chooser` and `exclude` name a group bound
elsewhere in the same ability. Checking them means resolving an ability's
alias graph: which targets bind which names, in what order, and whether a
reference points at something bound before it is read. That is a real analysis
with its own failure modes, and it also has to accommodate `"all_players"` —
a literal that is not a reference at all, accepted by `_named_players` and
`_holders` and by nothing else. In v1 these three are marked as taking a bound
group and are not checked.

**What a target returns.** Type, count, and whether the board can supply one.
Runtime's business, and §5 says why.

**`tests/test_desk.py::test_a_job_that_fails_says_so`.** A pre-existing race
in `lab/desk/bench.py` — `job.state` is set before `job.error`, so a poll can
land between them. Unrelated to targets; a separate task.
