# Step-local bindings — the placement defect, located

Analysis only. Nothing in `src/`, `tests/` or `content/` was changed, nothing
was committed, and no existing document was modified. Measured at `38abc34`.
Scratch probes were run and removed.

## 0. Two corrections to the premise, and a filename conflict

**The brief's figures predate a commit that is an ancestor of HEAD.**
`b021e94` — *"Let a step keep what it picks out for itself"* — landed step-local
bindings as Variant B. Re-measured at `38abc34`:

| the brief says | measured now |
|---|---|
| 179 bindings; 98 preserved, 57 name discarded, **24 refused** | **122 bindings; 0 refused** |
| A 12 / B 26 / C 102 / D 0 | 109 bound at the ability, 13 bound inside an arm |
| `incubus`, `famine`, `viii_justice`, `the_d4` are refusals | all four read, mean the same, and are checker-clean |
| step-local bindings are the largest remaining semantic class | **352 of 352 rules-carrying cards are clean**; nothing is refused |

**`docs/CARD_CONSTRUCTOR_V09_STEP_BINDINGS_IMPLEMENTATION_PLAN.md` already
exists** and was committed with `b021e94`'s stage. Task 11 asks for that path;
writing it would modify an existing analysis document, which the same brief
forbids. This document takes a non-colliding name and carries both the analysis
and the plan.

**There is still a real defect.** It is not the one the brief describes, it is
smaller, and §5 locates it to one line.


## 1. The binding lifecycle

One binding, traced end to end. Files and functions as they stand.

| stage | where | what happens |
|---|---|---|
| **card** | `content/**.json` | `{"target_player": {"as": "victim"}}` in an ability's `targets`, or in a step's own `targets` |
| **reader — ability level** | `author.py:1728`, `_bound_by` → `_binds(node["targets"], BY_THE_ABILITY)` | each binding recorded as `(kind, params, level)` |
| **reader — step level** | `author.py:1785`, `_read_step` → `_binds(written.pop("targets"), BY_THE_STEP)` | a step's own list is read the same way, marked as the step's |
| **reader — the use** | `author.py:1865–1914`, `_as_chosen` | the name is *resolved*: the step gets `aim`, `aim_fields`, `aim_groups`, and `aim_chosen_by` — the level the binding came from. **The name itself is discarded here** |
| **author state** | the step node | `{id, fields, aim, aim_fields, aim_groups, aim_chosen_by}`. No scope is stored, and no name |
| **editor** | `author.html::setAim` | writes `aim`, `aim_fields`, `aim_groups`. **Never writes `aim_chosen_by`** |
| **writer — gathering** | `author.py:1313`, `class _Chosen` | a stack of open lists; `holding()` pushes, `shut(mark)` pops |
| **writer — placement** | `author.py:1394` | `where = self._open[-1] if level == BY_THE_STEP else self._root` |
| **writer — the arm** | `author.py:998`, `_written_step` | a step's own list is attached as `node["targets"]` |
| **checker** | `cards/references.py::_walk` | validates visibility against `BRANCHES` and `NEW_SCOPE` |

The name is lost at `_as_chosen` and re-invented at `_Chosen.named` — as
`chosen_N` unless the card gave one. That is by design and was settled in an
earlier stage; it is why the round-trip comparison below is by *placement*
rather than by name.


## 2. The scope model, verified against the checker

Two rules, both declared in `cards/references.py`, both derived from the
runtime rather than assumed:

```python
BRANCHES = ("then", "else", "may", "choose", "modes", "effects")
# a name bound inside one is visible inside it and after it there, not outside

NEW_SCOPE = ("watch_for", "promise")
# "The runtime builds a fresh AbilityContext for a watcher when its event
#  arrives, so nothing this ability bound is there to be found."
```

`NEW_SCOPE` is the rule the brief does not mention and the one the defect turns
on. Entering such a body resets **both** namespaces (`references.py:314`):

```python
if _head(node) in NEW_SCOPE:
    self._walk(node.get("effects", ()) or (), {}, set(), f"{path}.effects")
```

The three shapes the brief asked for, measured:

| shape | checker | round-trip |
|---|---|---|
| bind X in arm A, use X in arm B | **refused** — *"'X' is bound, but not where this can see it"* | the refusal survives; the reader also declines |
| bind X at the ability, use X in both arms of a branch | **clean** | preserved at the ability level |
| bind X inside arm A, use X after the branch | **refused**, same message | refusal survives |

**The writer and the checker agree on `BRANCHES` and disagree on `NEW_SCOPE`.**
The writer has no notion of it at all.


## 3. Complete measured classification

122 bindings across 96 cards, at `38abc34`:

| category | count |
|---|---|
| 1. bound at the ability | **109** |
| 2. bound inside an arm | **13** |
| 3. used inside a nested branch | covered by 1 and 2; no case fails |
| 4. crossing a scope boundary | **0** in shipped content |
| 5. same textual name independently in different scopes | **0** shipped; synthesised in §6 |
| 6. created and consumed within one step | included in 2 |
| 7. name needed only for writing | the `chosen_N` case — every inline target |
| **currently refused** | **0** |

