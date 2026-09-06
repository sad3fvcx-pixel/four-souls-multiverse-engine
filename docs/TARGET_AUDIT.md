# Targets, and what may be checked before a game

A study, not a change. Nothing in this document was implemented; what it
recommends is written down so it can be argued with before it is built.

The question is narrow. Effects say what they take in their own signatures and
were checked first. Conditions do not, and were checked second by describing
their parameters beside the helpers that read them. Targets are the third and
last of the three vocabularies a card writes in, and this asks whether the
same thing works for them, or whether targets are different in a way that
should stop it.

---

## 1. What is there

46 registered names, backed by 42 functions — four names are aliases
(`source`/`self`, `current_player`/`active_player`, `monster`/`current_monster`,
`another_player`/`opponents`). Every one has the same signature:

```python
TargetFn = Callable[[GameState, AbilityContext, Mapping[str, Any], RNG], list[Any]]
```

So there is nothing to introspect, exactly as with conditions. Reading the
source instead:

| | targets |
|---|---|
| read parameters in their own body | 15 |
| read them only through a helper | 13 |
| read none at all | 18 |

The helpers are few and shared: `_ask` (11 targets), `_all_monsters` (5),
`_all_treasures` (3), `_stack_items` (2), `_named_players` (2), `_group`,
`_holders`, `_with_the_most`.

This is the same shape conditions had, and it is why the same answer applies:
a parameter is understood by the helper that reads it, so the helper is where
it should be described, and each target names the set it inherits on the line
it is already registered on.

**One warning from the measurement.** An automatic extractor was tried and it
missed `chooser`, because `chooser` is read by `_chooser`, which is called by
`_ask`, which is called by the target — two levels down. It was found by
reading the cards instead, which said `chooser` eight times. An extractor that
must follow a call graph is not a source of truth; it is a second
implementation of one.

## 2. What cards actually write

922 target specifications across `content/`: 558 bare names, 364 objects.
None uses the `{"target": ...}` form, though the resolver accepts it.

23 parameter keys in all, and their types are almost perfectly uniform:

| key | uses | written as |
|---|---|---|
| `as` | 358 | text |
| `deck` | 98 | text — `loot`, `treasure`, `monster`, `room` |
| `count` | 42 | whole number |
| `from_top` | 36 | whole number |
| `prompt` | 36 | text |
| `exclude_eternal` | 36 | flag |
| `exclude_controller` | 32 | flag |
| `minimum` | 28 | whole number |
| `of` | 28 | text (20) or a list of text (8) |
| `maximum` | 26 | whole number |
| `owner` | 20 | text — `controller`, `opponents` |
| `exclude_source` | 16 | flag |
| `pile` | 10 | text — `discard` |
| `chooser` | 8 | text |
| `tag` | 8 | text |
| `exclude_attacked` | 6 | flag |
| `exclude` | 6 | text |
| `triggers` | 4 | list |
| `most` | 4 | text — `souls`, `coins` |
| `exclude_type` | 4 | text |
| `counter` | 2 | text |
| `include_shop` | 2 | flag |
| `named` | 2 | text |

70 distinct (target, key) pairs. Only `of` is written two ways, and both are
correct: one name or several.

## 3. Why targets are harder — and where they are not

Three of the four differences usually given turn out not to be differences.

**Not harder: the parameters.** They layer through shared helpers exactly as
conditions do, and their types are as uniform. `target_treasure` reads eleven
keys, but five of them are `_ask`'s and six are `_all_treasures`'s, and both
sets are written once.

**Not harder: the closed domains.** They are, if anything, more closed than
conditions'. `_COUNTABLE` has four keys. `deck` and `pile` are concatenated
into a state attribute name — `f"{deck}_{pile}"` — and an unknown one raises
`UnknownTargetError` *during the game*. `{"target_deck_card": {"deck":
"tresure"}}` is a card that loads cleanly, plays for two hundred moves and
then stops the study. That is the same story the effect validation was built
for, and the same eight decks and piles are already named in `GameState`.

**Not harder: what a target returns.** A target may return nothing — an empty
monster row, a player with no items — and it is tempting to call that
uncheckable. It is not a validation question at all. A card that says "destroy
an item another player controls" when nobody has one is a correct card in a
board state where it does nothing, and the rules say so.

**Genuinely harder: a target name is not always a target.** `resolve` looks in
`context.targets` *before* the registry, so a spec may name a group some
earlier target bound with `as`. `{"target": "victim"}` is legal and `victim`
is in no registry and never will be — it belongs to one card. Nothing in the
effect or condition vocabularies has this property.

