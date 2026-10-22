"""Shared harness for the GeoLegalVault demo_video2 scenes.

Each scene script calls `run_scene(name, title, sid, fn)`. `fn(scene, browser)` opens one browser context per role
(a real, separate login). Videos land in demo_video2/recordings/<scene>/<role>.webm.

Sync model: the narration is one WAV per sentence (audio/<sid>_<key>.wav). A scene wraps each sentence's on-screen
step in `with sc.beat(page, key, caption):`. The beat is held on screen at least as long as its sentence takes to
speak. The start and end of every beat (and of any long wait to be trimmed) are stamped INTO THE VIDEO as a tiny
binary marker in the bottom-right corner, plus listed in timeline.json. assemble.py decodes the marker from the frames
(so it does not depend on wall-clock vs video-clock agreement), cuts each beat, places each sentence's audio at its
beat's start, and blanks the marker out of the final picture.

Safety: everything here points at the DEMO database `geolegalvault_demo`; `guard_db()` aborts if MONGODB_DB is set to
anything else. The dev database `geolegalvault` is never opened. The demo password is read from scripts/seed.py at
runtime and never printed; .env values are never printed.
"""
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
import wave
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
VID = ROOT / "demo_video2"
REC = VID / "recordings"
AUD = VID / "audio"
WORK = VID / "work"
STATE = VID / "state.json"
APP = "http://localhost:5174"
API = "http://localhost:8001/api/v1"
DEMO_DB = "geolegalvault_demo"
DEV_DB = "geolegalvault"
DATE = "20261022"
TITLE = f"DEMO-{DATE}-Lease"
LOC_LABEL = "Browser location supplied by test harness - the server still validates it"
INSIDE = dict(latitude=11.67, longitude=78.15, accuracy=20)
OUTSIDE = dict(latitude=11.00, longitude=77.00, accuracy=20)
POOR = dict(latitude=11.67, longitude=78.15, accuracy=500)
LEAD, GAP = 0.25, 0.45  # seconds of picture before the voice starts / after it ends

EMAILS = {
    "staff": "authorized_staff@geolegalvault.demo",
    "reviewer": "reviewing_officer@geolegalvault.demo",
    "legal": "legal_officer@geolegalvault.demo",
    "admin": "administrator@geolegalvault.demo",
    "auditor": "auditor@geolegalvault.demo",
}


def guard_db() -> None:
    """Abort unless every helper is pointed at the demo database."""
    cur = os.environ.get("MONGODB_DB")
    if cur not in (None, DEMO_DB):
        sys.exit(f"REFUSED: MONGODB_DB={cur!r}; the demo may only use {DEMO_DB!r}.")
    os.environ["MONGODB_DB"] = DEMO_DB
    assert DEMO_DB != DEV_DB and DEMO_DB == "geolegalvault_demo"


guard_db()


def demo_password() -> str:
    src = (ROOT / "scripts" / "seed.py").read_text(encoding="utf-8")
    return re.search(r'DEMO_PASSWORD\s*=\s*"([^"]+)"', src).group(1)


def env(name: str) -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return re.sub(r"\s+#.*$", "", line.split("=", 1)[1].strip()).strip().strip("\"'")
    return ""


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(**kw) -> dict:
    s = load_state()
    s.update(kw)
    STATE.write_text(json.dumps(s, indent=2))
    return s


def new_password() -> str:
    return "Dm!" + secrets.token_urlsafe(12)


def wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / float(w.getframerate())


def db():
    guard_db()
    from pymongo import MongoClient
    return MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=4000)[DEMO_DB]


