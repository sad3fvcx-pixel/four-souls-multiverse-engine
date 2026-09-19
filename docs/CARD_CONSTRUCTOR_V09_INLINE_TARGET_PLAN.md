# Inline targets and bound groups — what the residual difference actually is

Analysis only. Nothing was committed, nothing was pushed. `tests/`, `content/`
and the previous analysis documents were not modified. The uncommitted
one-line reader change is still in the working tree, and this document assumes
it: measurements are labelled *before* or *after* it where the distinction
matters.

**Short answer, and it overturns the premise this stage was set up on: the
inline/bound distinction is not the cause of the 12 remaining replay
differences, and no new author-state representation is required.** The
reader change already in the tree is the whole of the semantic fix. The 12
differences come from somewhere else entirely, measured in §6.

A second, separate instance of the *original* hoist defect was found while
answering Task 5, and it is not fixed by the reader change. It is in §4.


## 1. The runtime distinction

Measured directly against `TargetResolver`, with a stub `AbilityContext` and a
target that answers differently every time it is asked. No game, no bot.

| case | what was asked | result |
|---|---|---|
| **A** — the same inline target used by two steps | `resolve("changing")` twice | `answer#1`, `answer#2` — **independent** |
| **B** — one bound group used by two steps | bind as `x`, then `resolve("x")` twice | `answer#1`, `answer#1` — **shared** |
| **B2** — two step-local bindings of the same target | bind as `chosen_1`, bind as `chosen_2` | `answer#1`, `answer#2` — **independent** |
| **C** — an inline target after the ability bound the *bare name* | bind `{"changing": {}}`, then inline `changing` | `answer#1` — **memoised** |
| **D** — an inline target where the ability bound it under an alias | bind as `alias`, then inline `changing` | `answer#2` — **independent** |
| **E** — `resolve_all` twice on one alias | bind `y` twice | held; not re-asked |

The mechanism is two lines of the resolver. `resolve` looks in the context's
cache under both the alias and the target's own name:

```python
for key in (str(params.get("as", name)), name):
    bound = context.targets.get(key)
    if bound is not None:
        return list(bound)
```

and `resolve_all` refuses to re-bind an alias it already holds — deliberately,
so an ability that stopped to ask a question finds the answer when it resumes
rather than asking again.

So the distinction is real: **a bound group is resolved once and memoised for
the ability's context; an inline target is resolved afresh wherever it is
used.** It is not specific to `self` — it applies to any target whose answer
can differ between askings, which is every target that consults game state,
asks a player, or uses the RNG.

**But B2 is the row that decides this stage.** The Constructor does not turn
two inline uses into one shared group: it mints a *distinct* name per site
(`chosen_1`, `chosen_2`). Distinct aliases are resolved independently, and a
step's own `targets` are resolved by `resolve_all(op.asks, …)` in
`EffectExecutor._execute` immediately before that same op's target is
resolved — the same moment the inline form would have been. **Same
independence, same timing.** A step-local binding is therefore semantically
equivalent to the inline target it came from.

Case C is worth recording as pre-existing runtime behaviour that has nothing
to do with the Constructor: a card that binds a target under its bare name at
ability level silently memoises every later inline use of that name. No
shipped card does it; nothing here proposes changing it.


## 2. Where the reader conflates the forms

`_read_step` (`src/fsme/lab/desk/author.py`) handles an aim three ways:

| what the card wrote | what the reader records | binding placed |
|---|---|---|
| an aim written out in full, `{"target_player": {…}}` | `aim_chosen_by = BY_THE_STEP` | on the step |
| a name the ability or an earlier step bound | `aim_chosen_by = bound[aimed][2]` | wherever that was |
| **a bare engine-target name, `"self"`, `"target_loot"`** | **was `BY_THE_ABILITY`** | **at the ability root** |

`_written_step` passes that value to `_Chosen.named` as `level`, and `named`
writes into the step's own list when it is `BY_THE_STEP` and into the
ability's root otherwise.

The third row is the defect the final audit found. The uncommitted change makes
it `BY_THE_STEP`, which is what the card meant: the aim was written where it is
used. `_read_control` has always refused to fold a control node's aim up to the
ability — *"Folding that up to the ability would change which steps it
reaches"* — so the codebase already held the principle; it simply was not
applied to effect steps.

