from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import config
from tracker import ReadyStage

DUNGEONS_PATH = Path(__file__).with_name("dungeons.json")
_ROUTE_KEY_RE = re.compile(r"^(\d+)-(\d+):(HELL|NIGHTMARE|NORMAL)$", re.IGNORECASE)


@dataclass(frozen=True)
class ClickStep:
  x: int
  y: int
  delay: float = 0.25
  label: str = ""


@dataclass(frozen=True)
class DungeonRoute:
  key: str
  name: str
  difficulty: str
  act: int
  stage: int
  clicks: tuple[ClickStep, ...]


def normalize_difficulty(value: str) -> str:
  upper = value.strip().upper()
  if upper not in config.DIFFICULTY_LABELS:
    known = ", ".join(config.DIFFICULTY_LABELS)
    raise ValueError(f"Unknown difficulty '{value}'. Use one of: {known}")
  return upper


def stage_key(stage: ReadyStage) -> str:
  return f"{stage.act}-{stage.stage}:{normalize_difficulty(stage.difficulty)}"


def _parse_route_key(key: str) -> tuple[int, int, str]:
  match = _ROUTE_KEY_RE.match(key.strip().upper())
  if not match:
    raise ValueError(f"Invalid route key '{key}'. Expected act-stage:DIFFICULTY e.g. 2-5:HELL")
  return int(match.group(1)), int(match.group(2)), match.group(3)


def build_clicks_from_portal(act: int, stage: int, difficulty: str) -> tuple[ClickStep, ...]:
  """4 clicks: open difficulty -> pick difficulty -> act -> dungeon."""
  difficulty = normalize_difficulty(difficulty)
  ui = config.PORTAL_UI
  delay = float(ui.get("step_delay", 0.25))

  dropdown = ui.get("difficulty_dropdown")
  if not dropdown:
    raise KeyError("Missing difficulty_dropdown in config.PORTAL_UI — run calibrate_portal.py difficulty")

  diff_point = ui["difficulty_options"].get(difficulty)
  if not diff_point:
    raise KeyError(f"No click for difficulty {difficulty} in config.PORTAL_UI")

  act_point = ui["act_tabs"].get(act)
  if not act_point:
    raise KeyError(f"No act tab calibrated for act {act} in config.PORTAL_UI")

  diff_label = config.DIFFICULTY_LABELS[difficulty]
  open_delay = float(ui.get("dropdown_open_delay", 0.4))
  return (
    ClickStep(dropdown[0], dropdown[1], open_delay, "1 open difficulty"),
    ClickStep(diff_point[0], diff_point[1], delay, f"2 difficulty ({diff_label})"),
    ClickStep(act_point[0], act_point[1], delay, f"3 act {act}"),
    ClickStep(0, 0, delay, f"4 dungeon {act}-{stage}"),
  )


def _clicks_from_entry(entry: dict, act: int, stage: int, difficulty: str) -> tuple[ClickStep, ...]:
  if "clicks" in entry:
    return tuple(
      ClickStep(
        x=int(step["x"]),
        y=int(step["y"]),
        delay=float(step.get("delay", config.PORTAL_UI.get("step_delay", 0.25))),
        label=str(step.get("label", "")),
      )
      for step in entry["clicks"]
    )

  node = entry.get("node")
  if not node:
    raise ValueError("Route needs either 'node' [x,y] or a full 'clicks' list")

  built = list(build_clicks_from_portal(act, stage, difficulty))
  built[-1] = ClickStep(int(node[0]), int(node[1]), built[-1].delay, built[-1].label)
  return tuple(built)


def load_routes() -> dict[str, DungeonRoute]:
  if not DUNGEONS_PATH.exists():
    raise FileNotFoundError(f"Missing {DUNGEONS_PATH.name} — run record_combo.py to add routes")

  raw = json.loads(DUNGEONS_PATH.read_text(encoding="utf-8"))
  routes: dict[str, DungeonRoute] = {}

  for key, entry in raw.items():
    if key.startswith("_"):
      continue
    act, stage, difficulty = _parse_route_key(key)
    clicks = _clicks_from_entry(entry, act, stage, difficulty)
    upper_key = f"{act}-{stage}:{difficulty}"
    routes[upper_key] = DungeonRoute(
      key=upper_key,
      name=str(entry.get("name", upper_key)),
      difficulty=difficulty,
      act=act,
      stage=stage,
      clicks=clicks,
    )
  return routes


def get_route(stage: ReadyStage) -> DungeonRoute:
  routes = load_routes()
  key = stage_key(stage)
  route = routes.get(key)
  if route:
    return route

  known = ", ".join(sorted(routes)) or "(none)"
  raise KeyError(f"No route for {key}. Add it to dungeons.json. Known: {known}")
