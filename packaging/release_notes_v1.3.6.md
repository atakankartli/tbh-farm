Fixes lost drops and stale "where are we" state.

- **Drops can no longer be missed.** All blue drops go into a session-wide ledger the moment the game logs them — even while the macro is navigating, switching stages, or waiting on a different dungeon. Each stage's cycle consumes its own level from the ledger (a Lv15 drop seen during a Lv80 wait is kept for the 2-3 cycle, not discarded), and cooldowns are stamped with the moment the drop actually happened.
- **The macro knows where the game is parked.** It trusts its own navigation (including your manual "Go" clicks) instead of the save file's 1–2-minute-stale currentStage — so after you send it somewhere, it won't keep waiting for the previous dungeon's drop.
- **Your manual choice is respected**: if the stage you moved to is a ready farm target, it's farmed first instead of the macro immediately navigating away.

Everything else as in v1.3.5.
