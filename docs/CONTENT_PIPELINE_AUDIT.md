# Content Pipeline Audit

The question: **if somebody who has never seen this code writes their own
expansion, where can they still come unstuck?**

No code was changed for this document. Everything below was measured — broken
expansions were built in a temporary directory and put through the real
loader, and the cards that survived were resolved against a real board. Where
a claim comes from reading the source rather than running it, it says so.

---

## 1. The pipeline as it stands

Eleven stages. What each one checks, and when the author hears about it:

| # | stage | checks | tells the author |
|---|---|---|---|
| 1 | folder | a directory with a manifest in it is a set — at the root or one level down | at load |
| 2 | manifest | object; `id`, `name`, `version` present; `schema_version` supported; `requires` is a list | at load |
| 3 | read | JSON parses; file is an object, a list, or `{"cards": [...]}` | at load, with a line number |
| 4 | schema | required card fields; typed fields are the right type; `abilities` and `effects` are lists | at load |
| 5 | semantic | every effect, trigger, condition and target name; every parameter's kind, domain and floor | at load |
| 6 | identity | duplicate ids *within one expansion*; card's `expansion` matches the manifest; card `schema_version` | at load |
| 7 | references | `starting_item` resolves somewhere in the whole library | at load |
| 8 | registration | duplicate expansion id; **duplicate card id across expansions** | *not in the report — see §3* |
| 9 | dependencies | `requires` names a loaded set | *outside the report — see §3* |
| 10 | scenario | expansion, character and starting item exist | when a game starts |
| 11 | runtime / journal | everything the engine can only know with a board in front of it | mid-game |

The report accumulates and refuses the whole batch, so an author repairing a
set sees everything wrong with it at once rather than one problem per run.
Every message carries the category, the expansion, the file, the card and the
path inside it:

```
[semantic] mine .../cards/loot.json: mine-loot-spark: abilities[0].targets[0]:
  'target_deck_card' wants 'loot' or 'monster' or 'room' or 'treasure'
  for 'deck', card says 'tresure'
```

## 2. What works

Measured by building each mistake and loading it. All of these are refused
before a game, and the message names the file and the card:

**Structure** — malformed JSON (with the line), a manifest that is a list, a
manifest missing `id`/`name`/`version`, a card missing a required field, a
typed field given the wrong type (`"health": "lots"`), `abilities` given a
string, `effects` given an object, a card file that is a number.

**The DSL** — unknown effect, unknown trigger, unknown condition, unknown
control node, and every parameter check the three validation layers added: an
effect given text where a number belongs, a comparison the engine cannot make,
a deck that does not exist, a count written as a word, a flag where a family
name belongs, and a parameter that would be silently dropped.

**Identity** — a card id used twice in one expansion, a card claiming an
expansion it does not live in, a `starting_item` that resolves nowhere, an
expansion defined twice.

**The scenario stage** — an expansion that is not loaded, a character that
does not exist, a starting item that is not a starting item. All three refuse
with the list of what *is* available.

Three shapes of card file are accepted and all three work: `{"cards": [...]}`,
a bare list, and a single bare card.

## 3. Remaining failure modes

Ordered by how badly they behave, not by how likely they are.

### 3.1 Loads, then quietly does the wrong thing

The worst class, because nothing ever complains. Each of these was loaded and
then resolved on a real board.

| what the author wrote | what happens |
|---|---|
| a misspelled `scope` (`"evrybody"`) | loads; the ability fires under different rules than intended |
| a misspelled static `stat` (`"atack"`) | loads; the static contributes nothing — measured, the bonus is 0 |
| two targets binding one `as` name | loads; the second target is **skipped entirely** — `resolve_all` leaves a bound alias alone, which is what makes an ability resumable |
| `of` naming a group that holds cards, not players | loads; the target is empty and nothing says why |
| `of` naming a group bound *later* in the same ability | loads; empty, because order matters and nothing says so |
| `chooser` or `exclude` naming nothing | loads; falls back to the controller, or excludes nothing |
| an unknown field on an ability or a static | loads; ignored |
| an unknown field on a card or a manifest | loads; ignored |
| a scenario excluding a card id that does not exist | runs; excludes nothing |

The first two are the most dangerous, because `scope` and `stat` are short
words an author will guess at, and both change what the card does rather than
whether it works.

### 3.2 Loads, then stops the game

Refused, but hundreds of moves too late, naming no card and no file.