INIT_JS = r"""
(() => {
  if (window.__glvInit) return; window.__glvInit = true;
  let saved = {};
  try { saved = JSON.parse(sessionStorage.getItem('__glv') || '{}'); } catch (e) {}
  window.__glv = Object.assign({scene: '', step: '', note: '', seq: 0, zoom: 1.12}, saved);
  window.open = function (u) { window.__opened = u; return null; };   // a pre-signed URL is captured, never shown
  // All styling goes through the CSSOM (element.style), so it also works on pages with a strict CSP.
  const css = (el, o) => { for (const k in o) el.style.setProperty(k, o[k], 'important'); return el; };
  let cap = null, mk = null, cur = null, timer = null;
  const save = () => { try { sessionStorage.setItem('__glv', JSON.stringify(window.__glv)); } catch (e) {} };
  const render = () => {
    if (!cap) return;
    const g = window.__glv;
    cap.textContent = '';
    const sc = css(document.createElement('span'), {color: '#7db3ff'}); sc.textContent = g.scene;
    cap.appendChild(sc); cap.appendChild(document.createTextNode('  |  ' + g.step));
    if (g.note) {
      const n = css(document.createElement('div'), {font: '500 15px/1.3 Segoe UI,Arial,sans-serif', color: '#9fb3d9', 'margin-top': '2px'});
      n.textContent = g.note; cap.appendChild(n);
    }
    // Sync marker (blanked out again by assemble.py): white sync square, 12 data bits, black sync square.
    const z = parseFloat(document.documentElement.style.zoom) || 1;
    css(mk, {zoom: String(1 / z)});
    const bits = [1].concat([...Array(12)].map((_, i) => (g.seq >> (11 - i)) & 1)).concat([0]);
    bits.forEach((b, i) => css(mk.children[i], {background: b ? '#fff' : '#000'}));
  };
  const build = () => {
    const root = document.documentElement;
    if (!root) return;
    root.style.zoom = String(window.__glvFixedZoom || window.__glv.zoom);
    root.style.setProperty('overflow-x', 'hidden', 'important');   // no horizontal scrollbar: the sync marker must sit at the bottom edge
    if (document.body) document.body.style.setProperty('padding-bottom', '84px', 'important');
    if (!document.getElementById('glv-cap')) {
      cap = css(document.createElement('div'), {position: 'fixed', left: '0', right: '0', bottom: '0', 'z-index': '2147483647',
        background: 'rgba(8,12,24,.94)', color: '#fff', font: '600 22px/1.3 Segoe UI,Arial,sans-serif',
        padding: '10px 24px 12px', 'border-top': '3px solid #3b82f6', 'pointer-events': 'none'});
      cap.id = 'glv-cap';
      mk = css(document.createElement('div'), {position: 'fixed', left: '1600px', bottom: '0', width: '224px', height: '16px',
        display: 'flex', 'z-index': '2147483647', 'pointer-events': 'none'});
      mk.id = 'glv-mk';
      for (let i = 0; i < 14; i++) mk.appendChild(css(document.createElement('div'), {width: '16px', height: '16px', background: '#000'}));
      cur = css(document.createElement('div'), {position: 'fixed', width: '20px', height: '20px', border: '2px solid #ffd33d',
        'border-radius': '50%', background: 'rgba(255,211,61,.15)', 'z-index': '2147483646', 'pointer-events': 'none',
        transform: 'translate(-50%,-50%)', left: '-100px', top: '-100px', opacity: '0', transition: 'opacity .2s'});
      cur.id = 'glv-cur';
      const ov = css(document.createElement('div'), {position: 'fixed', left: '0', top: '0', right: '0', bottom: '0', 'z-index': '2147483000',
        background: 'rgba(0,0,0,.45)', 'pointer-events': 'none', display: 'none'});
      ov.id = 'glv-ov';
      [ov, cap, mk, cur].forEach(e => root.appendChild(e));
    } else { cap = document.getElementById('glv-cap'); mk = document.getElementById('glv-mk'); }
    render();
  };
  window.__glvBuild = build;
  window.__glvSet = (s) => { Object.assign(window.__glv, s); save(); build(); };
  window.__glvZoom = (z) => { window.__glvFixedZoom = z; build(); };   // per page; resets on navigation
  window.__glvDim = (on) => { build(); const o = document.getElementById('glv-ov'); if (o) o.style.setProperty('display', on ? 'block' : 'none', 'important'); };
  document.addEventListener('mousemove', e => {
    const k = document.getElementById('glv-cur'); if (!k) return;
    const z = parseFloat(document.documentElement.style.zoom) || 1;
    k.style.setProperty('left', (e.clientX / z) + 'px', 'important'); k.style.setProperty('top', (e.clientY / z) + 'px', 'important');
    const over = e.target && e.target.closest && e.target.closest('button,a,select,input,textarea,label,[role=button]');
    k.style.setProperty('opacity', over ? '0' : '1', 'important');   // never sits on a button label
    clearTimeout(timer); timer = setTimeout(() => k.style.setProperty('opacity', '0', 'important'), 600);   // short dwell
  }, true);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
"""


