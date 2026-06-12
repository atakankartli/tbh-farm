"""Local web GUI: blue-chest drop timers + what the macro is doing right now.

  python webgui.py          # standalone
  (main.py starts it automatically on a background thread)

Then open http://localhost:8765
"""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import chests
import config

STATUS_PATH = Path(__file__).with_name("macro_status.json")
SETTINGS_PATH = Path(__file__).with_name("macro_settings.json")   # GUI-toggled behavior
# Both OFF by default: starting the exe must not take over the mouse until
# the user flips the macro pill on the dashboard.
_DEFAULT_SETTINGS = {"stashEnabled": False, "macroEnabled": False}


def get_settings() -> dict:
  """Runtime toggles set from the GUI; main.py reads these every loop."""
  try:
    with open(SETTINGS_PATH, encoding="utf-8") as fh:
      data = json.load(fh)
  except (OSError, ValueError):
    data = {}
  return {**_DEFAULT_SETTINGS, **{k: v for k, v in data.items() if k in _DEFAULT_SETTINGS}}


def set_setting(key: str, value) -> dict:
  if key not in _DEFAULT_SETTINGS:
    raise ValueError(f"unknown setting {key!r}")
  if not isinstance(value, type(_DEFAULT_SETTINGS[key])):
    raise ValueError(f"{key} must be a {type(_DEFAULT_SETTINGS[key]).__name__}")
  settings = get_settings()
  settings[key] = value
  SETTINGS_PATH.write_text(json.dumps(settings), encoding="utf-8")
  return settings


def set_macro_status(phase: str, detail: str = "", target: str = "") -> None:
  """Called by main.py on every state change; the GUI shows it."""
  try:
    STATUS_PATH.write_text(
      json.dumps({"phase": phase, "detail": detail, "target": target, "updated": int(time.time() * 1000)}),
      encoding="utf-8",
    )
  except OSError:
    pass


def _read_json(path: str) -> dict | None:
  try:
    with open(path, encoding="utf-8") as fh:
      return json.load(fh)
  except (OSError, ValueError):
    return None


def _recent_drops(limit: int = 12) -> list[dict]:
  """Our own drop log. Optionally merge tbh-meter history if enabled."""
  drops = chests.recent_local_drops(limit)
  if getattr(config, "USE_METER_DROPS", False):
    settings = _read_json(chests._meter_settings_path()) or {}
    drops = drops + settings.get("chestDropLog", [])
    drops = sorted(drops, key=lambda e: -e.get("dropAt", 0))[:limit]
  return drops


def _live_run(save) -> dict:
  """Current run derived from the save (which stage we're parked on)."""
  if not save:
    return {}
  key = save.get("currentStage", 0)
  if not key:
    return {}
  diff = key // 1000
  act = (key % 1000) // 100
  stage = key % 100
  return {"act": act, "stageNo": stage, "difficulty": diff}


def _save_summary() -> dict | None:
  try:
    import savefile
    return savefile.summary()
  except Exception:
    return None


def build_state() -> dict:
  save = _save_summary()
  return {
    "now": int(time.time() * 1000),
    "chests": chests.get_status(),
    "macro": _read_json(str(STATUS_PATH)) or {"phase": "not running"},
    "live": _live_run(save),
    "recentDrops": _recent_drops(),
    "cooldownMin": getattr(config, "CHEST_COOLDOWN_MIN", 12),
    "save": save,
    "settings": get_settings(),
  }


INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TBH Blue-Chest Farm</title>
<style>
  :root{
    --bg:#0e0c0a; --bg2:#181410; --panel:#1d1813; --panel2:#241e17;
    --line:#3a2e1f; --line2:#4d3c27; --ink:#ece2d0; --muted:#9a876b; --dim:#6b5c47;
    --gold:#f0a830; --gold2:#ffce6b; --green:#74d063; --red:#ff7a7a; --purple:#c2a3ff;
  }
  *{box-sizing:border-box}
  body{background:radial-gradient(1200px 600px at 70% -10%,#241a10 0%,var(--bg) 60%);
    color:var(--ink); font:14px/1.5 'Segoe UI',system-ui,sans-serif; margin:0; padding:0 0 48px;
    overflow-x:hidden; -webkit-text-size-adjust:100%;}
  .wrap{max-width:1080px; margin:0 auto; padding:0 24px}
  /* header */
  header{position:sticky; top:0; z-index:10; backdrop-filter:blur(8px);
    background:linear-gradient(180deg,rgba(14,12,10,.95),rgba(14,12,10,.78));
    border-bottom:1px solid var(--line); margin-bottom:26px}
  .hbar{max-width:1080px; margin:0 auto; padding:16px 24px; display:flex; align-items:center; gap:14px}
  .logo{width:30px;height:30px;border-radius:8px;flex:none;
    background:linear-gradient(135deg,var(--gold2),#b9701a); box-shadow:0 0 18px rgba(240,168,48,.35);
    display:grid;place-items:center;font-size:16px}
  h1{font-size:16px; letter-spacing:2px; margin:0; color:var(--gold2); font-weight:700; text-transform:uppercase}
  .hsub{color:var(--dim); font-size:11px; letter-spacing:1px; margin-top:1px}
  .pills{margin-left:auto; display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end}
  .pill{display:flex; align-items:center; gap:7px; font-size:12px;
    background:var(--panel); border:1px solid var(--line); border-radius:999px; padding:6px 13px; color:var(--muted)}
  #savepill .rfx{color:var(--gold); font-size:13px}
  #stashpill.clickable,#macropill.clickable{cursor:pointer; user-select:none}
  #stashpill.clickable:hover,#macropill.clickable:hover{border-color:var(--line2)}
  #macropill.paused{border-color:#6a2020; color:var(--red)}
  .dot.red{background:var(--red); box-shadow:0 0 8px var(--red)}
  #savepill.stale{border-color:#6a4a20; color:var(--gold2)}
  #savepill.stale .rfx{color:var(--gold2)}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--green); box-shadow:0 0 8px var(--green)}
  .dot.busy{background:var(--gold); box-shadow:0 0 8px var(--gold); animation:pulse 1.1s infinite}
  .dot.off{background:var(--dim); box-shadow:none}
  @keyframes pulse{50%{opacity:.35}}
  /* status strip */
  .status{display:flex; flex-wrap:wrap; gap:10px 22px; align-items:center;
    background:linear-gradient(180deg,var(--panel2),var(--panel)); border:1px solid var(--line);
    border-radius:14px; padding:14px 18px; margin-bottom:14px}
  .status .phase{font-weight:700; letter-spacing:1px; text-transform:uppercase; font-size:12px;
    color:#15110b; background:var(--gold); padding:4px 11px; border-radius:7px}
  .status .detail{color:var(--ink); font-size:13px}
  .status .run{color:var(--muted); font-size:12px; margin-left:auto}
  .status .run b{color:var(--gold2); font-weight:600}
  /* stat tiles */
  .tiles{display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:30px}
  .tile{background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:13px 15px}
  .tile .k{color:var(--dim); font-size:10px; letter-spacing:1.4px; text-transform:uppercase}
  .tile .v{font-size:20px; font-weight:700; margin-top:3px; font-variant-numeric:tabular-nums}
  .tile .v small{font-size:12px; color:var(--muted); font-weight:400}
  .tile.warn{border-color:#6a2020; background:linear-gradient(180deg,#2a1414,var(--panel))}
  .tile.warn .v{color:var(--red)}
  /* section label */
  .seclabel{display:flex; align-items:center; gap:10px; margin:0 0 14px; color:var(--muted);
    font-size:11px; letter-spacing:2px; text-transform:uppercase}
  .seclabel::after{content:""; flex:1; height:1px; background:linear-gradient(90deg,var(--line),transparent)}
  /* chest cards */
  .cards{display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:14px; margin-bottom:34px}
  .card{position:relative; overflow:hidden; background:linear-gradient(180deg,var(--panel2),var(--panel));
    border:1px solid var(--line); border-radius:16px; padding:18px; transition:border-color .3s, transform .15s, box-shadow .3s}
  .card:hover{transform:translateY(-2px)}
  .card.rdy{border-color:rgba(116,208,99,.6); box-shadow:0 0 0 1px rgba(116,208,99,.25),0 8px 30px -12px rgba(116,208,99,.4)}
  .card .top{display:flex; align-items:center; gap:8px; margin-bottom:14px}
  .card .stage{font-size:17px; font-weight:700; letter-spacing:.5px}
  .card .lv{margin-left:auto; font-size:12px; color:var(--gold2); font-weight:600;
    background:rgba(240,168,48,.12); padding:2px 8px; border-radius:6px}
  .chip{font-size:10px; font-weight:700; letter-spacing:.5px; padding:2px 8px; border-radius:6px; text-transform:uppercase}
  .Hell{background:#3a1414; color:var(--red); border:1px solid #5a1c1c}
  .Nightmare{background:#241a3a; color:var(--purple); border:1px solid #3a2a55}
  .Normal{background:#16280f; color:var(--green); border:1px solid #28401f}
  .Torment{background:#102b33; color:#6ad0ff; border:1px solid #1c4a5a}
  .gauge{display:flex; align-items:center; gap:16px}
  .ring{--p:0; --c:var(--gold); width:84px;height:84px;border-radius:50%; flex:none;
    background:conic-gradient(var(--c) calc(var(--p)*1%), #2a2117 0);
    display:grid; place-items:center; transition:--p .9s linear}
  @property --p{syntax:'<number>';inherits:false;initial-value:0}
  .ring::before{content:""; position:absolute; width:64px;height:64px;border-radius:50%; background:var(--panel)}
  .ring .lab{position:relative; text-align:center; line-height:1.1}
  .ring .t{font-size:18px; font-weight:700; font-variant-numeric:tabular-nums}
  .ring .u{font-size:9px; color:var(--dim); letter-spacing:1px; text-transform:uppercase}
  .ring.rdy{--c:var(--green)} .ring.rdy .t{font-size:14px; color:var(--green); letter-spacing:1px}
  .meta{font-size:11px; color:var(--muted); line-height:1.6}
  .meta .name{color:var(--ink); font-weight:600; font-size:12px; display:block; margin-bottom:2px}
  /* add-dungeon */
  .addbtn{margin-left:8px; background:rgba(240,168,48,.1); color:var(--gold2); border:1px solid var(--line2);
    border-radius:999px; padding:3px 12px; font:600 11px 'Segoe UI',system-ui,sans-serif; letter-spacing:1px;
    text-transform:uppercase; cursor:pointer}
  .addbtn:hover{border-color:var(--gold); background:rgba(240,168,48,.18)}
  .addform{display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:0 0 14px;
    background:var(--panel); border:1px solid var(--line2); border-radius:12px; padding:12px 14px}
  .addform select,.addform input{background:var(--bg2); color:var(--ink); border:1px solid var(--line2);
    border-radius:8px; padding:7px 10px; font:13px 'Segoe UI',system-ui,sans-serif}
  .addform input{width:84px}
  .addform .go{background:var(--gold); color:#15110b; border:0; border-radius:8px; padding:8px 16px;
    font-weight:700; cursor:pointer}
  .addform .go:hover{background:var(--gold2)}
  .addform .err{color:var(--red); font-size:12px}
  .lv.edit{cursor:pointer}
  .lv.edit:hover{background:rgba(240,168,48,.28)}
  .card .rm{position:absolute; top:10px; right:10px; z-index:1; width:22px; height:22px; border-radius:6px;
    background:transparent; color:var(--dim); border:1px solid transparent; font-size:14px; line-height:1;
    cursor:pointer; display:grid; place-items:center}
  .card .rm:hover{color:var(--red); border-color:#5a1c1c; background:#2a1414}
  /* drops table */
  .tbl{background:var(--panel); border:1px solid var(--line); border-radius:14px; overflow:hidden}
  table{width:100%; border-collapse:collapse; font-size:13px}
  th,td{text-align:left; padding:11px 18px}
  th{color:var(--dim); font-weight:600; font-size:10px; text-transform:uppercase; letter-spacing:1.4px;
    background:var(--bg2); border-bottom:1px solid var(--line)}
  tbody tr{border-bottom:1px solid #241d14} tbody tr:last-child{border:0}
  tbody tr:hover{background:rgba(240,168,48,.04)}
  td.stg{font-weight:600}
  .empty{padding:26px; text-align:center; color:var(--dim)}
  .muted{color:var(--muted)}
  /* party */
  .party{display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:14px; margin-bottom:34px}
  .hero{display:flex; gap:14px; align-items:center; background:linear-gradient(180deg,var(--panel2),var(--panel));
    border:1px solid var(--line); border-radius:16px; padding:14px 16px}
  .hero .portrait{width:58px; height:84px; flex:none; border-radius:10px; image-rendering:pixelated;
    object-fit:contain; background:radial-gradient(40px 40px at 50% 40%,#2c2418,#171209); border:1px solid var(--line)}
  .hero .cls{font-weight:700; font-size:16px}
  .hero .hlv{margin-top:2px}
  .hero .lvl{color:var(--gold2); font-weight:700; font-size:13px}
  .hero .xp{font-size:11px; color:var(--muted); margin-top:7px}
  .hero .gear{font-size:11px; color:var(--dim); margin-top:2px}
  .Knight{--rc:#d8c27a}.Ranger{--rc:#8fd06a}.Sorcerer{--rc:#c2a3ff}.Priest{--rc:#ffce6b}.Hunter{--rc:#6ad0c0}.Slayer{--rc:#ff8f6a}
  .hero .cls{color:var(--rc,#ece2d0)}
  .tbl{overflow-x:auto}
  /* phones */
  @media (max-width:640px){
    body{-webkit-text-size-adjust:100%; padding-bottom:28px}
    .wrap{padding:0 12px}
    header{margin-bottom:18px}
    .hbar{padding:11px 12px; gap:10px}
    .logo{width:26px;height:26px;font-size:14px}
    h1{font-size:13px;letter-spacing:1px} .hsub{font-size:9px}
    .pill{padding:5px 10px;font-size:11px}
    .status{padding:12px 14px;gap:7px 12px;border-radius:12px}
    .status .phase{font-size:11px}.status .detail{font-size:12px}
    .status .run{margin-left:0;width:100%;font-size:11px}
    .tiles{grid-template-columns:repeat(2,1fr);gap:9px;margin-bottom:22px}
    .tile{padding:11px 13px;border-radius:11px}.tile .v{font-size:18px}
    .seclabel{margin-bottom:11px;font-size:10px}
    .party,.cards{grid-template-columns:1fr;gap:11px;margin-bottom:26px}
    .hero{padding:12px 14px}.hero .portrait{width:50px;height:72px}
    .card{padding:15px;border-radius:14px}
    .ring{width:74px;height:74px}.ring::before{width:56px;height:56px}
    .ring .t{font-size:16px}
    th,td{padding:9px 12px}td.stg,th{font-size:12px}
  }
  @media (max-width:380px){ .tiles{grid-template-columns:1fr 1fr;gap:8px} .tile .v{font-size:16px} }
</style></head><body>
<header><div class="hbar">
  <div class="logo">&#x1F4E6;</div>
  <div><h1>Blue-Chest Farm</h1><div class="hsub">STAGE-BOSS CHESTS &middot; <span id="cd">12</span>-MIN DUNGEON TIMER</div></div>
  <div class="pills">
    <div class="pill" id="macropill" title="Master switch: when off, the macro never touches the mouse (click to toggle)">
      <span class="dot" id="macrodot"></span><span id="macrolabel">macro</span></div>
    <div class="pill" id="stashpill" title="Stash loot after each cleared run (click to toggle)">
      <span class="dot" id="stashdot"></span><span id="stashlabel">stash</span></div>
    <div class="pill" id="savepill" title="When the game last wrote its save (it saves every ~1-2 min)">
      <span class="rfx">&#x21BB;</span><span id="saveage">&mdash;</span></div>
    <div class="pill"><span class="dot off" id="livedot"></span><span id="livelabel">connecting&hellip;</span></div>
  </div>
</div></header>
<div class="wrap">
  <div class="status">
    <span class="phase" id="phase">&mdash;</span>
    <span class="detail" id="detail"></span>
    <span class="run" id="liverun"></span>
  </div>
  <div class="tiles" id="tiles"></div>
  <div class="seclabel" id="partylabel" style="display:none">Party</div>
  <div class="party" id="party"></div>
  <div class="seclabel">Chest Timers
    <button class="addbtn" id="addbtn" type="button">+ Add Dungeon</button></div>
  <div class="addform" id="addform" style="display:none">
    <select id="f_diff"></select>
    <select id="f_stage"></select>
    <input id="f_level" type="number" min="0" placeholder="level">
    <button class="go" id="f_go" type="button">Add</button>
    <span class="err" id="f_err"></span>
  </div>
  <div class="cards" id="cards"></div>
  <div class="seclabel">Recent Drops</div>
  <div class="tbl"><table><thead><tr><th>Stage</th><th>Mode</th><th>Dropped</th></tr></thead>
    <tbody id="drops"></tbody></table></div>
</div>
<script>
const MODE=["?","Normal","Nightmare","Hell","Torment"];
const CAN_EDIT=!window.RAW_STATE; // the published GitHub Pages mirror is read-only
let state=null, ok=false;
const $=id=>document.getElementById(id);
function fmt(s){const m=Math.floor(s/60),x=s%60;return m+":"+String(x).padStart(2,"0")}
function ago(ms){const s=Math.max(0,Math.floor((Date.now()-ms)/1000));
  return s<60?s+"s ago":s<3600?Math.floor(s/60)+"m ago":Math.floor(s/3600)+"h "+Math.floor(s%3600/60)+"m ago"}
function nfmt(n){return n>=1e6?(n/1e6).toFixed(1)+"M":n>=1e3?(n/1e3).toFixed(1)+"K":""+n}

function render(){
  if(!state) return;
  const cdMs=state.cooldownMin*60000;
  $("cd").textContent=state.cooldownMin;

  // live connection pill
  const m=state.macro||{}, busy=m.phase&&!/wait|idle|not running/i.test(m.phase);
  $("livedot").className="dot "+(!ok?"off":busy?"busy":"");
  $("livelabel").textContent=!ok?"offline":busy?"working":"online";

  // master switch (main.py idles without touching the mouse when off)
  const macroOn=!state.settings||state.settings.macroEnabled!==false;
  $("macrolabel").textContent="macro "+(macroOn?"on":"paused");
  $("macrodot").className="dot"+(macroOn?"":" red");
  $("macropill").classList.toggle("paused",!macroOn);

  // stash toggle (main.py skips 'Stash All' after runs when off)
  const stashOn=!state.settings||state.settings.stashEnabled!==false;
  $("stashlabel").textContent="stash "+(stashOn?"on":"off");
  $("stashdot").className="dot"+(stashOn?"":" off");

  // save freshness (game flushes its save every ~1-2 min)
  const fm=state.save&&state.save.fileModified;
  if(fm){
    const age=Math.max(0,Math.floor((Date.now()-fm)/1000));
    $("saveage").textContent="saved "+(age<60?age+"s":Math.floor(age/60)+"m "+(age%60)+"s")+" ago";
    $("savepill").className="pill"+(age>150?" stale":"");
  } else { $("saveage").textContent="no save"; }

  // status strip
  $("phase").textContent=(m.phase||"idle").toUpperCase();
  $("detail").textContent=(m.target?m.target+"  ":"")+(m.detail||"");
  const lv=state.live||{};
  $("liverun").innerHTML=lv.act
    ? `STAGE <b>${lv.act}-${lv.stageNo}</b> ${MODE[lv.difficulty??0]||""}` : "";

  // stat tiles
  const sv=state.save, readyN=state.chests.filter(c=>!c.readyAt||Date.now()>=c.readyAt).length;
  const tiles=[["Ready Now",readyN+" / "+state.chests.length,readyN>0]];
  if(sv){
    const full=sv.stash.free===0;
    tiles.push(["Party Level","Lv"+sv.maxPartyLevel]);
    tiles.push(["Gold",nfmt(sv.gold)]);
    tiles.push(["Stash Free",sv.stash.free+" <small>/ "+sv.stash.unlocked+"</small>",false,full]);
  }
  $("tiles").innerHTML=tiles.map(([k,v,hot,warn])=>
    `<div class="tile${warn?" warn":""}"><div class="k">${k}</div><div class="v" style="${hot?"color:var(--green)":""}">${v}</div></div>`).join("");

  // party heroes
  const SPRITE_BASE=window.SPRITE_BASE||"/sprites/";
  const heroes=(sv&&sv.partyHeroes)||[];
  $("partylabel").style.display=heroes.length?"":"none";
  $("party").innerHTML=heroes.map(h=>`
    <div class="hero ${h.cls}">
      <img class="portrait" src="${SPRITE_BASE}heroes/${h.sprite}" alt="${h.cls}" onerror="this.style.visibility='hidden'">
      <div>
        <div class="cls">${h.cls}</div>
        <div class="hlv"><span class="lvl">Lv${h.level}</span></div>
        <div class="xp">${nfmt(Math.round(h.exp||0))} XP</div>
        <div class="gear">${h.gear}/9 gear equipped</div>
      </div>
    </div>`).join("");

  // chest cards
  $("cards").innerHTML=state.chests.map(c=>{
    const left=c.readyAt?Math.max(0,Math.floor((c.readyAt-Date.now())/1000)):0;
    const ready=left<=0;
    const pct=c.readyAt?Math.min(100,100*(1-left*1000/cdMs)):100;
    return `<div class="card ${ready?"rdy":""}">
      ${CAN_EDIT?`<button class="rm" title="Stop farming ${c.key}" onclick="removeTarget('${c.key}')">&times;</button>`:""}
      <div class="top"><span class="stage">${c.stage}</span><span class="chip ${c.mode}">${c.mode}</span><span class="lv${CAN_EDIT?" edit":""}" ${CAN_EDIT?`onclick="editLevel('${c.key}',${c.level})" title="chest level — drops are matched by it (click to change)"`:""}>Lv${c.level}</span></div>
      <div class="gauge">
        <div class="ring ${ready?"rdy":""}" style="--p:${pct}"><div class="lab">
          ${ready?'<div class="t">READY</div>':`<div class="t">${fmt(left)}</div><div class="u">left</div>`}
        </div></div>
        <div class="meta">${c.name?`<span class="name">${c.name}</span>`:""}
          ${c.lastDropAt?"last drop<br>"+ago(c.lastDropAt):"no drop recorded yet"}</div>
      </div></div>`;
  }).join("");

  // drops
  const dr=state.recentDrops||[];
  $("drops").innerHTML=dr.length? dr.map(d=>
    `<tr><td class="stg">${d.stage}</td><td><span class="chip ${d.mode}">${d.mode}</span></td><td class="muted">${ago(d.dropAt)}</td></tr>`).join("")
    : `<tr><td colspan="3" class="empty">No drops recorded yet</td></tr>`;
}
// add/remove farm targets (local GUI only)
let STAGES=null;
async function openAddForm(){
  const f=$("addform");
  if(f.style.display!=="none"){f.style.display="none";return}
  if(!STAGES){
    try{STAGES=(await (await fetch("/stages")).json()).stages}catch(e){STAGES=[]}
    const diffs=[...new Set(STAGES.map(s=>s.difficulty))];
    $("f_diff").innerHTML=diffs.map(d=>`<option>${d}</option>`).join("");
    $("f_diff").onchange=fillStages; fillStages();
  }
  $("f_err").textContent=""; f.style.display="";
}
function fillStages(){
  const d=$("f_diff").value, sel=$("f_stage");
  sel.innerHTML=STAGES.filter(s=>s.difficulty===d).map(s=>
    `<option value="${s.spec}" data-lvl="${s.level}">${s.act}-${s.stage}${s.name?" · "+s.name:""} (Lv${s.level})</option>`).join("");
  sel.onchange=()=>{const o=sel.selectedOptions[0]; $("f_level").placeholder="Lv"+((o&&o.dataset.lvl)||"?")};
  sel.onchange();
}
async function addTarget(){
  $("f_err").textContent="";
  try{
    const r=await fetch("/targets/add",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({spec:$("f_stage").value,level:$("f_level").value||null})});
    const j=await r.json();
    if(!j.ok){$("f_err").textContent=j.error||"failed";return}
    $("f_level").value=""; $("addform").style.display="none"; poll();
  }catch(e){$("f_err").textContent="request failed"}
}
async function editLevel(key,current){
  const v=prompt("Chest level for "+key+" (drops are matched by item key 920<level>1; 0 = match any):",current);
  if(v===null)return;
  const lvl=parseInt(v,10);
  if(isNaN(lvl)||lvl<0||lvl>99){alert("level must be 0-99");return}
  try{
    const r=await fetch("/targets/level",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({spec:key,level:lvl})});
    const j=await r.json();
    if(!j.ok)alert(j.error||"failed");
  }catch(e){alert("request failed")}
  poll();
}
async function removeTarget(key){
  if(!confirm("Stop farming "+key+"? Its drop history is kept."))return;
  try{
    const r=await fetch("/targets/remove",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({spec:key})});
    const j=await r.json();
    if(!j.ok)alert(j.error||"failed");
  }catch(e){alert("request failed")}
  poll();
}
async function toggleSetting(key){
  const on=!state||!state.settings||state.settings[key]!==false;
  try{
    await fetch("/settings",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({[key]:!on})});
  }catch(e){}
  poll();
}
if(CAN_EDIT){
  $("addbtn").onclick=openAddForm;$("f_go").onclick=addTarget;
  $("stashpill").classList.add("clickable");$("stashpill").onclick=()=>toggleSetting("stashEnabled");
  $("macropill").classList.add("clickable");$("macropill").onclick=()=>toggleSetting("macroEnabled");
}else{$("addbtn").style.display="none"}
const STATE_URL=window.STATE_URL||"/state";
async function poll(){
  try{
    state = window.STATE_FETCH ? await window.STATE_FETCH()
                               : await (await fetch(STATE_URL,{cache:"no-store"})).json();
    ok=true;
  }catch(e){ ok=false; if(window.ON_FETCH_ERROR) window.ON_FETCH_ERROR(e); }
  render();
}
setInterval(render,1000); setInterval(poll,3000); poll();
</script></body></html>"""


SPRITES_DIR = Path(__file__).with_name("sprites")


class _Handler(BaseHTTPRequestHandler):
  def _send_json(self, obj: dict, code: int = 200) -> None:
    body = json.dumps(obj).encode()
    self.send_response(code)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def do_POST(self):  # noqa: N802 — GUI actions: farm targets, behavior toggles
    if self.path not in ("/targets/add", "/targets/remove", "/targets/level", "/settings"):
      self.send_error(404)
      return
    try:
      length = int(self.headers.get("Content-Length") or 0)
      payload = json.loads(self.rfile.read(length) or b"{}")
    except ValueError:
      self._send_json({"ok": False, "error": "bad JSON body"}, 400)
      return
    spec = str(payload.get("spec", "")).strip()
    try:
      if self.path == "/settings":
        settings = get_settings()
        for key, value in payload.items():
          settings = set_setting(key, value)
        self._send_json({"ok": True, "settings": settings})
      elif self.path == "/targets/add":
        level = payload.get("level")
        target = chests.add_target(spec, int(level) if level not in (None, "") else None)
        self._send_json({"ok": True, "key": target.key, "level": target.level})
      elif self.path == "/targets/level":
        target = chests.set_target_level(spec, int(payload.get("level", -1)))
        self._send_json({"ok": True, "key": target.key, "level": target.level})
      elif chests.remove_target(spec):
        self._send_json({"ok": True})
      else:
        self._send_json({"ok": False, "error": f"{spec} is not a farm target"}, 400)
    except ValueError as exc:
      self._send_json({"ok": False, "error": str(exc)}, 400)

  def do_GET(self):  # noqa: N802
    if self.path == "/state":
      body = json.dumps(build_state()).encode()
      ctype = "application/json"
    elif self.path == "/stages":
      body = json.dumps({"stages": chests.all_stages()}).encode()
      ctype = "application/json"
    elif self.path == "/":
      body = INDEX_HTML.encode()
      ctype = "text/html; charset=utf-8"
    elif self.path.startswith("/sprites/"):
      rel = self.path[len("/sprites/"):].split("?")[0].lstrip("/")
      target = (SPRITES_DIR / rel).resolve()
      if SPRITES_DIR.resolve() in target.parents and target.is_file():
        body = target.read_bytes()
        ctype = "image/png"
      else:
        self.send_error(404)
        return
    else:
      self.send_error(404)
      return
    self.send_response(200)
    self.send_header("Content-Type", ctype)
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def log_message(self, *args):  # silence per-request console spam
    pass


def _lan_ip() -> str | None:
  import socket
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  try:
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]
  except OSError:
    return None
  finally:
    s.close()


def serve(port: int | None = None, host: str | None = None) -> ThreadingHTTPServer:
  port = port or getattr(config, "WEBGUI_PORT", 8765)
  host = host or getattr(config, "WEBGUI_HOST", "0.0.0.0")
  server = ThreadingHTTPServer((host, port), _Handler)
  print(f"Web GUI:  http://localhost:{port}")
  if host == "0.0.0.0":
    ip = _lan_ip()
    if ip:
      print(f"  phone (same Wi-Fi):  http://{ip}:{port}")
  return server


def start_tunnel(port: int | None = None) -> None:
  """Launch a free Cloudflare quick tunnel (public https URL, no signup).
  Requires `cloudflared` on PATH (winget install Cloudflare.cloudflared)."""
  import shutil
  import subprocess

  port = port or getattr(config, "WEBGUI_PORT", 8765)
  exe = shutil.which("cloudflared")
  if not exe:
    print("  tunnel: cloudflared not installed — run: winget install Cloudflare.cloudflared")
    return

  def run() -> None:
    proc = subprocess.Popen(
      [exe, "tunnel", "--url", f"http://localhost:{port}"],
      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    for line in proc.stdout:
      if "trycloudflare.com" in line:
        url = line[line.find("https://"):].split()[0].strip()
        print(f"\n  PUBLIC URL (open on phone): {url}\n")

  threading.Thread(target=run, daemon=True).start()


def start_in_background(tunnel: bool | None = None) -> None:
  server = serve()
  threading.Thread(target=server.serve_forever, daemon=True).start()
  want_tunnel = tunnel if tunnel is not None else getattr(config, "WEBGUI_TUNNEL", False)
  if want_tunnel:
    start_tunnel()


if __name__ == "__main__":
  import sys

  server = serve()
  if "--tunnel" in sys.argv or getattr(config, "WEBGUI_TUNNEL", False):
    start_tunnel()
  server.serve_forever()
