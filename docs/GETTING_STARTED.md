# Getting started

Twenty minutes, from nothing to your own card measured. No knowledge of how
FSME is built is needed, and nothing here asks you to read source code.

If you only have one minute, do the first two steps.

---

## 1. Install it

You need **Python 3.12 or newer**. FSME has no other dependencies.

```bash
git clone <this repository>
cd four-souls-multiverse-engine
pip install .
```

Check it arrived:

```bash
fsme --version
fsme cards          # what card content is loaded, and how much of it works
```

`fsme cards` printing a list of sets means the cards travelled with the
install. If it says it cannot find them, see *When something goes wrong* below.

Prefer not to install anything? Every command below has its real output saved
in [`examples/`](../examples/), one file each.

---

## 2. See what it does

```bash
fsme demo
```

Twenty seconds, no arguments. It plays a game, proves the record of that game
is reproducible, reports on it, plays sixty more and says what they have in
common, then measures one card by playing the same games without it.

Each step prints the command that produced it, so the tour is also the tutorial.

If you would rather click than type:

```bash
fsme desk --open
```

The same four things behind buttons, in a browser. Every button runs the same
function the command runs and shows the same text.

---

## 3. Look at one game closely

```bash
fsme play --seed 42 --players 3 --journal my-game.json
fsme report my-game.json
```

The report has six parts, and each says what it is *not* as well as what it is:

| Part | What it tells you |
|---|---|
| The table | who did what, in counts |
| Key moments | the handful of moves that moved the scoreboard furthest |
| Why *X* won | what the winner did differently from everybody else |
| Why the others did not | the same comparison, the other way round |
| The decisions | what a bot would have played instead, and why |
| What did the work | which cards' effects moved the game |

The journal is the whole game written down — every position, every alternative
the engine would have accepted, every event. `fsme show my-game.json` reads it
out; `fsme replay my-game.json` plays it back and confirms it still comes out
the same.

---

## 4. Ask about many games

```bash
fsme study --games 200 --jobs 4
```

Four questions answered at once: where souls come from, what goes with
winning, which cards travel together, and which games are odd enough to look at
by hand. It ends with the cards worth putting under test, and the command that
would test them.

Read the wording carefully — it is chosen to be honest rather than impressive.
"Went with winning" never means "caused winning".

---

## 5. Write a card

Make a set under `content/user/`:

```
content/user/my_set/
├── manifest.json
└── cards.json
```

**manifest.json**

```json
{ "id": "my_set", "name": "My Set", "version": "1.0.0", "schema_version": "1" }
```

**cards.json**

```json
[
  {
    "id": "my_set-lucky_penny",
    "name": "Lucky Penny",
    "type": "loot",
    "expansion": "my_set",
    "text": "Gain 3 cents.",
    "abilities": [
      { "trigger": "on_play", "effects": [{ "effect": "gain_coins", "amount": 3 }] }
    ]
  }
]
```

Then:

```bash
fsme cards          # validates everything; your set appears in the list
```

A mistake is named where it is, with the nearest thing the engine does know:

```
  [semantic] .../content/user/my_set/cards.json: my_set-lucky_penny: ability 0:
      unknown effect 'gain_coinz' — did you mean 'gain_coins'?
```

The full vocabulary is in [EFFECT_REGISTRY.md](EFFECT_REGISTRY.md),
[TRIGGER_REGISTRY.md](TRIGGER_REGISTRY.md),
[CONDITION_REGISTRY.md](CONDITION_REGISTRY.md) and
[TARGET_REGISTRY.md](TARGET_REGISTRY.md). The shape of a card is in
[CARD_SCHEMA.md](CARD_SCHEMA.md).

---

## 6. Find out whether your card matters

One card among a thousand is rarely dealt, so make a smaller world for it:

```bash
mkdir -p /tmp/small
cp -r content/base_game content/user/my_set /tmp/small/

fsme test-card --content /tmp/small my_set-lucky_penny --games 200 --jobs 4
```

FSME plays two hundred games with the card in the deck and two hundred without
it, and compares. The verdict is one of three sentences:

- **an effect, in N of 5 measures** — the runs differ by more than their own
  uncertainty;
- **no effect this run could see** — they do not. Note the wording: not "no
  effect";
- **too scarce to say** — the card barely reached the table, so the difference
  between the runs is the deck rather than the card.

Read [LIMITATIONS.md](LIMITATIONS.md) before acting on any of it. The largest
caveat: taking a card out reshuffles every game, so the two runs differ
everywhere and not only where the card is.

---

## When something goes wrong

**`cannot find the cards`** — the install did not bring the card data. Point at
a checkout: `fsme cards --content /path/to/four-souls-multiverse-engine/content`.

**A wall of validation errors after adding a card** — that is the design:
invalid content refuses the whole library rather than loading half of it. The
message names the file, the card and the ability.

**`cannot listen on 127.0.0.1:8000`** — another `fsme desk` or `fsme serve` is
still running. Stop it, or pass `--port 8001`.

**A game that will not finish** — some pairs of cards can copy each other
without end. The engine stops and names them; this is a known gap, see
[LIMITATIONS.md](LIMITATIONS.md).

Anything else: please [open an issue](../.github/ISSUE_TEMPLATE/bug_report.yml).
The single most useful thing you can include is the **seed** — every game is
reproducible from one.

---

## Where to go next

- [`examples/`](../examples/) — output of each command, one file each
- [DEMONSTRATION.md](DEMONSTRATION.md) — the same tour with commentary on what
  each report is doing and why
- [LIMITATIONS.md](LIMITATIONS.md) — what FSME cannot do and will not claim
- [CONTRIBUTING.md](../CONTRIBUTING.md) — how to help
- [NEXT.md](NEXT.md) — where this might go, and what would justify going there