class Scene:
    def __init__(self, name: str, title: str, sid: str):
        self.name, self.title, self.sid = name, title, sid
        self.dir = REC / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.t0 = time.time()
        self.beats: list[dict] = []
        self.pages: dict = {}
        self.ctxs: dict = {}
        self.caps: dict = {}
        self.seq = 0
        self.geos: dict = {}
        self._cur: dict | None = None
        self._curpage = None

    # -- browser contexts -------------------------------------------------------------------------
    def context(self, browser, role: str, geo: dict | None = INSIDE):
        opts = dict(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(self.dir / f"_{role}"),
            record_video_size={"width": 1920, "height": 1080},
        )
        if geo:
            opts.update(geolocation=geo, permissions=["geolocation", "clipboard-read", "clipboard-write"])
        ctx = browser.new_context(**opts)
        ctx.add_init_script(INIT_JS)
        ctx.set_default_timeout(30000)
        page = ctx.new_page()
        self.ctxs[role], self.pages[role] = ctx, page
        self.geos[role] = geo
        page.on("domcontentloaded", lambda _p=page, r=role: self._reapply(_p, r))
        return page

    def role_of(self, page) -> str:
        return next(r for r, p in self.pages.items() if p is page)

    def _push(self, page, **cap):
        role = self.role_of(page)
        self.caps.setdefault(role, dict(scene=self.title, step="", note="", seq=0)).update(cap)
        try:
            page.evaluate("s => window.__glvSet && window.__glvSet(s)", self.caps[role])
        except Exception:
            pass

    def _reapply(self, page, role):
        cap = self.caps.get(role)
        if cap:
            try:
                page.evaluate("s => window.__glvSet && window.__glvSet(s)", cap)
            except Exception:
                pass

    def say(self, page, step: str, note: str = "", geo: bool = False, mark: bool = False) -> int:
        note = (note + (" | " if note and geo else "") + (LOC_LABEL if geo else "")).strip()
        if mark:
            self.seq += 1
        self._push(page, scene=self.title, step=step, note=note, **({"seq": self.seq} if mark else {}))
        return self.seq

    def mark(self, page) -> int:
        """Stamp the next sync number into the page (and so into the recorded video)."""
        self.seq += 1
        self._push(page, seq=self.seq)
        page.wait_for_timeout(300)   # evaluate() is not slowed by slow_mo: keep the marker on screen for a few frames
        return self.seq

    def set_geo(self, role: str, loc: dict):
        """Change the browser's reported location (and remember it for refresh_geo)."""
        self.geos[role] = loc
        self.ctxs[role].set_geolocation(loc)

    def refresh_geo(self, role: str):
        """Re-issue the current location so its reading is fresh: the server refuses readings older than
        GEO_FRESHNESS_MAX_SEC (LOCATION_STALE), and a context that sat idle while other roles worked would be stale."""
        if self.geos.get(role):
            self.ctxs[role].set_geolocation(self.geos[role])

    def zoom(self, page, z: float):
        page.evaluate("z => window.__glvZoom(z)", z)

    def dim(self, page, on: bool = True):
        page.evaluate("on => window.__glvDim(on)", on)

    def login(self, page, role: str, password: str | None = None, email: str | None = None, expect_ok: bool = True):
        page.goto(f"{APP}/login")
        page.fill("#email", email or EMAILS[role])
        page.fill("#password", password or demo_password())
        page.click("button[type=submit]")
        if expect_ok:
            page.wait_for_url(lambda u: "/login" not in u, timeout=20000)
            page.wait_for_timeout(1200)

    # -- narration-synchronised beats -------------------------------------------------------------
    @contextmanager
    def beat(self, page, key: str, step: str = "", note: str = "", geo: bool = False):
        """One spoken sentence. Holds the picture until the sentence has been spoken (plus a small gap). The beat's
        start and end (and any trimmed wait) are stamped into the video as sync markers."""
        dur = wav_seconds(AUD / f"{self.sid}_{key}.wav")
        if geo:
            self.refresh_geo(self.role_of(page))
        seq0 = self.say(page, step, note, geo, mark=True)
        b = dict(key=key, sid=self.sid, scene=self.name, role=self.role_of(page), seq0=seq0, waits=[], dur=dur, step=step,
                 t0=time.time())
        self._cur, self._curpage = b, page
        print(f"[{self.name}] {key}: {step}", flush=True)
        yield b
        left = b["t0"] + LEAD + dur + GAP - time.time()
        if left > 0:
            page.wait_for_timeout(int(left * 1000))
        b["seq1"] = self.mark(page)
        self.beats.append(b)
        self._cur = self._curpage = None

    def hold_audio(self, page):
        """Inside a beat: keep the picture until the sentence has been spoken, so a long wait can follow it."""
        b = self._cur
        left = b["t0"] + LEAD + b["dur"] + GAP - time.time()
        if left > 0:
            page.wait_for_timeout(int(left * 1000))

    @contextmanager
    def trimmed(self):
        """A long wait (a block confirmation, a page load). assemble.py keeps only its first moments."""
        s0 = self.mark(self._curpage)
        yield
        s1 = self.mark(self._curpage)
        self._cur["waits"].append([s0, s1])

    def slide(self, key: str, slide: str):
        """A narrated slide beat: no browser involved; assemble.py renders the slide for the sentence's length."""
        self.beats.append(dict(key=key, sid=self.sid, scene=self.name, role=None, slide=slide, waits=[], t0=time.time(),
                               dur=wav_seconds(AUD / f"{self.sid}_{key}.wav"), step=""))

    def close_role(self, role: str):
        """Close one role's context as soon as its last beat is done (its video is finalised then)."""
        ctx = self.ctxs.pop(role, None)
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass

    def finish(self):
        roles = list(self.pages)
        for role in list(self.ctxs):
            self.close_role(role)
        for role in roles:
            d = self.dir / f"_{role}"
            vids = sorted(d.glob("*.webm"))
            if vids:
                vids[-1].replace(self.dir / f"{role}.webm")
            for v in d.glob("*"):
                v.unlink()
            if d.exists():
                d.rmdir()
        (self.dir / "timeline.json").write_text(json.dumps(dict(sid=self.sid, beats=self.beats), indent=1))


