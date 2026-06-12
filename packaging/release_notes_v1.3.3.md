Faster stage turnaround.

- The drop log is now checked every second (it's a cheap file-size stat), so the moment the game logs your blue chest the macro stamps it and moves on to the next ready stage — previously it could idle up to 15 seconds on the save-poll cadence. The heavier save-file read stays on its 15s interval. Tunable via `LOG_POLL_SEC` in `config.py` if you ever care.

Everything else as in v1.3.2 (macro/stash off by default, log-verified drops, 63 MB download).