| what the author wrote | what happens |
|---|---|
| a **bare** misspelled target name in an ability's `targets` | `UnknownTargetError` when the ability fires |
| `watch_for` or `promise` naming an event that does not exist | `EffectExecutionError` when the effect resolves |

The bare-name hole is worth spelling out, because it is the commonest spelling
an author will reach for and the object form *is* caught:

```
{"targets": [{"target_playr": {}}]}   → refused, "did you mean 'target_player'?"
{"targets": ["target_playr"]}         → accepted
```

The cause is that `_declared_target_names` treats a bare string in `targets` as
a name the ability *declares*, which shadows the spelling check. That reading
exists because `{"targets": ["all_players"]}` does legitimately bind the group
under its own name — but binding is not declaring, and a bare name should have
to be a real target as well.

**No shipped card writes a bare name in `targets` — 0 of 922 specifications —
so tightening this costs nothing.**

The event names on `watch_for` and `promise` are checkable too: the domain is
`EventType`, which already crosses the boundary as `Vocabulary.triggers`. The
parameters are described as plain `text` with no domain.

### 3.3 Crashes outside the report

Not validation failures — exceptions, with none of the file-and-card context
every other message carries.

| what the author did | what happens |
|---|---|
| the same card id in **two different** expansions | the whole report passes, then `DuplicateCardError` on `registry()`, naming neither expansion nor file |
| `requires` naming a set that is not loaded | `MissingDependencyError` after `raise_if_failed`, so it is never batched with anything else |

The first is a real hazard for public extensions and is the natural
consequence of the duplicate check being per-expansion: `_load_cards` builds a
fresh `seen` for each set. Two authors who both ship `spark` collide, and the
error tells the person assembling the folder nothing about which two sets.

### 3.4 Silent across runs

The journal records `content_version` — `base_game@1.0.0,mine@1.2.0`,
deliberately a list of manifest versions rather than a hash. Its own docstring
says it is written "so that a game replayed against different content can be
told *why* it diverged rather than only that it did".

**Replay never reads it.** A journal replayed against changed content diverges
on a state digest and reports a digest mismatch, which tells the author
nothing about the cause. And because the identity is the manifest version, an
author who edits a card without bumping that version gets a journal that
diverges with no signal at all.

## 4. The data / logic boundary

This one is clean, and the audit found nothing to fix.

- `content/` and `cards/` import **nothing** from the engine — only
  `fsme.util.errors` and each other. Verified by reading every import in both
  packages.
- No `eval`, `exec`, `__import__`, `importlib`, `compile`, `pickle`,
  `marshal`, `subprocess` or `yaml.load` anywhere in either package. The only
  reader is `json.loads`.
- A card file is data. There is no path by which an expansion can supply code,
  and none by which the loader can run any.
- The vocabulary crossing into the pipeline is plain data — names, kinds,
  tuples of strings, integers, booleans. No handler, no condition function and
  no target function crosses. Checked by walking every `ParamShape` in all
  three shape tables.
- No card in `content/` has a special case anywhere in the engine.

**Can an outside author write a complete card using only data?** For the
overwhelming majority, yes: 1045 shipped cards are data, and 352 of them have
rules. The honest exceptions are two, and both are *expressive* limits rather
than boundary leaks:

