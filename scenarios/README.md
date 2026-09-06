# Scenarios

A folder of experiments. One file each, and each file is the whole description
of one: `fsme scenario list` reads this directory, `fsme scenario validate`
checks a file before a long run spends an hour finding a typo, and
`--scenario FILE` on `serve`, `play`, `simulate` and `study` sets a game up
from one.

A scenario is not a save. It says how a game *starts* — which sets are in the
decks, who sits where, what the table is worth winning. What happened
afterwards is a journal, and a journal carries a copy of the scenario inside
it, so deleting a file from here never stops a game replaying.