The thirteen bound inside an arm:

```
the_lamb  mourners  may        incubus   shown      choose/effects
ultra_greed spoils  may        incubus   mine_card  choose/effects/may
the_lost  woken     may        incubus   their_card choose/effects/may
rainbow_tapeworm model then    host_hat  bystander  effects
g_fuel    revived   may        dead_bird snatched   may
finger    mine      may        finger    theirs     may
the_habit revived   may
```

`incubus` reaches three levels deep and round-trips clean. `host_hat`'s
`bystander` sits inside a `watch_for` body — the only shipped binding inside a
`NEW_SCOPE`, and it is written there by the card and read back there.


## 4. The four proof cases

All four read, mean the same, rewrite stably and check clean.

| card | bindings, and where | outcome |
|---|---|---|
| `g_fuel` | `revived` at `may` | placement preserved; one `chosen_1` added at the ability for an inline target |
| `pestilence` | `first_point`, `second_point` at the ability | preserved; `divided` added for an inline target |
| `dead_bird` | `snatched` at `may` | preserved exactly, nothing added |
| `finger` | `mine`, `theirs` at `may`; `roller` at the ability | all three preserved at their own levels; `swap_pair` added at `may` — the correct arm |

**Every difference between the card as written and the card as rewritten is an
addition, never a relocation and never a loss.** The additions are inline
targets being given a name so a later step can point at them, which is the
documented `chosen_N` behaviour.

That answers the brief's concern directly: the writer does **not** treat the
same textual name across an ability as one binding. §6 measures it deliberately.


## 5. The remaining refusal set — none of them is refused

| card | state at `38abc34` | what it actually was |
|---|---|---|
| `incubus` | reads, means the same, clean | three-level arm-local bindings; fixed by `b021e94` |
| `famine` | clean | a *nested answer* problem — a name inside another answer — fixed by `188e36f` (`_named_inside`) |
| `viii_justice` | clean | same class as `famine` |
| `the_d4` | clean | same class; `rerolled_player` preserved at the ability |

None is a step-local binding problem, and none is refused. The brief's grouping
of these four with the binding work is stale.


## 6. The writer's collision behaviour

Synthesised, because shipped content has no case. Measured:

| case | result |
|---|---|
| **A** same name in sibling arms (`then` binds X, `else` binds X) | **independent**. Both written, both kept in their own arm, clean, stable |
| **B** bound at the ability, used in a nested arm | preserved at the ability level, clean |
| **C** inner shadows outer | **the language refuses it**: *"'X' is already bound by another target"*. The refusal round-trips faithfully |
| **D** two independent bindings, same name, sequential `may` arms | **not collapsed**. Both survive independently, clean, stable |
| **E** inner binding used outside its arm | refused by the checker; the reader also declines |

**No collision defect.** `_Chosen.named` searches `reversed(self._open)` —
innermost first — and only reuses a binding it finds in a currently open list,
which is why siblings stay independent.

One observation, not a defect: in case E the reader's message is *"aimed at
'X', which nothing on this card binds"* while the checker's is the more
accurate *"bound, but not where this can see it"*. Both refuse; one explains
better.


## 7. The defect

Aiming a step **inside a `watch_for` or `promise` body**. Measured, end to end:

| what author state says | ability-level targets | the checker |
|---|---|---|
| no note — *what the page produces today* | `[{"target_player": {"as": "chosen_1"}}]` | **refused** — *"'chosen_1' is bound, but not where this can see it"* |
| `aim_chosen_by = ability` | same | **refused**, same message |
| `aim_chosen_by = step` | *none* — written inside the body | **clean** |

For contrast, the same aim inside a `may` arm is **clean** with ability-level
placement, because `may` runs in the same ability resolution and the ability's
targets are there. Inside a `NEW_SCOPE` body they are not — the runtime builds
a fresh context.

**The line:**

```python
# author.py:1394, in _Chosen.named
where = self._open[-1] if level == BY_THE_STEP else self._root
```

`self._root` is the ability's list, unconditionally. Inside a `NEW_SCOPE` body
the root is **unreachable**, so ability-level placement is not a choice a card
can express there — and the writer offers it anyway and produces a card the
checker refuses.

**Reach**: six shipped cards have such a body — `compost`, `crystal_ball`,
`host_hat`, `mom_s_bra`, `polycephalus`, `two_of_clubs`. One aims inside it
(`host_hat`), and it is written correctly by the card, so **no shipped card is
affected**. The defect is reachable only by authoring: through the expert
editor, and now through the guided walk since `bff6cd0` made `watch_for`
finishable.


## 8. Minimum representation required

**None. Nothing new is needed, and the scope tree is not justified.**

The information already exists in three places:

- `NEW_SCOPE` — declared in `cards/references.py`, beside the checker that
  enforces it, with the runtime reason stated.
- `_Chosen._open` — the writer already tracks the stack of open lists, so it
  knows where it is.
- `aim_chosen_by` — already records who chose, and setting it to `BY_THE_STEP`
  already produces the correct card (measured, §7).

What is missing is that the writer never consults the first. `(name, arm)` is
not needed as an identity, because names are re-invented and arms are already
walked; explicit scope identity is not needed, because the stack is the scope.

