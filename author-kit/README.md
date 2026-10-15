# Author Kit

Everything needed to write your first FSME expansion, and nothing that is
written down somewhere else.

**This is an index, not a tutorial.** The tutorial already exists and is good:
[`docs/GETTING_STARTED.md`](../docs/GETTING_STARTED.md) takes you from an
empty directory to a card measured in a game. Start there. Come back here for
a working set to copy.

---

## What is in here

```
author-kit/
├── templates/empty_expansion/   a set with no cards in it — copy this
└── examples/                    five sets, each showing one thing
    ├── simple_loot/             an effect and nothing else
    ├── simple_treasure/         a passive item: a number that is always on
    ├── conditional_card/        rolling a die and branching on it
    ├── choice_card/             choosing a player
    └── reference_card/          naming what you chose, and using it again
```

Every example in here is loaded, validated **and played** by
`tests/test_author_kit.py` on every run. If one of them stops working the
build fails, so nothing here can quietly rot into an example that no longer
does what it says.

## Where the answers are

| question | where |
|---|---|
| what an expansion is, and how to make your first one | [`docs/GETTING_STARTED.md`](../docs/GETTING_STARTED.md) |
| what fields a card may have | [`docs/CARD_SCHEMA.md`](../docs/CARD_SCHEMA.md) |
| **every effect, condition, target and trigger there is** | [`docs/REFERENCE.md`](../docs/REFERENCE.md) |
| what one of them is *for* | `docs/EFFECT_REGISTRY.md` and its three companions |
| what the engine will not do, and why | [`docs/LIMITATIONS.md`](../docs/LIMITATIONS.md) |

`docs/REFERENCE.md` is generated from the engine, so it is never out of date.
The four registry documents are written by hand and explain what things mean;
between them they still describe less than the reference lists, and the
reference says by how much.

There is deliberately no copy of the vocabulary in this directory. A second
copy is a copy that drifts.

## Checking your set without playing a game

```bash
fsme cards --content path/to/your/content
```

That loads and fully validates everything, prints what it found, and exits
non-zero if anything is wrong — so it works in a script as well as by hand.
Nothing is loaded at all if any card is wrong: an expansion is accepted or
refused whole, never in part.

Errors name the set, the file, the card and the path inside it, and offer the
nearest spelling the engine does know:

```
[semantic] my_set .../cards/loot.json: my_set-loot-oops: ability 0:
    unknown effect 'gain_coinz' — did you mean 'gain_coins'?
```

One thing to expect: **fixing an error can reveal another.** The engine cannot
check what you gave `gain_coinz` until it knows what `gain_coinz` is, so a
misspelled name hides the mistakes inside it. Run it again after each fix.

## Starting

```bash
cp -r author-kit/templates/empty_expansion content/user/my_set
$EDITOR content/user/my_set/manifest.json      # give it an id and a name
$EDITOR content/user/my_set/cards/loot.json    # add a card
fsme cards
```

Then copy whichever example is closest to what you are trying to write.

## Two things worth knowing early

**A card is data.** You combine effects the engine already has; you cannot add
new ones from an expansion, and nothing you write is ever executed as code.
If a card cannot be expressed with the vocabulary in the reference, it cannot
be written yet — that is a gap in the engine, and worth reporting as one.

**Card ids must be unique across every set loaded together.** The convention
every shipped card follows is `expansion-deck-subcategory-name`. Nothing
enforces it, and it is what stops your set colliding with somebody else's.
