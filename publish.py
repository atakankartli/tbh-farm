"""Publish a password-protected dashboard to GitHub Pages — plain git, no gh CLI.

GitHub Pages is static and can't password-protect, so we publish the state
AES-encrypted: the page prompts for the password and decrypts in the browser
(WebCrypto). Without the password the data is unreadable ciphertext.

Layout: the project code lives on `main`; the live site (index.html + the
encrypted state.json) lives on the `gh-pages` branch in a separate working
copy (PUBLISH_DIR), force-pushed with one rolling commit so history stays flat
and the code branch is never disturbed.

One-time setup (uses your stored git credential):
    python publish.py --setup        # push code, create gh-pages site, enable Pages, print URL
Then:
    python publish.py                # publish loop (also auto-runs from main.py if enabled)
    python publish.py --once         # single encrypted push
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from Crypto.Cipher import AES

import config
import webgui

PROJECT_DIR = Path(__file__).parent
PUBLISH_DIR = Path(getattr(config, "PUBLISH_DIR", os.path.expanduser(r"~\tbh-farm-site")))
USER = getattr(config, "GITHUB_USER", "atakankartli")
REPO = getattr(config, "GITHUB_REPO", "tbh-farm")
PASSWORD = getattr(config, "SITE_PASSWORD", "changeme")
INTERVAL = getattr(config, "PUBLISH_INTERVAL", 90)
PBKDF2_ITERS = 150_000
COMMIT_MSG = "live state"
REMOTE = f"https://github.com/{USER}/{REPO}.git"


def _run(args, cwd=None, check=True, quiet=False):
  r = subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
  if not quiet and r.stdout.strip():
    print("   ", r.stdout.strip().replace("\n", "\n    "))
  if check and r.returncode != 0:
    raise RuntimeError(f"{' '.join(args)} failed:\n{r.stderr.strip()}")
  return r


def _token() -> str:
  r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                     text=True, capture_output=True)
  for line in r.stdout.splitlines():
    if line.startswith("password="):
      return line[len("password="):]
  raise RuntimeError("No stored GitHub credential found (git credential fill returned nothing)")


# --------------------------------------------------------------- encryption

def _b64(b: bytes) -> str:
  return base64.b64encode(b).decode()


def encrypt_state(plaintext: bytes, password: str) -> dict:
  """AES-256-GCM with a PBKDF2-SHA256 key. Layout matches WebCrypto on the page:
  ciphertext has the 16-byte GCM tag appended."""
  salt, iv = os.urandom(16), os.urandom(12)
  key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERS, 32)
  ct, tag = AES.new(key, AES.MODE_GCM, nonce=iv).encrypt_and_digest(plaintext)
  return {"v": 1, "iter": PBKDF2_ITERS, "salt": _b64(salt), "iv": _b64(iv), "ct": _b64(ct + tag)}


# ----------------------------------------------------------- site generation

_GATE = """
<style>
  #gate{position:fixed;inset:0;z-index:100;display:grid;place-items:center;
    background:radial-gradient(800px 400px at 50% 20%,#241a10,#0e0c0a 70%)}
  #gate .box{background:linear-gradient(180deg,#241e17,#1d1813);border:1px solid #4d3c27;
    border-radius:16px;padding:32px 28px;width:300px;text-align:center;box-shadow:0 20px 60px -20px #000}
  #gate .lk{font-size:30px}#gate h2{color:#ffce6b;margin:10px 0 4px;font:700 16px 'Segoe UI';letter-spacing:1px}
  #gate p{color:#9a876b;font:12px 'Segoe UI';margin:0 0 18px}
  #gate input{width:100%;padding:11px 13px;border-radius:9px;border:1px solid #4d3c27;background:#15110b;
    color:#ece2d0;font-size:14px;outline:none}#gate input:focus{border-color:#f0a830}
  #gate button{width:100%;margin-top:12px;padding:11px;border:0;border-radius:9px;cursor:pointer;
    background:linear-gradient(135deg,#ffce6b,#b9701a);color:#15110b;font-weight:700;font-size:14px}
  #gate .err{color:#ff7a7a;font:12px 'Segoe UI';margin-top:12px;min-height:14px}
</style>
<div id="gate"><div class="box">
  <div class="lk">&#x1F512;</div><h2>BLUE-CHEST FARM</h2><p>Enter password to view</p>
  <input id="pw" type="password" placeholder="Password" autocomplete="current-password">
  <button id="go">Unlock</button><div class="err" id="gerr"></div>
</div></div>
<script>
const b64d=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
async function deriveKey(pw,salt,iter){
  const base=await crypto.subtle.importKey('raw',new TextEncoder().encode(pw),'PBKDF2',false,['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:iter,hash:'SHA-256'},base,
    {name:'AES-GCM',length:256},false,['decrypt']);
}
async function decryptEnvelope(env,pw){
  const key=await deriveKey(pw,b64d(env.salt),env.iter||150000);
  const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:b64d(env.iv)},key,b64d(env.ct));
  return JSON.parse(new TextDecoder().decode(pt));
}
window.STATE_FETCH=async function(){
  const pw=sessionStorage.getItem('tbhpw'); if(!pw) throw new Error('locked');
  const env=await (await fetch('state.json?t='+Date.now(),{cache:'no-store'})).json();
  const st=await decryptEnvelope(env,pw);           // throws on wrong password
  document.getElementById('gate').style.display='none';
  return st;
};
window.ON_FETCH_ERROR=function(e){
  if(String(e).includes('locked')||String(e&&e.name).includes('Operation')) showGate();
};
function showGate(){document.getElementById('gate').style.display='grid';}
async function unlock(){
  const pw=document.getElementById('pw').value, err=document.getElementById('gerr');
  err.textContent='checking...';
  try{
    const env=await (await fetch('state.json?t='+Date.now(),{cache:'no-store'})).json();
    await decryptEnvelope(env,pw);                  // validate before storing
    sessionStorage.setItem('tbhpw',pw); err.textContent=''; poll();
  }catch(e){ err.textContent='Wrong password'; }
}
document.getElementById('go').onclick=unlock;
document.getElementById('pw').addEventListener('keydown',e=>{if(e.key==='Enter')unlock();});
if(sessionStorage.getItem('tbhpw')) poll(); else showGate();
</script>
"""


def _static_html() -> str:
  html = webgui.INDEX_HTML
  # the gate drives poll() itself, so neutralise the built-in auto-start loop
  html = html.replace("setInterval(render,1000); setInterval(poll,3000); poll();",
                      "setInterval(render,1000); setInterval(()=>{if(sessionStorage.getItem('tbhpw'))poll();},3000);")
  # sprites are published next to index.html (relative path, not the local /sprites/ route)
  html = html.replace("</head>", '<script>window.SPRITE_BASE="sprites/";</script></head>', 1)
  return html.replace("</body>", _GATE + "</body>", 1)


def _write_site() -> None:
  import shutil
  PUBLISH_DIR.mkdir(parents=True, exist_ok=True)
  (PUBLISH_DIR / "index.html").write_text(_static_html(), encoding="utf-8")
  (PUBLISH_DIR / ".nojekyll").write_text("", encoding="utf-8")
  src = PROJECT_DIR / "sprites"
  if src.is_dir():
    shutil.copytree(src, PUBLISH_DIR / "sprites", dirs_exist_ok=True)
  _write_state()


def _write_state() -> None:
  plaintext = json.dumps(webgui.build_state()).encode("utf-8")
  env = encrypt_state(plaintext, PASSWORD)
  (PUBLISH_DIR / "state.json").write_text(json.dumps(env), encoding="utf-8")


# -------------------------------------------------------------------- setup

def _enable_pages() -> None:
  import urllib.error
  import urllib.request

  token = _token()
  body = json.dumps({"source": {"branch": "gh-pages", "path": "/"}}).encode()
  for method in ("POST", "PUT"):
    req = urllib.request.Request(
      f"https://api.github.com/repos/{USER}/{REPO}/pages", data=body, method=method,
      headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
    )
    try:
      urllib.request.urlopen(req)
      print(f"  Pages enabled ({method}).")
      return
    except urllib.error.HTTPError as e:
      if e.code in (409, 422):  # already exists / already configured
        print("  Pages already enabled.")
        return
  print("  Could not enable Pages via API — enable it manually: Settings > Pages > branch gh-pages /(root)")


def setup() -> None:
  print(f"Repo: {USER}/{REPO}")

  # 1) push the project code to main
  if not (PROJECT_DIR / ".git").exists():
    _run(["git", "init", "-b", "main"], cwd=PROJECT_DIR)
  _run(["git", "config", "user.name", USER], cwd=PROJECT_DIR, check=False, quiet=True)
  _write_gitignore()
  _run(["git", "add", "-A"], cwd=PROJECT_DIR)
  _run(["git", "commit", "-m", "tbh blue-chest farm macro"], cwd=PROJECT_DIR, check=False)
  _run(["git", "remote", "remove", "origin"], cwd=PROJECT_DIR, check=False, quiet=True)
  _run(["git", "remote", "add", "origin", REMOTE], cwd=PROJECT_DIR)
  print("Pushing code to main...")
  _run(["git", "push", "-u", "origin", "main", "--force"], cwd=PROJECT_DIR)

  # 2) build the gh-pages site in its own working copy
  print(f"Building site in {PUBLISH_DIR} ...")
  PUBLISH_DIR.mkdir(parents=True, exist_ok=True)
  if not (PUBLISH_DIR / ".git").exists():
    _run(["git", "init", "-b", "gh-pages"], cwd=PUBLISH_DIR)
    _run(["git", "remote", "add", "origin", REMOTE], cwd=PUBLISH_DIR)
  _run(["git", "config", "user.name", USER], cwd=PUBLISH_DIR, check=False, quiet=True)
  _write_site()
  _run(["git", "add", "-A"], cwd=PUBLISH_DIR)
  _run(["git", "commit", "-m", COMMIT_MSG], cwd=PUBLISH_DIR, check=False)
  print("Pushing site to gh-pages...")
  _run(["git", "push", "-u", "origin", "gh-pages", "--force"], cwd=PUBLISH_DIR)

  # 3) enable Pages
  _enable_pages()

  url = f"https://{USER}.github.io/{REPO}/"
  print("\n" + "=" * 60)
  print(f"  SITE: {url}")
  print(f"  PASSWORD: {PASSWORD}")
  print("  (first build ~1 min). Keep it live with:  python publish.py")
  print("=" * 60)


def _write_gitignore() -> None:
  # config.py holds SITE_PASSWORD + local paths -> keep it OUT of the public repo
  (PROJECT_DIR / ".gitignore").write_text(
    "__pycache__/\n*.pyc\n_*.png\nconfig.py\nsecret*.py\n"
    "macro_status.json\nmacro_chests.json\nmacro_drops.json\n",
    encoding="utf-8",
  )


def publish_once(initial: bool = False) -> None:
  if not (PUBLISH_DIR / ".git").exists():
    raise SystemExit("Site not set up. Run:  python publish.py --setup")
  _write_state()
  _run(["git", "add", "state.json"], cwd=PUBLISH_DIR, quiet=True)
  head = _run(["git", "log", "-1", "--pretty=%s"], cwd=PUBLISH_DIR, check=False, quiet=True).stdout.strip()
  if head == COMMIT_MSG and not initial:
    _run(["git", "commit", "--amend", "-m", COMMIT_MSG, "--no-edit"], cwd=PUBLISH_DIR, check=False, quiet=True)
  else:
    if not _run(["git", "status", "--porcelain"], cwd=PUBLISH_DIR, quiet=True).stdout.strip():
      return
    _run(["git", "commit", "-m", COMMIT_MSG], cwd=PUBLISH_DIR, check=False, quiet=True)
  _run(["git", "push", "--force-with-lease", "origin", "gh-pages"], cwd=PUBLISH_DIR, check=False, quiet=True)


def loop() -> None:
  print(f"Publishing (encrypted) every {INTERVAL}s -> {USER}.github.io/{REPO} (Ctrl+C)")
  while True:
    try:
      publish_once()
    except Exception as exc:
      print(f"  publish failed: {exc}")
    time.sleep(INTERVAL)


def start_in_background() -> None:
  import threading
  if not (PUBLISH_DIR / ".git").exists():
    print("Publish skipped: site not set up (run `python publish.py --setup`).")
    return
  threading.Thread(target=loop, daemon=True).start()


def rebuild_site() -> None:
  """Re-push the full site (index.html + sprites + state) after a design change."""
  if not (PUBLISH_DIR / ".git").exists():
    raise SystemExit("Site not set up. Run:  python publish.py --setup")
  _write_site()
  _run(["git", "add", "-A"], cwd=PUBLISH_DIR, quiet=True)
  _run(["git", "commit", "-m", COMMIT_MSG], cwd=PUBLISH_DIR, check=False, quiet=True)
  _run(["git", "push", "--force-with-lease", "origin", "gh-pages"], cwd=PUBLISH_DIR, check=False)
  print(f"Rebuilt + pushed site -> https://{USER}.github.io/{REPO}/")


if __name__ == "__main__":
  if "--setup" in sys.argv:
    setup()
  elif "--site" in sys.argv:
    rebuild_site()
  elif "--once" in sys.argv:
    publish_once()
    print("published one encrypted update")
  else:
    loop()
