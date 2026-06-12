"""Blue-chest (stage boss) cooldown tracker — no OCR, no overlay window.

Mechanics (verified against tbh-meter's chestDropLog history):
- Killing a stage boss drops a blue chest IF 12 minutes have passed since that
  dungeon's previous blue drop. The drop lands at run end (boss kill).
- 2-5 Hell history: 33 drops with gaps clustering at ~886-915s = exactly three
  chained ~295s runs; the first clear after the 720s cooldown drops.
- tbh-meter (reading game memory) appends every blue drop to chestDropLog in
  its settings.json and rewrites the file immediately, so it is a fresh,
  reliable source of drop timestamps.

This module merges tbh-meter's log with our own local record (macro_chests.json,
written by main.py when a navigated run succeeds) so a delayed settings write
cannot make a stage look READY right after we farmed it.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import config
from tracker import ReadyStage

COOLDOWN_MS = getattr(config, "CHEST_COOLDOWN_MIN", 12) * 60 * 1000


def _atomic_write(path: Path, text: str) -> None:
  """Write to a temp file then replace, so a crash mid-write can never leave a
  truncated/corrupt drop-times file (which would wipe cooldowns on restart)."""
  tmp = path.with_suffix(path.suffix + ".tmp")
  tmp.write_text(text, encoding="utf-8")
  os.replace(tmp, path)

LOCAL_STATE_PATH = Path(__file__).with_name("macro_chests.json")   # latest drop per stage
LOCAL_LOG_PATH = Path(__file__).with_name("macro_drops.json")      # append-only drop history
EXTRA_TARGETS_PATH = Path(__file__).with_name("macro_targets.json")  # stages added via web GUI
_STAGE_DATA_PATH = Path(__file__).with_name("stage_data.json")


def _load_stage_table() -> dict[str, dict]:
  """Numeric stage key -> stage info (act/diff/label/lvl/name), extracted game table."""
  try:
    with open(_STAGE_DATA_PATH, encoding="utf-8") as fh:
      return json.load(fh)
  except (OSError, ValueError):
    return {}


_STAGE_TABLE = _load_stage_table()


def _load_stage_names() -> dict[str, str]:
  names = {}
  for key, info in _STAGE_TABLE.items():
    name = info.get("name")
    if isinstance(name, dict):
      name = name.get("en-US") or next(iter(name.values()), None)
    if name:
      names[key] = name
  return names


_STAGE_NAMES = _load_stage_names()

_DIFFICULTY_NUM = {"NORMAL": 1, "NIGHTMARE": 2, "HELL": 3, "TORMENT": 4}


@dataclass(frozen=True)
class Target:
  act: int
  stage: int
  difficulty: str  # NORMAL / NIGHTMARE / HELL
  level: int
  custom: bool = False  # added at runtime via the web GUI (macro_targets.json)

  @property
  def key(self) -> str:
    return f"{self.act}-{self.stage}:{self.difficulty}"

  @property
  def stage_key(self) -> int:
    """tbh-meter's numeric key: difficulty*1000 + act*100 + stage."""
    return _DIFFICULTY_NUM[self.difficulty] * 1000 + self.act * 100 + self.stage

  @property
  def mode(self) -> str:
    # .get so a config.py predating a difficulty (e.g. TORMENT) still works
    return config.DIFFICULTY_LABELS.get(self.difficulty, self.difficulty.capitalize())


def _parse_spec(spec: str, level: int = 0, custom: bool = False) -> Target:
  try:
    stage_part, difficulty = spec.strip().upper().split(":")
    act, stage = stage_part.split("-")
    act_n, stage_n = int(act), int(stage)
  except ValueError:
    raise ValueError(f"bad stage spec {spec!r} (expected 'act-stage:DIFFICULTY')") from None
  if difficulty not in _DIFFICULTY_NUM:
    raise ValueError(f"bad difficulty {difficulty!r} (one of {', '.join(_DIFFICULTY_NUM)})")
  return Target(act=act_n, stage=stage_n, difficulty=difficulty, level=int(level), custom=custom)


def _load_targets_file() -> dict:
  """{'extras': [{spec, level}, ...], 'disabled': ['2-5:HELL', ...]}.
  A bare list (the v1.1.0 format) is read as extras with nothing disabled."""
  try:
    with open(EXTRA_TARGETS_PATH, encoding="utf-8") as fh:
      raw = json.load(fh)
  except (OSError, ValueError):
    return {"extras": [], "disabled": []}
  if isinstance(raw, list):
    return {"extras": [e for e in raw if isinstance(e, dict) and "spec" in e], "disabled": []}
  return {
    "extras": [e for e in raw.get("extras", []) if isinstance(e, dict) and "spec" in e],
    "disabled": [s for s in raw.get("disabled", []) if isinstance(s, str)],
  }


