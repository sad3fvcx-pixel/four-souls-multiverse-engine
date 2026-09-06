# Ready for the first author

The last stage before somebody outside the project writes a set. The aim was
not to add anything, but to remove the mistakes that used to load in silence.

**Verdict: yes, with three known limits, all of them documented and none of
them silent.**

---

## 1. What was closed

Six ways of writing a card wrong used to load cleanly and then play by rules
its author had not written. Each is now refused before a game, naming the
expansion, the file, the card, the path inside it, and the choices.

| written | before | now |
|---|---|---|
| `"scope": "contoller"` on an ability | fell through to `any`; the card reacted to every event at the table | `abilities[0].scope: 'contoller' is not one of 'self' or 'controller' or 'any' — did you mean 'controller'?` |
| `"scope": "contoller"` on a static | fell through to `controller` | refused, with all six scopes listed |
| `"stat": "atack"` | matched nothing; the static contributed nothing | `'atack' is not something a player has — did you mean 'attack' or 'attacks'?` |
| `"stat": "max_hp"` with `"scope": "all_monsters"` | loaded; nobody reads it | `'max_hp' is not something a monster has` |
| an unknown key on an ability or a static | ignored | `'whenever' is not part of an ability` |
| a misspelled key inside `if`, `may`, `choose`, `for_each`, `repeat` | a branch that never ran | `'thne' is not part of an if — did you mean 'then'?` |

### Where each domain came from

No list was written out by hand. That was the constraint and it held:

| domain | read from |
|---|---|
| ability `scope` | `ABILITY_SCOPES`, named at the branch in `in_scope` that gives the three answers |
| static `scope` | `PLAYER_SCOPES + MONSTER_SCOPES`, at the branch in `_in_scope` |
| a static's `stat` | `STATS` or `MONSTER_STATS`, chosen by where the static lands |
| `add_modifier`'s `stat` | `STATS \| MONSTER_STATS` — the union the effect's own guard reads |
| ability keys | `fields(Ability)` — `from_data` reads exactly the fields |
| static keys | `fields(Static)` |
| control-node keys | `CONTROL_KEYS`, one entry per `_expand_*`, beside the expanders |

Two of these were already tuples in the engine. Three are new names for
branches that had none — written at the branch itself, so that a fourth word
cannot be added to the language without the branch that gives it meaning.

### The two contexts of `stat`

The decision in `CARD_LANGUAGE_DECISIONS.md`, implemented as written:

- **`add_modifier`** takes either set. The effect decides player-or-monster
  from the target's runtime type, so nothing before a game may narrow it.
  `{"add_modifier": {"stat": "difficulty", "target": "current_monster"}}` is a
  legitimate card and still loads.
- **A static** takes the narrow set, because its landing place *is* known
  beforehand: monster scopes and a monster's own `self` reach a monster, and
  everything else reaches a player. Four shipped cards write
  `{"stat": "difficulty", "scope": "self"}` on a monster and all four still
  load.

### Strict inside, extensible outside

The rule now has a line through it, and the line is where forward
compatibility is a real argument:

- **The top of a card is extensible.** `{"rarity": "epic"}` still loads. A set
  may carry an artist credit or a field a later engine will read.
- **Inside the DSL it is strict.** There is nothing to be forward compatible
  with: the interpreter reads a closed set of keys and hands nothing else on,
  so an unknown key there is a mistake now.

## 2. Checked

| | result |
|---|---|
| all of `content/` | 24 sets, **1045 cards**, unchanged |
| the Author Kit examples | 5 of 5 load, validate and **play** |
| the tutorial's own example | extracted from the markdown and loaded |
| the kit's template | copies out and loads empty |
| 1000 recorded games | **0 changed**, 1000 finished, 0 broke |
| replay | **40 of 40 journals faithful** |
| tests | 1227 pass |
| ruff, mypy --strict | clean |

Every rule was dry-run over the whole of `content/` before it was written, and
each is tested from both sides — that it refuses the mistake, and that it
accepts the shipped card that looks like it.

One thing improved along the way: a misspelled key on a control node used to
produce two complaints, because the walker looking for effect names read the
stray key as one. A control node is named by its head, and everything else on
it belongs to that node. One typo, one message.

## 3. What an author is told

`GETTING_STARTED.md` §5 now opens by saying what a set can and cannot do —
that a card is data, that effects cannot be added from an expansion, that
nothing in a set is ever executed, and that a card which seems to need a new
mechanic usually needs three existing ones. Somebody was going to try;
finding out by failing is a poor first lesson.

No new reference was written. `docs/REFERENCE.md` is still generated from the
engine, and the kit links to it rather than copying it — a test asserts the
copy does not exist.

## 4. Limits that remain

All three are visible, none is silent.

1. **89 names have no prose.** 31 of 70 effects, 28 of 46 targets, 29 of 44
   conditions and 51 of 66 triggers have a section in their registry. The
   generated reference lists everything with what it takes, so nothing is
   *undiscoverable* — but an author who finds `take_card` there has nowhere
   to read what it means. The reference counts its own shortfall in each
   section.
2. **`docs/` holds 41 files** and an author needs five. The kit's README is a
   signpost; an index in `docs/` would be better.
3. **A group's kind is checked only as players-or-cards.** That is what the
   engine tells apart, so nothing finer would be true — but it means
   `{"of": "some_monsters"}` where items are meant is accepted. The runtime
   behaves correctly; it simply finds nothing.

Two smaller ones worth knowing: fixing an error can reveal another, because
the engine cannot check what was given to a misspelled effect until it knows
what the effect is; and card ids are unique across every set loaded together,
enforced by name but not by convention.

## 5. Ready?

**Yes.** An author who misspells anything the engine knows about — an effect,
a condition, a target, a trigger, a parameter, a scope, a stat, a key, or the
name of something their own ability chose — is told before a game starts,
with the file, the card, the path and the nearest spelling.

What they are not told is what a name *means* when they find it. That is the
one gap worth watching in the focus group, and it is a gap in prose rather
than in the engine.

The test plan is in `docs/AUTHOR_EXPERIENCE.md` §7: hand somebody the
repository, the guide and the kit; ask for one loot card; measure the time to
the first card that loads, every error message they could not act on alone,
**every time they open a file under `src/`**, and how many of the 41 documents
they open. Do not help while they work — a question asked out loud is a
documentation gap that would otherwise go unrecorded.