**With that change, every reader path sets `aim_chosen_by` explicitly.** That
matters in §4.


## 3. Author state — can it already represent an inline target?

**It does not need to, and that is the answer to Task 4.** §1 case B2 shows the
step-local binding the reader now produces is semantically the inline target.
Nothing is lost, so nothing needs a new representation.

Asked literally — *could* author state carry "inline, unbound"? Partly, and it
would cost more than it buys:

- `_written_step` reads `described["target"]` and writes it verbatim when there
  is no `aim`. Given author state carrying `{"id": "destroy_treasure",
  "target": "self"}` it emits `{"effect": "destroy_treasure", "target":
  "self"}`, checker-clean. So **the writer has a latent path** and no writer
  change would be needed.
- But `aimHtml` draws the aim control from `step.aim`. A step with a plain
  `target` and no `aim` shows **no aim control at all**: the author could not
  see or change what the effect is aimed at. Preserving the spelling would cost
  the editability of 179 target sites.

So the existing state is sufficient for meaning and insufficient for editing,
and since meaning is already preserved, the trade is not worth making.
**No new author-state field is required.**


## 4. `setAim` — the exclusion is no longer justified

`setAim` is four lines: choosing a target writes `step.aim` and empty
`aim_fields` / `aim_groups`; clearing deletes all three. The page never
mentions `aim_chosen_by` anywhere.

`aim` is **not** overloaded. It means "what this step is aimed at". Who binds
it is a separate field, `aim_chosen_by` — and `setAim` never writes it.
`_written_step` therefore falls back to its default:

```python
str(described.get("aim_chosen_by", "") or BY_THE_ABILITY)
```

Measured, building a card from author state exactly as the page would leave it:

| author state | ability.targets | where the binding went |
|---|---|---|
| a new aim on a step at the ability's top level | `[{"target_loot": {"as": "chosen_1"}}]` | ability |
| **a new aim on a step inside a `then` branch** | `[{"target_loot": {"as": "chosen_1"}}]` | **ability — hoisted** |
| the same, with `aim_chosen_by` set to `step` | `null` | the step, inside the branch |

**So a card authored in the Constructor still hoists.** The reader change fixes
cards read off disk; a card typed in from scratch reproduces the original
defect exactly, because the default says the ability chose it.

This is the same defect, reached by the other door, and it is the reason the
previous brief's exclusion of `setAim` no longer holds.

The smaller of the two available corrections is not in `setAim` at all: since
the reader now always sets `aim_chosen_by`, the writer's default governs
**only** newly authored aims, and the correct default for an aim written on a
step is the step. Changing that default fixes every producer of author state at
once; changing `setAim` fixes only the page.

Nothing is lost either way: the page has no control for `ability.targets` — a
person cannot author one today — and a card read off disk keeps its
ability-level targets through `bound[aimed][2]`.


## 5. The corpus, classified

Every target occurrence in the 1045 shipped cards, at HEAD `6d68f96`:

| form | count |
|---|---|
| genuine ability-level targets (`ability.targets` entries) | 98 |
| names pointing at a group the ability bound — at a step's top level | 77 |
| names pointing at a group the ability bound — inside a branch | 8 |
| names bound by an earlier step in the same body | 18 |
| targets already written as explicit step-local `targets` | 24 |
| **inline bare target name — at a step's top level** | **128** |
| **inline bare target name — inside a branch** | **51** |
| inline target written out in full — at a step's top level | 12 |
| inline target written out in full — inside a branch | 48 |
| inline bare target name inside a `watch_for` body | 1 |

The 179 inline bare names are the form the reader used to hoist. After the
change they become minted step-local bindings: **136 cards, 172 sites** —
the same figures the final audit reported, re-measured here.

Replay, 200 games at 4 players, against an untouched copy of `content/`:

| corpus | differing |
|---|---|
| control | 0 / 200 |
| rewritten, before the reader change | 58 / 200 |
| **rewritten, after the reader change** | **12 / 200** |

