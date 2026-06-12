Chest levels editable on the dashboard.

- The **Lv badge on every dungeon card is now clickable** — set the stage's real chest level without touching `config.py` or restarting. This matters because drop verification matches the game's item key `920<level>1`: if the level is wrong, real drops are ignored and the macro waits forever. Set `0` to match any blue drop. Overrides persist in `macro_targets.json` and apply within one poll.

Everything else as in v1.3.3 (log-only drop watching, no decision sleeps, macro/stash off by default).