def _save_targets_file(data: dict) -> None:
  _atomic_write(EXTRA_TARGETS_PATH, json.dumps(data))


def _config_entries() -> list[tuple[str, int]]:
  entries = []
  for entry in getattr(config, "TARGET_STAGES", ()):
    spec, level = (entry, 0) if isinstance(entry, str) else entry
    entries.append((spec, level))
  return entries


def get_targets() -> list[Target]:
  """config.TARGET_STAGES plus GUI-added stages, minus GUI-disabled ones,
  deduped (config wins)."""
  data = _load_targets_file()
  entries = [(spec, level, False) for spec, level in _config_entries()]
  entries += [(e["spec"], e.get("level", 0), True) for e in data["extras"]]

  disabled = set(data["disabled"])
  targets: list[Target] = []
  seen: set[str] = set()
  for spec, level, custom in entries:
    target = _parse_spec(spec, level, custom)
    if target.key not in seen and target.key not in disabled:
      seen.add(target.key)
      targets.append(target)
  return targets


def all_stages() -> list[dict]:
  """Every stage in the game table, for the GUI's add-dungeon picker."""
  out = []
  for key, info in sorted(_STAGE_TABLE.items(), key=lambda kv: int(kv[0])):
    stage_no = int(key) % 100
    out.append({
      "spec": f"{info['act']}-{stage_no}:{info['diff']}",
      "act": info["act"],
      "stage": stage_no,
      "difficulty": info["diff"],
      "level": info.get("lvl", 0),
      "name": _STAGE_NAMES.get(key),
    })
  return out


def add_target(spec: str, level: int | None = None) -> Target:
  """Add a farm target at runtime (web GUI). Persisted in macro_targets.json,
  picked up by the loop on its next poll. Level defaults to the stage's level.
  Re-adding a GUI-removed config stage just re-enables it."""
  target = _parse_spec(spec, level or 0, custom=True)
  info = _STAGE_TABLE.get(str(target.stage_key))
  if info is None:
    raise ValueError(f"stage {target.key} does not exist")
  if level is None:
    target = _parse_spec(spec, int(info.get("lvl", 0)), custom=True)
  data = _load_targets_file()
  if target.key in data["disabled"]:
    data["disabled"].remove(target.key)
    _save_targets_file(data)
    return target
  if any(t.key == target.key for t in get_targets()):
    raise ValueError(f"{target.key} is already a farm target")
  data["extras"].append({"spec": target.key, "level": target.level})
  _save_targets_file(data)
  return target


def remove_target(spec: str) -> bool:
  """Remove any farm target: GUI-added ones are deleted from the extras list;
  config-defined ones go on a disabled list (config.py itself stays untouched).
  Returns False if the spec isn't currently a target."""
  key = _parse_spec(spec).key
  data = _load_targets_file()
  kept = [e for e in data["extras"] if _parse_spec(e["spec"]).key != key]
  if len(kept) != len(data["extras"]):
    data["extras"] = kept
    _save_targets_file(data)
    return True
  config_keys = {_parse_spec(s, lv).key for s, lv in _config_entries()}
  if key in config_keys and key not in data["disabled"]:
    data["disabled"].append(key)
    _save_targets_file(data)
    return True
  return False


def _meter_settings_path() -> str:
  return getattr(
    config, "TBH_METER_SETTINGS",
    os.path.expanduser(r"~\AppData\Roaming\tbh-meter\settings.json"),
  )


def _load_meter_drops() -> dict[int, int]:
  """Latest blue-chest dropAt (ms) per numeric stageKey from tbh-meter."""
  try:
    with open(_meter_settings_path(), encoding="utf-8") as fh:
      settings = json.load(fh)
  except (OSError, ValueError):
    return {}
  drops: dict[int, int] = {}
  for entry in settings.get("chestDropLog", []) + settings.get("chestCooldowns", []):
    key, at = entry.get("stageKey"), entry.get("dropAt")
    if isinstance(key, int) and isinstance(at, (int, float)):
      drops[key] = max(drops.get(key, 0), int(at))
  return drops