def run_scene(name: str, title: str, sid: str, fn, slow_mo: int = 400, headed: bool = True):
    guard_db()
    sc = Scene(name, title, sid)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed, slow_mo=slow_mo, args=["--window-size=1920,1080"])
        try:
            fn(sc, browser)
        finally:
            sc.finish()
            browser.close()
    print(f"[{name}] done in {time.time() - sc.t0:.0f}s, {len(sc.beats)} beats")


def api(method: str, path: str, token: str | None = None, body=None, headers=None):
    """Raw API call for supplementary views. Returns (status, parsed_json_or_text)."""
    h = {"Content-Type": "application/json", **(headers or {})}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, headers=h,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def wallet_balance() -> str:
    """Service wallet balance in ETH (address and balance only; the helper never prints a key or URL)."""
    import subprocess
    py = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
    out = subprocess.run([str(py), str(VID / "wallet_balance.py")], capture_output=True, text=True, cwd=str(ROOT),
                         env={**os.environ, "PYTHONPATH": str(ROOT / "backend")}).stdout
    m = re.search(r"balance_eth=(\S+)", out)
    return m.group(1) if m else "unknown"


def token_for(email: str, password: str) -> str:
    s, body = api("POST", "/auth/login", body={"email": email, "password": password})
    assert s == 200, f"login failed: HTTP {s}"
    return body["access_token"]


def geo_headers(loc: dict = INSIDE) -> dict:
    return {"X-Geo-Lat": str(loc["latitude"]), "X-Geo-Lng": str(loc["longitude"]),
            "X-Geo-Accuracy": str(loc["accuracy"]), "X-Geo-Timestamp": str(time.time())}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def show_supp(page, title: str, lines: list[str], highlight: list[str] | None = None, note: str = "",
              font: int = 28) -> None:
    """A clearly labelled 'Supplementary view' (real read-only output, secrets removed). `highlight` substrings are
    marked. Lines should be cropped by the caller to the relevant ones (about 20 lines fit at this size)."""
    body = "\n".join(esc(l) for l in lines)
    for h in highlight or []:
        eh = esc(h)
        body = body.replace(eh, f"<mark>{eh}</mark>")
    html = (
        "<html><head><style>body{margin:0;background:#0b1020;color:#e6edf7;font-family:Consolas,monospace}"
        "mark{background:#facc15;color:#111;padding:0 4px;border-radius:4px;font-weight:700}</style></head><body>"
        '<div style="background:#b45309;color:#fff;font:700 26px Segoe UI;padding:12px 24px">'
        "SUPPLEMENTARY VIEW &mdash; real read-only output, secrets removed. This is NOT the application UI.</div>"
        f'<h2 style="font:600 30px Segoe UI;margin:16px 24px 8px">{esc(title)}</h2>'
        f'<pre style="font-size:{font}px;line-height:1.38;margin:0 24px;white-space:pre-wrap">{body}</pre>'
        + (f'<p style="font:500 24px Segoe UI;color:#cfe0ff;margin:14px 24px">{esc(note)}</p>' if note else "")
        + "</body></html>"
    )
    page.set_content(html)
    page.evaluate("() => { window.__glvFixedZoom = 1; window.__glvBuild(); }")   # caption bar + sync marker on the new document


def storage_client():
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3", endpoint_url=env("STORAGE_ENDPOINT") or "http://localhost:9000",
        aws_access_key_id=env("STORAGE_ACCESS_KEY"), aws_secret_access_key=env("STORAGE_SECRET_KEY"),
        region_name="us-east-1", config=Config(s3={"addressing_style": "path"}))


def bucket() -> str:
    return env("STORAGE_BUCKET")


def j(o) -> str:
    return json.dumps(o, indent=2, default=str)
