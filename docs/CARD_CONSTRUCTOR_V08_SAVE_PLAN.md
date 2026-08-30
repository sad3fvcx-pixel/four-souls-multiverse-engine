# Card Constructor v0.8 — keeping a change

A card can be opened, read back, changed part by part and played. It cannot be
kept. This is the plan for the last step, and it is the first thing in the
whole chain that writes over somebody's own file — so the plan is mostly about
what must *not* happen.

Measured against the engine at `2e419fe`.

---

## 1. Where cards actually live

Two roots, and only one of them is writable:

| Root | What it is | Written by the desk |
|---|---|---|
| `content/` (or inside the frozen bundle) | the 1045 shipped definitions | **never** |
| `~/FSME/my sets/<set>/cards/*.json` | the author's own sets | yes |

`content_roots()` loads both, so a card somebody wrote is dealt exactly like a
shipped one. But the desk's own doors — `sets()`, `open_card`, `save_card`,
`delete_card` — all go through `_set_directory()`, which resolves under
`sets_directory()` and nowhere else.

**The shipped cards are therefore not reachable from "My cards" at all**, and
not by care but by construction: they are in no set, so they cannot be listed,
so they cannot be opened, so they cannot be written over. Two tests pin this.

Worth stating because the coverage figures quoted through v0.8 — 248 read, 226
editable — are about the *reader*, measured directly against the shipped files.
What a person can reach today is the cards in their own sets.

---

## 2. How a card reaches a file today

```
state.card ──→ build_card ──→ check_card ──→ write
                                   │
                              problems? nothing is written
```

`save_card` in `lab/desk/author.py`:

1. `build_card(described)` — author state to a `CardDefinition`.
2. `check_card(card)` — the same validator every card goes through.
3. If anything is wrong: return the problems and write nothing.
4. Otherwise write `{"cards": [card]}` to
   `<set>/cards/<card id>.json`, `indent=2`, `ensure_ascii=False`.

Validation already happens before the write, and that half of the contract is
already right. The identifier is the part that is not:

```
card_identifier(expansion, type, name)  →  "probe-loot-thumbtack"
```

A card's file is named after its identifier, and its identifier is made out of
its **name and type**. That is fine for a card being made — the first save
names it — and it is the source of the first of the two problems below.

---

## 3. The contract, and where it already holds

Measured by running each scenario, not by reading the code.

| | Scenario | Today |
|---|---|---|
| **A** | open → save, nothing changed | **file byte-identical** ✓ |
| **B** | open → change a value → save | **only that value moved**; name, type, expansion, the other action and the bindings all kept ✓ |
| **C** | a change that breaks the card | **not saved, file untouched, reason given** ✓ |
| **D** | the file changed on disk after opening | **last write wins, silently** ✗ |
| — | rename the card and save | **two files; the old one is still there and still loads** ✗ |

So three of the four already hold, and the two failures are both about the
*file* rather than about the card.

### D — what to do about a file that changed underneath

Three options, and only one is defensible here:

- **Refuse.** Compare the card on disk with the card that was opened; if they
  differ, do not write, and say so. The person keeps their change in hand and
  decides.
- **Overwrite.** What happens today. It silently destroys somebody's work, and
  there is no signal anywhere that it happened.
- **Merge.** Two edits to the same card, reconciled without either author
  present. This is a hard problem in general and an absurd one for a
  single-person tool with no history to merge against.

**Recommendation: refuse.** It costs one comparison, it is explainable in one
sentence, and it is the only option that cannot lose work. There is no locking
to add: the card that was opened is already in hand, so the check is "is the
file still what I read".

### Renaming

Renaming changes the identifier, which changes the file name, so the save
creates a new file and orphans the old one. The author renamed one card and now
has two, both loading, both dealt.

Options: keep the old identifier for the life of the card (a card would then
carry a name that no longer matches its identifier, which the shipped content
never does), or write the new file and remove the old one. The second is what a
rename means. It needs the identifier the card was *opened* under, which the
save call does not currently carry.

---

## 4. What survives a round trip through the file

Measured on a card written by hand with four-space indent, sorted keys, the
short spelling and extra notes:

| | |
|---|---|
| keys lost | **none** |
| keys gained | **none** |
| `metadata` | kept exactly |
| `tags` | kept exactly |
| an ability's `description` | kept |
| the short spelling `{"gain_coins": 2}` | rewritten as `{"effect": …, "amount": 2}` |
| indent 4, sorted keys | rewritten as indent 2, shape order |
| comments | JSON has none to lose |

So **the card survives and the text does not**. Opening and saving canonicalises
the file even when nothing was edited — which is the same canonicalisation the
reader has always done, and is why scenario A is byte-identical only for a file
that `save_card` wrote in the first place.

An unknown field is not silently dropped: `read_card` refuses a card carrying a
key the engine does not describe, so such a card cannot be opened and therefore
cannot lose anything.