def _load_local_drops() -> dict[int, int]:
  try:
    with open(LOCAL_STATE_PATH, encoding="utf-8") as fh:
      raw = json.load(fh)
    return {int(k): int(v) for k, v in raw.items()}
  except (OSError, ValueError):
    return {}


def record_local_drop(target: ReadyStage | Target, drop_at_ms: int) -> None:
  """Stamp a blue drop we caused: update latest-per-stage (for cooldowns) and
  append to the history log (for the GUI / our own record)."""
  num_key = _DIFFICULTY_NUM[target.difficulty.upper()] * 1000 + target.act * 100 + target.stage
  drop_at_ms = int(drop_at_ms)
  drops = _load_local_drops()
  drops[num_key] = max(drops.get(num_key, 0), drop_at_ms)
  _atomic_write(LOCAL_STATE_PATH, json.dumps(drops))

  log = recent_local_drops(limit=500)
  log.insert(0, {
    "stageKey": num_key,
    "stage": f"{target.act}-{target.stage}",
    "mode": config.DIFFICULTY_LABELS.get(
      target.difficulty.upper(), target.difficulty.capitalize()),
    "dropAt": drop_at_ms,
    "dropAtStr": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(drop_at_ms / 1000)),
  })
  _atomic_write(LOCAL_LOG_PATH, json.dumps(log[:500]))


def recent_local_drops(limit: int = 12) -> list[dict]:
  try:
    with open(LOCAL_LOG_PATH, encoding="utf-8") as fh:
      log = json.load(fh)
  except (OSError, ValueError):
    return []
  return sorted(log, key=lambda e: -e.get("dropAt", 0))[:limit]


def get_drop_times() -> dict[int, int]:
  """Latest real drop per stage.

  When USE_METER_DROPS is on, tbh-meter's chestDropLog is AUTHORITATIVE — it
  reads game memory and logs every real drop within ~1s, for manual OR macro
  farming, so it overrides our self-model (which can mis-stamp). Our local log
  fills stages tbh-meter has no record of, and is the sole source when
  tbh-meter isn't running (independent mode)."""
  local = _load_local_drops()
  if not getattr(config, "USE_METER_DROPS", False):
    return local
  merged = dict(local)
  merged.update(_load_meter_drops())  # memory truth overrides our inference
  return merged


def bootstrap_from_meter() -> int:
  """One-time warm start: seed our local log from tbh-meter's drop history so we
  don't re-farm everything on first run. Optional; safe to skip for cold start."""
  meter = _load_meter_drops()
  if not meter:
    print("No tbh-meter drop history found; cold start (all targets READY).")
    return 0
  local = _load_local_drops()
  targets = {t.stage_key for t in get_targets()}
  seeded = 0
  for key, at in meter.items():
    if key in targets and at > local.get(key, 0):
      local[key] = at
      seeded += 1
  _atomic_write(LOCAL_STATE_PATH, json.dumps(local))
  print(f"Seeded {seeded} stage cooldowns from tbh-meter history.")
  return seeded


def get_status(now_ms: int | None = None) -> list[dict]:
  """Per-target cooldown state, newest-drop based. For the GUI and the loop."""
  now = int(time.time() * 1000) if now_ms is None else now_ms
  drops = get_drop_times()
  status = []
  for target in get_targets():
    drop_at = drops.get(target.stage_key, 0)
    ready_at = drop_at + COOLDOWN_MS if drop_at else 0
    status.append(
      {
        "key": target.key,
        "stage": f"{target.act}-{target.stage}",
        "act": target.act,
        "stageNo": target.stage,
        "difficulty": target.difficulty,
        "mode": target.mode,
        "level": target.level,
        "name": _STAGE_NAMES.get(str(target.stage_key)),
        "custom": target.custom,
        "lastDropAt": drop_at or None,
        "readyAt": ready_at or None,
        "ready": now >= ready_at,
        "secondsLeft": max(0, (ready_at - now) // 1000),
      }
    )
  return status


def get_ready_stages() -> list[ReadyStage]:
  """READY targets, highest chest level first (config order breaks ties)."""
  ready = [
    ReadyStage(
      label=s["stage"], act=s["act"], stage=s["stageNo"],
      difficulty=s["difficulty"], level=s["level"],
    )
    for s in get_status() if s["ready"]
  ]
  if getattr(config, "PRIORITIZE_BY_LEVEL", True):
    ready.sort(key=lambda s: -s.level)
  return ready
