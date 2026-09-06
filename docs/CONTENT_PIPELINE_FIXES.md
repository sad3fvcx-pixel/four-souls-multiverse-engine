# Content Pipeline Fixes

What was done about `docs/CONTENT_PIPELINE_AUDIT.md`, and what was decided
against. Every change here was measured before it was made and again after.

**Baseline, taken before anything changed and unchanged after:** 24
expansions, 1045 cards, 352 of them with rules. 1000 recorded games: **0
changed**, 1000 finished, 0 broke. None of these changes can touch a game —
they all refuse earlier, and refusing earlier changes nothing about a set that
was already correct.

---

## 1. A bare target name is a target, not a declaration

**Was.** `{"targets": [{"target_playr": {}}]}` was refused with a suggestion.
`{"targets": ["target_playr"]}` loaded cleanly and stopped the game when the
ability fired — the commoner spelling, and the one with no diagnosis.

The cause was that a bare string in `targets` was read as a name the ability
*declares*, which shadowed the spelling check.

**Analysis first.** Every place a target may be written as a string was
counted across `content/`:

| where | how many | what they are |
|---|---|---|
| ability `targets` list | **0** | — |
| effect `target` | 282 | 179 registered targets, 103 groups the ability bound |
| `of` | 11 | 10 bound groups, 1 registered target (`all_players`) |
| `for_each` | 1 | a registered target |

**Zero strings anywhere are neither a target nor a bound name**, and no shipped
card writes a bare name in `targets` at all. So the change costs nothing.

**Now.** A bare string in `targets` still binds a group under the target's own
name — which is what `{"targets": ["all_players"]}` relies on — but binding is
not declaring, and only `as` introduces a name that need not exist. The
misspelling is refused before a game, with the expansion, the file, the card,
the path and a suggestion.

The runtime resolver was not touched.

## 2. `requires` is part of the report

**Was.** Raised as `MissingDependencyError` after `raise_if_failed`, so a set
with a missing dependency *and* three broken cards told its author about the
dependency and nothing else.

**Now.** An ordinary reference issue, batched with everything else.

**The three cases asked about:**

- **Missing** — reported, with the set and the name it wants.
- **Repeated** (`requires: ["base", "base"]`) — not an error. It asserts the
  same true thing twice.
- **Cyclic** — **not an error, deliberately.** Nothing in the pipeline orders
  sets by their requirements: directories are read in sorted order and every
  set is read independently, so a requirement asserts that a set is *present*
  and says nothing about *when*. Two sets that require each other are both
  present. Refusing them would be inventing a rule for a failure that cannot
  happen. It becomes worth checking the day something reads sets in dependency
  order, and not before — there is a test saying exactly this, so the decision
  is visible rather than an omission.

`ContentLibrary.check_dependencies` stays where it is and still raises: it is
also called by `only()`, when a *scenario* narrows the library to a few sets.
That happens as a game is being set up, not while content is being read, and
raising is right there.

## 3. Card ids are global

**Was.** The duplicate check built a fresh table per expansion, so the same id
in two sets passed the whole report and then raised `DuplicateCardError` on
first use — naming neither set, neither file, and arriving with none of the
context every other message carries.

**Which layer.** The loader, where both files are still in hand. The registry
is too late (it has definitions, not paths) and a card file cannot know about
another set. So the table of "identifier → the file it came from" now spans
the whole root instead of one set.

**Now:**

```
[duplicate] theirs shared-loot-spark: card id is used in two files:
      .../mine/cards/loot.json
      .../theirs/cards/loot.json
    card ids must be unique across every set loaded together
```

Two cards in *one* file stay `validate_cards`' business — it is handed the
whole list and says so itself. Reporting it twice, with the same path on both
lines, is not more helpful.

Nothing is auto-corrected and no namespace is added. The convention every
shipped card follows — `expansion-deck-subcategory-name` — is still a
convention, and an author who ignores it gets away with it until their set
meets another one. Enforcing it would be inventing a rule; saying so in the
author documentation is the honest answer, and it is on the list.

## 4. Content identity on replay