Content is unaffected by the change: 1045/1045 readable, 1045/1045 stable,
352/352 checker-clean, 1014 editable, 31 view-only, 0 refused at read — before
and after.


## 6. The 12 residual differences

**All 12 have one cause, and it is not the Constructor.**

They were traced to `src/fsme/lab/bot/appraisal.py`:

```python
def _destroys_itself(ability: bool) -> bool:
    return any(
        isinstance(entry, Mapping)
        and entry.get("effect") == "destroy_treasure"
        and entry.get("target") == "self"
        for entry in _everywhere(ability.effects)
    )
```

It matches the **literal string** `"self"`. When the reader correctly makes the
target a step-local binding, `target` becomes `chosen_2`, the check returns
`False`, and `_uses` prices the card as reusable instead of once-only. The bot
then buys and plays it differently.

Eight shipped cards are affected, and the mispricing is tenfold:

| card | ability | `_uses` before | after |
|---|---|---|---|
| `treasure_deck-active_items-base_game-glass_cannon` | 0 | 1.0 | 10.0 |
| `treasure_deck-one_use_items-base_game-box` | 0 | 1.0 | 10.0 |
| `treasure_deck-one_use_items-base_game-chaos_card` | 0 | 1.0 | 10.0 |
| `treasure_deck-one_use_items-base_game-mom_s_shovel` | 1 | 1.0 | 10.0 |
| `treasure_deck-one_use_items-base_game-the_d4` | 0 | 1.0 | 10.0 |
| `treasure_deck-one_use_items-mewgenics-mini_nuke` | 1 | 1.0 | 10.0 |
| `treasure_deck-passive_items-retro-1_up` | 0 | 1.0 | 5.0 |
| `treasure_deck-soul_item-base_game-pandora_s_box` | 0 | 1.0 | 10.0 |

Proved two independent ways, both on the 12 differing seeds
(0, 15, 34, 49, 58, 61, 63, 81, 100, 117, 141, 187):

| experiment | differing |
|---|---|
| rewritten corpus, unmodified bot | 12 / 200 |
| rewritten corpus, **bot's check made spelling-insensitive** | **0 / 200** |
| rewritten corpus, **those 8 cards left spelled as the card wrote them**, unmodified bot | **0 / 200** |

And with the same spelling-insensitive bot, the **pre-change** corpus still
differs in **58 / 200** — so the hoist was a genuine runtime defect all along,
undiluted, and the reader change closes all 58 of it.

| card | construct | original | rewritten | semantic cause |
|---|---|---|---|---|
| the 8 above | `destroy_treasure` aimed at `self` | `"target": "self"` | `"target": "chosen_N"` + a step-local binding | **none in the engine** — identical resolution, identical timing; the difference is a bot heuristic reading card JSON by literal shape |

So the replay oracle the final audit used has a blind spot: it measures the
engine *and the bot together*, and the bot reads card text. That does not
weaken the audit's finding — the 58 were real — but it means "0 differing"
cannot be reached while a heuristic pattern-matches on a spelling the
Constructor is entitled to change.

**This is not a Constructor defect and is not proposed for fixing here.** It is
recorded as a separate, pre-existing fragility in `fsme.lab.bot`.


## 7. The minimal required representation

**None.** §1 case B2 and §3 between them show the existing representation is
both sufficient and correct. The only thing missing is a **default**: §4.


## 8. Classification

Against the stage's own categories:

- **A — reader bug.** Yes, and it is the whole of the semantic problem. Author
  state already distinguished the forms through `aim_chosen_by`; the reader
  filled it in wrongly for one of its three paths. Fixed by the change in the
  tree.
- **A again, second instance — the writer's default.** `setAim` leaves
  `aim_chosen_by` unset and `_written_step` defaults to the ability, so newly
  authored branch targets hoist. Same bug, different door. **Not yet fixed.**
- **B — author-state representation gap.** No. §3.
- **C — UI/editor representation gap.** No. The page needs no new control; it
  never had one for `ability.targets` and does not need one now.
- **D — language/model concept.** No. Nothing new is published, nothing in the
  vocabulary changes.
- **E — writer-only issue.** Only in the narrow sense of §4's default, which is
  one line and is better described as the same reader-side bug.