---

## 5. The format to write

**Option A — full rewrite in canonical JSON.** Chosen.

- **B, patch only the changed fields**, would need a diff against the file and a
  way to apply it, which is a second writer of card files that has to agree with
  the first about everything. There is one builder; a patcher would be a second.
- **C, a separate author format**, is the second on-disk representation this
  project has refused at every turn, and it would rot at the first hand edit —
  which is how all 1045 shipped cards were written.

A is what `save_card` already does, and it is right for the same reason the
reader canonicalises: there is one way to write a card, and a file that has been
through the desk is written that way. The cost — a hand-formatted file being
reformatted — is real and worth saying out loud on the screen, once.

---

## 6. The contract, written first

Eight tests are in `tests/test_card_rehydration.py` now.

Passing today, and they must keep passing:

- saving a card nobody changed changes nothing;
- changing one value keeps everything else, and opening it again gives back
  what was kept;
- a change that breaks the card is not kept, and the file is untouched;
- keeping a change to one part keeps the other parts;
- saving can only ever write under the author's own sets;
- nothing in `content/` appears in any set, so nothing there can be opened or
  written over.

Failing on purpose, marked `xfail(strict=True)` so that fixing them turns them
into failures and forces the marker off:

- renaming a card does not leave the old one behind;
- a card changed underneath is not overwritten silently.

---

## 7. Order of implementation

1. **Carry the identifier a card was opened under.** `open_card` knows it;
   nothing passes it back. Everything else depends on this.
2. **Refuse a file that changed underneath** — compare what is on disk with
   what was opened, before writing.
3. **Rename properly** — write the new file, remove the one it replaced, and
   only when the write succeeded.
4. **The screen** — the button, what it says afterwards, and the one sentence
   about a hand-formatted file being rewritten.
5. **Gate**: `pytest`, `ruff check .`, `mypy src --strict`, `git diff --check`,
   352/1045, 1000-game replay, and — new for this stage — a test that the
   author workspace is exactly as expected after each scenario.

Steps 1–3 are the whole of the risk and none of the interface. They are worth
doing and reviewing before a button exists.

---

## 8. What could break the first time somebody saves a real card

| | Weight | |
|---|---|---|
| **a rename silently doubles a card** | **high** | happens today, on the first rename; step 3 |
| **two windows, one card, one edit lost** | **high** | happens today, silently; step 2 |
| a hand-formatted file is reformatted | medium | unavoidable with one writer; say so on the screen |
| the short spelling is rewritten long | medium | the same canonicalisation, and the card is unchanged |
| a card is saved that would not load | low | already impossible — checked before writing |
| shipped content is touched | **none** | structurally unreachable, and two tests say so |
| a partial write leaves a broken file | medium | `write_text` is not atomic; write beside and replace |
| the set's manifest and its cards disagree | low | the manifest lists no cards; the directory is the list |

The last one on the list is the only new thought: `path.write_text` truncates
before it writes, so a crash mid-write leaves an empty or half file. Writing to
a temporary name in the same directory and replacing is one line and removes
the whole class.

---

## 8a. What Stage 1 settled, and what it left

Built, backend only — no button, no screen:

- **a stable identifier.** A card's id is made from its name once, when it has
  never been saved. After that the card carries it back through `opened`, and
  renaming changes what the card is called and not which card it is. This is
  the opposite of what §3 above recommended, and the reason is that a scenario
  file names cards by identifier, typed by hand: a card that took a new id on
  being renamed would stop being the card those files mean.
- **a fingerprint check.** What the file said when it was opened, compared
  with what it says now. Different, gone, or shared with other cards: refused,
  nothing written, reason given. No merge.
- **an atomic write.** Beside the card, fsynced, then `os.replace`. A failure
  at any point leaves the old card whole and nothing beside it.

Left deliberately, and the next risk to take:

| Risk | Weight | |
|---|---|---|
| **new card creation → derived id collision → refuse overwrite** | **high** | a card being made carries no fingerprint, so a new card whose derived id matches one already in the set still overwrites it silently. The same class as D, by the one route the carried identity cannot cover. Its own stage: **Create flow protection**. |

---

## 9. Deliberately not in this stage

- **Undo, or any history.** Refusing to overwrite is not the same as keeping
  versions, and versions are a much larger idea.
- **Editing a shipped card.** It is not in a set; copying one into a set is a
  different feature with its own questions.
- **Merging two edits.**
- **Anything about the 104 cards that do not read** or the 22 that read and
  cannot be changed.

---

## 10. The invariant

```
Constructor ──┐
              ├──→ state.card ──→ build_card ──→ CardDefinition ──→ Validator ──→ file
Expert Editor ┘         ↑                                              │
                   read_card ←────────────────────────────────────── the file
```

One builder, one checker, one reader, one writer. A card on disk is a card the
engine loads, whoever wrote it and however it got there.