**The minimum is: the writer must know that inside a `NEW_SCOPE` body, the root
is not a place a binding may go.**


## 9. Classification — **D, writer algorithm gap**

Against the brief's categories:

- **Not A.** `NEW_SCOPE` is declared and published where it is enforced.
- **Not B.** The reader represents it correctly — `host_hat` reads its
  `watch_for`-body binding as the step's.
- **Not C.** Author state is sufficient: `aim_chosen_by = step` yields a clean
  card with no other change.
- **D — yes.** All the information exists and `_Chosen.named` places the
  binding incorrectly, at one line.
- **Not E.** No new language concept. The semantics are already stated, in the
  docstring of the constant the writer ignores.

A secondary, smaller gap sits alongside it: `author.html::setAim` never writes
`aim_chosen_by`, so a person has no way to express step-level placement. Fixing
D makes that moot for `NEW_SCOPE` bodies — where the choice does not exist —
and leaves it open elsewhere, where ability-level placement is valid and is the
right default.


## 10. Round-trip invariants an implementation must satisfy

The brief's ten, plus three the analysis added:

1. binding names survive — where the card gave one
2. binding targets survive
3. same names in sibling scopes remain independent — **measured true today**
4. outer bindings remain visible to nested scopes
5. inner bindings do not escape their scope
6. independent bindings do not collapse when written — **measured true today**
7. a second rewrite is stable
8. existing ability-level bindings are unchanged — all 109
9. invalid scopes remain refused, with the same message
10. runtime semantics do not change

**Added by this analysis:**

11. **a binding inside a `NEW_SCOPE` body is never placed on the ability** —
    the defect itself
12. **`host_hat` keeps `bystander` inside its watched body** — the one shipped
    card that exercises the path
13. **placement is compared, not names** — the writer re-invents names, so any
    test asserting them will pass or fail for the wrong reason


## 11. v0.9 scope

| question | answer |
|---|---|
| shipped cards that would become editable | **zero** — 352 of 352 are already clean |
| refusal classes that would remain | none in shipped content; the three replacement effects stay out of the walk, which is a fact about them |
| runtime semantics changed | **none** |
| a new language concept | **none** |
| required by the v0.9 criterion | **no** — the criterion is that accepted cards round-trip, and every accepted card does. An invalid card is *refused*, not altered |

**It does not belong in v0.9 as a requirement.** It is a correctness fix worth
doing on its own merits: the editor can lead an author to a dead end where the
correct card is representable and unreachable through the interface.


## 12. Whether implementation is justified

**Yes, as a small isolated fix, and no, not as a v0.9 blocker.**

For: the defect is real, precisely located, produces an invalid card from a
supported flow, and the correct output is already reachable — measured — by
setting one existing field. `bff6cd0` widened the reach by making `watch_for`
finishable in the walk.

Against urgency: no shipped card is affected, nothing is corrupted, and the
checker refuses with an accurate message.


## 13. The plan

**Exact defect.** `_Chosen.named` (`author.py:1394`) places a binding on
`self._root` whenever the level is not `BY_THE_STEP`. Inside a body listed in
`NEW_SCOPE` the root is unreachable, and the resulting card is refused.

**Minimal representation.** None added. The writer reads `NEW_SCOPE` from
`cards/references.py`, which already declares it beside the checker.

**Reader.** No change. It already reads such a binding as the step's.

**Author state.** No change. `aim_chosen_by` already carries the level.

**Writer.** `_Chosen` learns that some open lists are boundaries — when
`_written_step` enters a step whose head is in `NEW_SCOPE`, the root is not
available below it, and a binding that would have gone there goes to the
innermost open list instead. Whether that is expressed as a flag on the
`holding()` push or as a second root is an implementation choice, not a
modelling one.

**Checker.** No change. It is already correct and is the thing being agreed
with.

**UI.** No change required for this defect. The separate `setAim` gap — no way
to say "this step chose it" where both placements are valid — is explicitly a
**non-goal** here.

**Regression cases.** The five in §6, plus: a step aimed inside a `watch_for`
body writes its binding there and checks clean; the same inside a `promise`
body; an aim inside a `may` arm still binds at the ability, unchanged.

**Shipped cards to verify.** `host_hat` and `crystal_ball` (`watch_for`
bodies); `compost`, `mom_s_bra`, `two_of_clubs`, `polycephalus` (`promise`
bodies); `finger`, `incubus`, `dead_bird`, `g_fuel` (arm-local bindings);
and all 352, unchanged.

**Browser verification.** Build a `watch_for` through the guided walk, add a
step inside it, aim that step, save, and read the file back off disk.

**Round-trip verification.** All 352 stable and clean; placement compared
rather than names (invariant 13).

**Replay.** 1000 games identical to `mass_baseline.jsonl` — a formality, since
nothing on a game path is touched, and cheap enough to be worth running.

**Explicit non-goals.** Not `setAim`. Not the reader's less accurate message in
case E. Not the guided walk. Not shadowing, which the language refuses on
purpose. Not `promise`'s or `watch_for`'s own contents. No new declaration, and
no scope tree.