Dependency: the §4 default matters only because the reader now always sets
`aim_chosen_by` explicitly. Before the reader change the default was
indistinguishable from the bug; after it, it is the last place the wrong answer
is still produced.

Separately, and outside all five categories: the bot heuristic of §6.


## 9. Proposed implementation boundary

| | change? | why |
|---|---|---|
| **reader** (`_read_step`, third aim path) | **yes — already in the tree** | the defect itself |
| **writer** (`_written_step`'s `aim_chosen_by` default) | **yes — one line** | otherwise newly authored branch targets still hoist |
| author state | **no** | already sufficient — §3 |
| `setAim` | **no** | the writer default covers it, and covers every other producer of author state too |
| tests | **yes** | §10 |
| browser | **yes** | §11 |
| runtime | **no** | nothing about resolution changes |
| the bot | **no** | §6, separate and pre-existing |
| `NEW_SCOPE`, `BRANCHES`, binding semantics, `rewards`, open mappings, `when`, `DRAWS`, Guided Walk | **no** | untouched |

So the stage is two lines in one file, plus tests and a browser check.


## 10. Required regression tests

Focused, not corpus-wide:

- **A** — `pills-v2`: read and written with no edit keeps no `ability.targets`,
  and the binding stays on `discard_cards` inside `then`.
- **B** — a synthetic branch-local target stays nested.
- **C** — an ordinary inline target at a step's top level stays on the step.
- **D** — a genuine `ability.targets` entry read off a card is still written
  back at ability level.
- **E** — a target two branches deep stays where it was.
- **F** — the `NEW_SCOPE` case from `6d68f96` still holds.
- **G** — **a newly authored aim inside a branch is written inside that
  branch**, built from author state shaped exactly as `setAim` leaves it, with
  no `aim_chosen_by`. This is the §4 case and nothing else covers it.
- **H** — a minted name stays stable across repeated round-trips.

`test_a_name_this_invented_is_not_taken_for_the_card_s_own` asserts the minted
binding lands in `abilities[0].targets`. Its real invariant — that a made-up
name is stable and does not escalate — still holds (verified idempotent over
three round-trips). Only its assertion about *where* is out of date, and it
needs the same kind of update `test_a_step_inside_a_body_is_not_aimed_here`
received in `6d68f96`.


## 11. Browser verification

- `pills-v2`: open, change nothing, save, reopen — no page error, `problems=[]`,
  no `ability.targets`, the binding inside the branch.
- One card with genuine ability-level targets: still ability-level.
- One `watch_for` case and one `may` case: unchanged from `6d68f96`.
- **Authoring, not just opening**: build a card in the page with an `if`, put a
  target on a step inside `then`, save, and read the file back. This is the
  §4 case and it cannot be reached by opening an existing card.


## 12. Non-goals

- Not fixing `fsme.lab.bot.appraisal._destroys_itself` (§6). Recorded only.
- Not changing runtime resolution, memoisation, or `resolve`'s bare-name cache
  lookup (§1 case C).
- Not adding an author-state field for "inline, unbound" (§3, §7).
- Not adding a UI control for `ability.targets`.
- Not modifying `setAim` (§9).
- Not touching `NEW_SCOPE`, `BRANCHES`, `rewards`, open mappings, `when`,
  `DRAWS`, or the Guided Walk.
- Not modifying `CARD_CONSTRUCTOR_V09_FINAL_AUDIT.md`, which remains an
  accurate record of the state before the fix. Its one figure that this
  document refines is the composition of the 58: they are all genuine, and the
  path from 58 to 0 runs through the bot as well as the reader.


## 13. What to do with the change in the tree

**Keep it, and finish it in the same commit** — option A of the three offered,
not C.

It is correct, it is regression-free (0 games newly differing), and it closes
all 58 genuine differences. But on its own it leaves the §4 door open, and a
commit that fixes opening a card while leaving authoring one broken would be a
worse thing to land than either half. The writer default is one line and shares
every test in §10, so there is nothing to gain by splitting them.

Splitting would also make test **G** homeless: it fails before the writer
default changes and passes after, so it cannot go in a reader-only commit.
