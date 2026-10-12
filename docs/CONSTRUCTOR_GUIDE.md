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

## Which kinds of card are walked

Eight kinds are walked through the questions from the moment you choose them:
**loot**, **treasure**, **starting item**, **event**, **monster**,
**character**, **curse** and **room**. For the first four the engine already
knows when the card acts — a loot card or an event is played, an item is used —
so the Constructor goes straight to what it does. For the other four it asks
when first, then the same questions follow.

Four kinds open in the editor instead: **bonus soul**, **soul**, **token** and
**other**. You can make all of them there, and they are checked and saved like
any other card. They are not walked, for these reasons:

- **A bonus soul** waits on a condition of its own rule — "the first player
  with 25¢" is asked before the rule does anything at all. The questions can
  only put a condition inside what a rule does, and the engine does not treat
  the two alike, so the questions would make a different card from the bonus
  souls that ship. Write its condition in the editor.
- **A soul, a token and an "other"** have no card in the shipped sets, and
  nothing in a game the engine deals lays one out or makes one. There is
  nothing yet to design the questions against.

This is where things stand, not a rule that they never will be walked.

Three things are worth keeping apart. **Being walked** means the Constructor
can make a card of that kind by asking questions. **Being kept faithfully**
means the card it saves opens again as the same card, which is true of every
kind. **Being played in full** is a question about the engine, not the
Constructor, and it has gaps a walked card does not close:

- **A room's rule that answers only to its controller never fires.** A room
  belongs to nobody. What the Constructor offers if you leave "Whose is it?"
  alone is never that, so a room's rule is caught out only by choosing it.
- **A room that can be attacked is not modelled.** A room prints no health,
  attack or roll here, and the Constructor does not ask for them.

Events and curses are dealt, yours included. The monster deck is built from
the monsters, then the events, then the curses, and shuffled; that order is how
the list is put together, not where any card ends up, which is the shuffle's.
Laying a game out fills the monster slots with monsters, as long as the deck
has them, and an event or curse it turns over on the way goes under the deck.
After that, an event or curse revealed where a monster would be — refilling a
slot, or attacking the deck — is played: an event happens, and a curse is
attached to the active player. The rules do not say who a revealed curse goes
to; giving it to the active player is what the engine does, not a settled rule.

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

## What v0.10 does not do

These are the edges of the model, not things that are broken.

**Some fields are kept whole rather than taken apart.** A card's `rewards`,
a promise's `when`, and `metadata` are stored and returned exactly as written,
and shown as the data they are rather than as separate boxes. What you type
into one of those comes back the way you typed it, names and order included.

`rewards` is where that was decided. What a monster pays out is an open set of
names with whole numbers under them: the checker asks that every value be a
whole number and says nothing about the names, so a card naming a reward this
engine has never paid still loads. The engine is the narrow one — it pays
`cents`, `loot` and `treasure` and ignores anything else — and that is what the
game does with the numbers, not what a card is allowed to say. A form drawing a
box per reward it knew would write back only those boxes, and a name it had no
box for would be gone; and telling the Constructor what is inside a field is
how a set of keys becomes closed, which would refuse a card the engine accepts.
So the field is left whole until a second one of the same shape exists to
design against: a mechanism drawn from a single use is a special case wearing a
general name.

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

A few things to know if you do:

- Every field must be one the engine describes. Unknown fields at the top of a
  card are **not** kept — the Constructor will refuse to open such a card, and
  the printed words of a card belong in `metadata.text`, which is where all
  1045 shipped cards keep theirs.
- A hand-written card is checked by the same validator: `fsme cards` loads
  everything and names the file, the card and the ability when something is
  wrong.
- A control node is written under its own name. `may`, `choose` and `sequence`
  may instead be written as a marker, `{"may": true, "effects": [...]}`; the
  Constructor opens that and saves it as `{"may": [...]}`, which plays the
  same. Writing the answer under both names, or a marker other than `true`, is
  refused. `stop` is best written as the bare word `"stop"`; whatever is
  written under a `{"stop": ...}` key is never read.

The full vocabulary — every effect, condition, target and trigger, with what
each one takes — is in [REFERENCE.md](REFERENCE.md), generated from the engine
so it cannot go stale. The shape of a card is in
[CARD_SCHEMA.md](CARD_SCHEMA.md). Working sets to copy rather than type are in
[`author-kit/`](../author-kit/README.md).

## Where to go next

- [Getting started](GETTING_STARTED.md) — install, demo, and the rest of FSME
- [Watch a game you set up](GETTING_STARTED.md#6-watch-a-game-you-set-up) —
  choose the characters, sets and starting cents, keep it, and deal it again
- [What FSME cannot do](LIMITATIONS.md) — the engine's limits, stated plainly
- [REFERENCE.md](REFERENCE.md) — the whole vocabulary, generated
- [Architecture summary](CARD_CONSTRUCTOR_V09_ARCHITECTURE_SUMMARY.md) — how
  the Constructor is built, for people changing it rather than using it
