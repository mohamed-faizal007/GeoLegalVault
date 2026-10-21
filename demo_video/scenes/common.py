"""Shared harness for the GeoLegalVault demo scenes.

Each scene script calls `run_scene(name, title, fn)`. `fn(scene, browser)` opens one browser context per role
(a real, separate login). Videos land in demo_video/recordings/<scene>/<role>.webm and step timings in
recordings/<scene>/timeline.json. Secrets: the demo password is read from scripts/seed.py at runtime and never
printed; .env values are never printed.
"""
import json
import re
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
VID = ROOT / "demo_video"
REC = VID / "recordings"
STATE = VID / "state.json"
APP = "http://localhost:5173"
API = "http://localhost:8000/api/v1"
DATE = "20261021"
LOC_LABEL = "Browser location supplied by test harness - the server still validates it"
INSIDE = dict(latitude=11.67, longitude=78.15, accuracy=20)
OUTSIDE = dict(latitude=11.00, longitude=77.00, accuracy=20)
POOR = dict(latitude=11.67, longitude=78.15, accuracy=500)

EMAILS = {
    "staff": "authorized_staff@geolegalvault.demo",
    "reviewer": "reviewing_officer@geolegalvault.demo",
    "legal": "legal_officer@geolegalvault.demo",
    "admin": "administrator@geolegalvault.demo",
    "auditor": "auditor@geolegalvault.demo",
}


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


INIT_JS = r"""
(() => {
  const css = `
  #glv-cap{position:fixed;left:0;right:0;bottom:0;z-index:2147483647;background:rgba(8,12,24,.94);color:#fff;
    font:600 22px/1.3 Segoe UI,Arial,sans-serif;padding:10px 24px;border-top:3px solid #3b82f6;pointer-events:none}
  #glv-cap small{display:block;font:500 15px/1.3 Segoe UI,Arial;color:#9fb3d9;margin-top:2px}
  #glv-cap .sc{color:#7db3ff}
  #glv-cur{position:fixed;width:34px;height:34px;border:3px solid #ffd33d;border-radius:50%;background:rgba(255,211,61,.22);
    z-index:2147483646;pointer-events:none;transform:translate(-50%,-50%);left:-100px;top:-100px}
  html{zoom:1.12} body{padding-bottom:84px}`;
  window.__glv = JSON.parse(sessionStorage.getItem('__glv') || '{"scene":"","step":"","note":""}');
  window.__glvRender = () => { const c = document.getElementById('glv-cap'); if (!c) return;
    c.innerHTML = '<span class="sc">' + window.__glv.scene + '</span> &nbsp;|&nbsp; ' + window.__glv.step +
      (window.__glv.note ? '<small>' + window.__glv.note + '</small>' : ''); };
  window.__glvSet = (s) => { Object.assign(window.__glv, s);
    try { sessionStorage.setItem('__glv', JSON.stringify(window.__glv)); } catch (e) {} window.__glvRender(); };
  const mk = () => {
    if (document.getElementById('glv-cap')) return;
    const st = document.createElement('style'); st.textContent = css; document.documentElement.appendChild(st);
    const c = document.createElement('div'); c.id = 'glv-cap'; document.documentElement.appendChild(c);
    const k = document.createElement('div'); k.id = 'glv-cur'; document.documentElement.appendChild(k);
    window.__glvRender();
    document.addEventListener('mousemove', e => { k.style.left = e.clientX + 'px'; k.style.top = e.clientY + 'px'; }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mk); else mk();
})();
"""


class Scene:
    def __init__(self, name: str, title: str):
        self.name, self.title = name, title
        self.dir = REC / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.t0 = time.time()
        self.timeline: list[dict] = []
        self.pages: dict = {}
        self.ctxs: dict = {}

    def context(self, browser, role: str, geo: dict | None = INSIDE):
        opts = dict(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(self.dir / f"_{role}"),
            record_video_size={"width": 1920, "height": 1080},
        )
        if geo:
            opts.update(geolocation=geo, permissions=["geolocation"])
        ctx = browser.new_context(**opts)
        ctx.add_init_script(INIT_JS)
        ctx.set_default_timeout(30000)
        page = ctx.new_page()
        self.ctxs[role], self.pages[role] = ctx, page
        self.caps = getattr(self, "caps", {})
        page.on("domcontentloaded", lambda _p=page, r=role: self._reapply(_p, r))
        return page

    def _reapply(self, page, role):
        cap = self.caps.get(role)
        if cap:
            try:
                page.evaluate("s => window.__glvSet && window.__glvSet(s)", cap)
            except Exception:
                pass

    def say(self, page, step: str, note: str = "", geo: bool = False):
        note = (note + (" | " if note and geo else "") + (LOC_LABEL if geo else "")).strip()
        cap = {"scene": self.title, "step": step, "note": note}
        for r, p in self.pages.items():
            if p is page:
                self.caps[r] = cap
        try:
            page.evaluate("s => window.__glvSet && window.__glvSet(s)", cap)
        except Exception:
            pass
        self.timeline.append({"t": round(time.time() - self.t0, 1), "step": step})
        print(f"[{self.name}] {step}", flush=True)

    def login(self, page, role: str, password: str | None = None, email: str | None = None, expect_ok: bool = True):
        page.goto(f"{APP}/login")
        page.fill("#email", email or EMAILS[role])
        page.fill("#password", password or demo_password())
        page.click("button[type=submit]")
        if expect_ok:
            page.wait_for_url(lambda u: "/login" not in u, timeout=20000)
            page.wait_for_timeout(1500)

    def finish(self):
        for role, ctx in self.ctxs.items():
            try:
                ctx.close()
            except Exception:
                pass
        for role in self.ctxs:
            d = self.dir / f"_{role}"
            vids = sorted(d.glob("*.webm"))
            if vids:
                vids[-1].replace(self.dir / f"{role}.webm")
            for v in d.glob("*"):
                v.unlink()
            if d.exists():
                d.rmdir()
        (self.dir / "timeline.json").write_text(json.dumps(self.timeline, indent=1))


def run_scene(name: str, title: str, fn, slow_mo: int = 400):
    sc = Scene(name, title)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=slow_mo, args=["--window-size=1920,1080"])
        try:
            fn(sc, browser)
        finally:
            sc.finish()
            browser.close()
    print(f"[{name}] done in {time.time() - sc.t0:.0f}s")


def api(method: str, path: str, token: str | None = None, body=None, headers=None):
    """Raw API call for supplementary views. Returns (status, parsed_json_or_text)."""
    h = {"Content-Type": "application/json", **(headers or {})}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, headers=h,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def db():
    from pymongo import MongoClient
    return MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=4000)["geolegalvault"]


def show_text(page, title: str, text: str):
    """Render a clearly-labelled 'Supplementary view' page (real output; the caller has removed secrets)."""
    esc = text.replace("&", "&amp;").replace("<", "&lt;")
    page.set_content(
        '<html><body style="margin:0;background:#0b1020;color:#e6edf7;font-family:Consolas,monospace">'
        '<div style="background:#b45309;color:#fff;font:700 22px Segoe UI;padding:12px 24px">'
        "SUPPLEMENTARY VIEW - real read-only output, secrets removed. This is NOT the application UI.</div>"
        f'<h2 style="font:600 26px Segoe UI;margin:16px 24px 6px">{title.replace("&", "&amp;").replace("<", "&lt;")}</h2>'
        f'<pre style="font-size:16px;line-height:1.3;margin:0 24px;white-space:pre-wrap">{esc}</pre></body></html>'
    )