The validator already handles it: `_declared_target_names` and
`_effect_aliases` gather the names an ability binds, and a name is accepted if
it is either registered or bound. So the hard part is solved; it was solved
before this audit.

**Genuinely harder, and unsolved: three keys are references, not values.**
`of`, `chooser` and `exclude` name a group bound elsewhere in the same
ability. Checking them is a different question from checking a type — it asks
whether the ability binds that name — and it is the one target check with no
analogue anywhere else.

**One thing found while measuring.** `owner` means two different things.
`_all_treasures` reads `controller` and `opponents`; `_target_curse` reads
only `controller` and silently treats `opponents` as "everybody". No shipped
card writes it, so nothing is wrong today. It is an argument against a table
of keys and for a table of targets: the domain of `owner` is not a property of
the word.

## 4. The three options

**A — runtime only.** Leave targets unchecked outside a game; the resolver
already raises on everything it cannot do.

Cheapest, and wrong for the same reason it was wrong for effects. The
resolver's guard fires in the middle of somebody's game, names no card, no
file and no field, and only for the paths that game happened to take. A
custom set of forty cards can be loaded, played a thousand times and still
have a target nobody reached.

**B — a TargetShape, on the same terms as ConditionShape.** Describe
parameters beside the helper that reads them; name the set on the line each
target is already registered on; hand the descriptions over as plain data
through `Vocabulary`, as effects and conditions already are.

Cost: about nine shape constants and one extra argument on 46 existing lines.
No new file in the pipeline, no new concept for a card author, no second
table — the operators, the countables, the decks and the card types are all
read from the tables that already perform them.

**C — describe some targets and not others.** Cover the ones with obvious
parameters and leave the rest open.

This is the worst of the three. A partial description is indistinguishable
from a complete one at the point of use, so an author cannot tell whether a
target accepted their parameter or merely had no opinion. Conditions avoided
this by describing all forty-one, and a test asserts that a condition cannot
be registered without a description.

## 5. Recommendation

**B**, with its scope stated exactly, because the danger in B is that it grows.

Describe: the parameters, their kinds, their closed domains, and their
minimums. That is what the helpers already know.

Do **not** describe: what a target returns, how many it returns, what type of
object it returns, or whether the board can supply one. Those need a game, and
a description that guessed at them would be a second resolver — the thing this
must not become.

The reference keys — `of`, `chooser`, `exclude` — are a separate, later
question. They should be marked as taking a bound group and left unchecked at
first, because checking them properly means resolving the alias graph of an
ability, and that deserves its own decision rather than being smuggled in.

## 6. What would change, and what must not

Changes:

- `runtime/target_resolver.py` — shape constants beside the helpers; `register`
  gains a third argument; a `shapes()` accessor. Mirrors the condition change
  exactly.
- `content/vocabulary.py` — a `TargetShape`, plain data, reusing `ParamShape`.
- `runtime/vocabulary.py` — carries them across, as it does the other two.
- `content/loader.py` — one more argument threaded through.
- `cards/validator.py` — parameters checked where target *names* are already
  checked. The traversal exists.
- `docs/CARD_SCHEMA.md` — the fourth tier described alongside the other three.

Must not change:

- **The card format.** Every spelling the resolver accepts today stays
  accepted. 922 target specifications in `content/` are the test of that.
- **What official content does.** The thousand-game record is the measure, and
  it must come back identical.
- **Determinism.** Nothing here runs during a game. The resolver's own guards
  stay exactly where they are; validation refuses earlier, it does not refuse
  instead.
- **The plain-data boundary.** The loader must not import the resolver or hold
  a `TargetFn`, for the same reason it holds no effect and no condition.

## 7. How it would be tested

1. Every target the engine ships says what it takes — no target may be
   registered undescribed, or the descriptions are a separate table again.
2. Every one of the 922 target specifications in `content/` still passes, and
   the whole of `content/` still loads and plays.
3. A card whose target parameter is wrong before a game is refused before a
   game: `{"target_deck_card": {"deck": "tresure"}}`, `{"target_player":
   {"count": "two"}}`, `{"most_common": {"most": "fingers"}}`.
4. A card whose target names a group bound by another target still loads —
   the alias is not a target and must not be looked for in the registry.
5. A target registered without a description is not judged, and that silence
   is not read as permission.