**Was.** The journal recorded `content_version` and nothing read it. A game
replayed against changed content reported a state digest that did not match
and stopped, which says something is different and nothing about what.

**The three options.**

- **A — compare the version.** Free: the data is already in the journal, no
  format changes, and it names *which set* differs, which is the actionable
  half.
- **B — compare a content digest.** Needs a fingerprint over a thousand
  definitions in the journal. `ContentLibrary.identity` was written
  deliberately against this: a hash would be exact and would say nothing
  anybody could act on. It would also embed content in a record that is meant
  to be about one game.
- **C — both.** Pays B's cost for B's one advantage.

**Chosen: A.** Its blind spot is stated rather than papered over — two
libraries with the same identity are not proven identical, so a card edited
without its manifest version changing looks like no change at all. When the
identities agree, the replay says **nothing**, rather than claiming the
content is the same.

```
entry 41 (play_loot): the content is not what this was played against —
the journal says base_game@1.0.0,mine@2.0.0, this library is base_game@1.0.0
```

No format changed. `Divergence` already had a `reason`.

## 5. The registries

**Was.** 40 of 70 effects, 18 of 46 targets, 16 of 44 conditions and 15 of 66
triggers were missing from the documents that exist to list them. The drift ran
one way — nothing was described that the engine lacks — so nobody was sent down
a dead end; they simply could not find out that half the vocabulary exists.

**What can and cannot be generated.** The registries are hand-written prose
explaining what each name is *for*, per name, with examples. That is worth
having and cannot be generated, and inventing it would be worse than the gap.

What drifted is the part that was only ever a copy: **which names exist, and
what each one takes.** The engine now knows both exactly — the three shape
tables were built for validation and describe every parameter, its kind, its
domain and its floor.

**Now.** `tools/make_reference.py` writes `docs/REFERENCE.md` out of the live
engine: every effect, condition, target and trigger, with what each takes. It
is wholly generated, so no file is half-written by hand, and a test fails when
it is stale. The four registries keep their prose and are unchanged.

The reference also *counts the gap* in each section — "31 of 70 have a section
in `EFFECT_REGISTRY.md`; **39 are listed here and nowhere else**" — so the
shortfall is visible and tracked without failing a build. Blocking a new effect
until somebody writes a paragraph would trade one problem for a worse one.

---

## What was decided against

- **A namespace prefix added automatically to card ids.** The author's id is
  the author's.
- **Auto-correcting a misspelling.** `did you mean` is help; loading
  `target_playr` as `target_player` would be the engine guessing at meaning.
- **A cycle check on `requires`** — see §2.
- **A content digest in the journal** — see §4.
- **Generating the registry prose** — see §5.
- **Failing the build on undocumented names** — see §5.

## What is still open

Two need a rules answer before they can be written:

1. **`stat` on a static has no domain.** `STATS` exists in
   `fsme.state.modifiers` with eight names, but content also writes
   `difficulty`, which is defined outside the tuple. Whether `difficulty`
   joins `STATS`, or the domain is `STATS + (DIFFICULTY,)`, is a rules
   question. Until then a misspelled `stat` loads and the static silently
   contributes nothing.
2. **Unknown fields inside an ability or a static.** `CARD_SCHEMA.md` §14 says
   unknown optional fields are ignored for forward compatibility, which is
   right at the top level of a card. Inside an ability it is the same quiet
   mistake the parameter checks were built to catch. The two principles
   collide and somebody has to choose. A misspelled `scope` is the case that
   matters: it loads, and the ability fires under different rules.

And one is a stage of its own:

3. **The Target Reference Layer.** `of`, `chooser` and `exclude` name a group
   the ability bound, and checking them means resolving an ability's alias
   graph. It covers four remaining quiet failures at once — a name used before
   it is bound, a name bound twice (the second target is silently dropped), a
   name of the wrong kind, and a reference to nothing.

With those three done, the sentence at the top of the audit is true without
qualification. Today it is true with one: **most of an author's mistakes are
found before a game starts, and the ones that are not need either a rules
decision or the alias graph.**