1. **Nothing in the DSL asks a specific bound player to choose from their own
   items.** `target_loot` and `target_soul` do it for hands and souls, and
   `target_treasure` now does it for items — but the general shape ("ask *this*
   group about *that* group") is a per-target arrangement, not a thing an
   author can compose.
2. **An author cannot introduce a new effect.** That is the design, not a gap:
   cards are data and mechanics live in the engine. It is worth stating
   plainly in the author documentation, because somebody will try.

## 5. Documentation gaps

The largest practical barrier, and it is measurable. Comparing the four
registry documents against the live engine:

| document | engine has | not mentioned in the document |
|---|---|---|
| `EFFECT_REGISTRY.md` | 70 effects | **40** |
| `CONDITION_REGISTRY.md` | 44 conditions | **16** |
| `TARGET_REGISTRY.md` | 46 targets | **18** |
| `TRIGGER_REGISTRY.md` | 66 triggers | **15** |

Spot-checked rather than trusted to a regex: `deck_top`, `target_curse`,
`group`, `add_counter` and `end_turn` appear **zero** times in their own
registry file.

The drift runs one way only — the documents name nothing the engine lacks — so
an author is never sent down a dead end. But they cannot discover more than
half of what is available, which for somebody writing a card is the same as it
not existing.

What is missing beyond the registries, listed rather than written:

1. **A card-author's guide** that is one document: the required fields, the
   three accepted file shapes, how to write a manifest, and how ids work.
2. **The id convention.** `expansion-deck-subcategory-name` is used
   consistently by every shipped card and is enforced nowhere. An author who
   writes `spark` gets away with it until their set meets another one.
3. **Parameter domains in one place.** The engine now knows every closed
   domain — decks, piles, card types, comparison operators, countable things,
   stack kinds. None of it is written down for an author.
4. **What `as` means, and the order it implies.** Three of the quiet failures
   in §3.1 are an author not knowing that a bound name must be bound *before*
   it is read, and that binding the same name twice drops a target.
5. **That an expansion cannot add behaviour**, only combine what exists.
6. **That editing a card without bumping the manifest version** makes an old
   journal diverge silently.

The registries should not be written by hand again — they drifted because they
were. They should be generated from the engine and pinned by a test, which is
the discipline the validation layers already use.

## 6. Required fixes before public extensions

The minimum after which it is honest to say *"the engine either accepts your
expansion or explains why it will not"*. Ordered by cost against benefit.

**Cheap, and they close whole categories:**

1. A bare name in `targets` must be a known target. Measured cost: zero
   shipped cards write one.
2. Duplicate card ids **across** expansions become a report issue, with both
   files named, instead of a `DuplicateCardError` on first use.
3. `requires` naming an absent set becomes a report issue, batched with
   everything else.
4. `event` on `watch_for` and `promise` gets the domain it already has.
5. `scope` gets its domain — the values the engine actually branches on.

**Needs a decision first:**

6. `stat` on a static gets a domain. `STATS` exists in `fsme.state.modifiers`
   and has eight names, but content also writes `difficulty`, which is defined
   outside the tuple. Whether `difficulty` joins `STATS` or the domain is
   `STATS + (DIFFICULTY,)` is a rules question, not a validation one.
7. Unknown fields on an **ability** or a **static**. `CARD_SCHEMA.md` §14 says
   unknown optional fields are ignored for forward compatibility, and that is
   right for the top level of a card. Inside an ability it is the same quiet
   mistake the parameter checks were built to catch. The two principles
   collide and somebody has to choose.

**Larger, and the single biggest remaining item:**

8. **The Target Reference Layer** — resolving an ability's alias graph. It
   covers four of the nine quiet failures in §3.1 at once: a name used before
   it is bound, a name bound twice, a name of the wrong kind, and `chooser` or
   `exclude` naming nothing. It was deliberately deferred from Target
   Validation v1 and this audit does not change that judgement; it does move
   it to the front of the queue.
9. **Replay compares `content_version`** and says so when it differs, instead
   of reporting a digest mismatch.
10. **Regenerate the four registries from the engine, with a test that fails
    when a name is added without a description.**

## 7. What should not be added

Named because each is a plausible answer to a problem above, and each would
cost more than the problem.

- **A card editor or any UI.** Out of scope, and it would become the contract
  instead of the format.
- **Python, plugins or any executable content in an expansion.** §4 is the
  most valuable property this pipeline has.
- **A runtime import in the loader** — including "just to check one thing".
- **Special cases for individual cards**, in the engine or the validator.
- **Auto-correcting a misspelling.** Suggesting `did you mean` is help;
  silently loading `target_playr` as `target_player` would make the engine
  guess at what a card means.
- **A separate language for targets**, or any DSL growth to make an author's
  life easier. The two expressive limits in §4 are worth living with until a
  real card cannot be written.
- **A hash-based content digest.** The manifest version is a number somebody
  is already responsible for; a fingerprint over a thousand definitions would
  be exact and would say nothing anybody could act on.
- **Relaxing the whole-batch refusal.** Partial loading would put half-valid
  content into a game, which is the thing the pipeline exists to prevent.

---

## Summary

The boundary is sound and needs no work. The validation layers cover the
structure and the language well: every mistake in §2 is caught before a game,
with the file and the card named.

What remains is almost entirely the third category — a card that loads and
then means something other than what its author wrote. Five of those are cheap
to close and one, the alias graph, is a stage of its own.

The documentation is the largest gap by distance. More than half of the
engine's vocabulary is undiscoverable from the documents that exist to
describe it, and no amount of validation helps an author who cannot find out
that `deck_top` exists.
