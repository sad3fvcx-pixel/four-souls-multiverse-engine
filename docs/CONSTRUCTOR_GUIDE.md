# Making cards with the Constructor

The Constructor is how you write cards for FSME. It runs in a browser, it asks
questions in the game's own words, and it will not let you save a card the
engine cannot play.

You do not need to read or write JSON to use it. Card files are still plain
JSON and you can still edit them by hand — see [Writing a card by
hand](#writing-a-card-by-hand) — but that is the expert path, not the ordinary
one.

## What it is

**Not a JSON editor.** A JSON editor knows that a file has fields. The
Constructor knows what a card *means*: which effects exist, what each one
needs, what may be aimed at what, and when a question is asked during a game.
It is built from the engine's own vocabulary, so it can only offer you cards
the engine can actually play.

Three things follow from that, and they are the whole point:

- **It checks as you go.** A card is validated by the same code that validates
  the shipped sets. If the Constructor says a card is ready, the engine will
  load it.
- **It keeps what your card means.** Open a card, change one number, save it,
  and everything else about the card is untouched — not merely the text of the
  file, but the game it produces. Every one of the 1045 shipped cards has been
  opened, saved and replayed to prove it.
- **It refuses rather than guesses.** A card using something the engine does
  not describe is not opened half-way and quietly repaired. You are told which
  part, and the file is left exactly as it was.

## Running it

```bash
pip install .
fsme desk --open
```

That opens a browser at `http://127.0.0.1:8000/`. The first screen offers
**Make a card**, **My cards** and **Watch a game**; the engine's other tools —
play, study, test, report — are one click further on under **Everything else**.

Your sets are saved in `FSME/my sets` inside your documents folder, not inside
the project. Both places are loaded whenever FSME runs, so a card you make is
dealt into games exactly like a card that ships with the engine, with no flag
to remember.

## Making your first card

1. **Open the Constructor** — `fsme desk --open`, then **Make a card**.
2. **Choose the kind of card** — loot, treasure, monster, character, and the
   rest. The list comes from the engine, so it is always the kinds that exist.
3. **Fill in what is printed on it** — its name, and the numbers its kind has:
   a monster has health, attack and a roll; a treasure has a price.
4. **Say what it does.** Pick an action from the list, and the Constructor asks
   what that action needs: how many cents, who it happens to, what must be true
   first. Add as many actions as the card has. An action can hold others —
   "roll a die, and on a 5 or 6 do this" — and the questions follow.
5. **Check it.** The card is checked as you type. What is missing is said in
   the words you used, not in the engine's: *"'Add coins to a player' needs to
   know how many cents."*
6. **Save it.** Saving is refused while anything is wrong, and nothing is
   written until everything is right.

Then watch it play:

```bash
fsme cards                       # your set appears in the list
fsme test-card <your-card-id>    # play many games with and without it
```

**Two ways in, one card.** Simple cards are quicker to answer as a series of
questions; complicated ones are quicker to see all at once. The Constructor
offers both and they produce the same card — you can move between them at any
point, and nothing is converted or lost when you do.

## How it works

```
card.json ──► reader ──► the model ──► the Constructor
                                              │
card.json ◄── writer ◄── the model ◄──────────┘
```

The reader turns a card file into a model of what the card *does*. The page
draws questions from that model. The writer turns the answers back into a card
file.

What the round trip protects is **meaning**, not formatting. The file may come
back spelled differently — the card language allows several spellings of the
same thing and the writer picks one — while the game the card produces is
identical. That is the guarantee, and it is measured rather than asserted: the
whole shipped corpus is rewritten through the Constructor and replayed, and
the games come out the same.

## What v0.9 does not do

These are the edges of the model, not things that are broken.

**Some fields are kept whole rather than taken apart.** A card's `rewards`,
a promise's `when`, and `metadata` are stored and returned exactly as written,
and shown as the data they are rather than as separate boxes. That is
deliberate: the engine accepts reward types it does not yet understand so that
future content does not invalidate today's cards, and a form with a box per
known reward would delete the ones it had no box for. Keeping them whole
cannot lose anything.

**Cards whose identifier is not a plain name can be opened but not saved.**
An identifier becomes a file name, so the Constructor only writes identifiers
made of lowercase letters, digits, `-` and `_`. Thirty-one cards in the
`engine_demo` set use dots in their identifiers; you can look at them, and
saving is refused rather than silently renaming the card that scenario files
point at.

**A card using something the engine does not describe is refused.** Not
repaired, not partially opened. The message names the part. This is the same
rule that makes the round trip safe: if the Constructor cannot represent
something faithfully, it does not pretend to.

**A card cannot invent new mechanics.** You combine effects, conditions,
targets and triggers the engine already has. A card that needs something new
is a gap in the engine worth reporting, not something to work around — see
[LIMITATIONS.md](LIMITATIONS.md).

## Writing a card by hand

Cards are plain JSON and nothing stops you editing them directly. It is the
right tool for bulk changes across many cards, for anything the Constructor
refuses, and for reading a diff.

Two things to know if you do:

- Every field must be one the engine describes. Unknown fields at the top of a
  card are **not** kept — the Constructor will refuse to open such a card, and
  the printed words of a card belong in `metadata.text`, which is where all
  1045 shipped cards keep theirs.
- A hand-written card is checked by the same validator: `fsme cards` loads
  everything and names the file, the card and the ability when something is
  wrong.

The full vocabulary — every effect, condition, target and trigger, with what
each one takes — is in [REFERENCE.md](REFERENCE.md), generated from the engine
so it cannot go stale. The shape of a card is in
[CARD_SCHEMA.md](CARD_SCHEMA.md). Working sets to copy rather than type are in
[`author-kit/`](../author-kit/README.md).

## Where to go next

- [Getting started](GETTING_STARTED.md) — install, demo, and the rest of FSME
- [What FSME cannot do](LIMITATIONS.md) — the engine's limits, stated plainly
- [REFERENCE.md](REFERENCE.md) — the whole vocabulary, generated
- [Architecture summary](CARD_CONSTRUCTOR_V09_ARCHITECTURE_SUMMARY.md) — how
  the Constructor is built, for people changing it rather than using it
