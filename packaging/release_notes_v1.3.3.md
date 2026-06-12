Simpler and snappier waiting.

- **The drop log is the only thing the macro watches now.** While farming a stage it just polls `Player.log` every second (a file-size stat) until the game records your blue chest, then stamps and moves to the next ready stage immediately — previously detection could lag up to 15 seconds behind the save-poll cadence. Clear times, run counters and gold checks are gone from the normal path entirely (they remain only as a fallback if `Player.log` is unavailable).

- **No idle pauses between decisions**: after stamping a drop (or giving up on a stage) the macro picks the next ready stage immediately instead of sleeping a poll interval, and the click→recapture delays during navigation are shorter.

Everything else as in v1.3.2 (macro/stash off by default, log-verified drops, 63 MB download).
