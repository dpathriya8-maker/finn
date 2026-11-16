"""Checks a running FINN site (local or live) in a real phone-sized Chromium, over the DevTools protocol.

    backend/.venv/Scripts/python scripts/check_live.py https://finn-mocha.vercel.app
    backend/.venv/Scripts/python scripts/check_live.py http://localhost:3000 --only brief,alerts --shots docs/screens

For every screen (and every state a screen can be put in), at 360 and 390 px, in light and dark, it checks:
  * no uncaught error, console error or failed request;
  * the page does not scroll sideways (scrollWidth == clientWidth, and nothing sticks out past the screen);
  * every piece of text has a contrast ratio of at least 4.5:1 against what is behind it (3:1 for large text).
Scenarios may also assert on what is on the screen. Exit code 1 if anything fails. Needs Edge or Chrome; no extra dependencies.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
from websockets.sync.client import connect

sys.path.insert(0, str(Path(__file__).parent))
from shoot import find_browser  # noqa: E402

CONTRAST_JS = r"""
(() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  function rgba(color) {
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = color; cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255];
  }
  function over(top, below) { const a = top[3]; return [0, 1, 2].map(i => top[i] * a + below[i] * (1 - a)).concat([1]); }
  function lum(c) { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); }
  function ratio(a, b) { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
  function backdrop(el) {
    const chain = [];
    for (let n = el; n; n = n.parentElement) chain.push(n);
    let bg = rgba(getComputedStyle(document.documentElement).backgroundColor); if (bg[3] < 1) bg = [255, 255, 255, 1];
    for (const n of chain.reverse()) { const c = rgba(getComputedStyle(n).backgroundColor); if (c[3] > 0) bg = over(c, bg); }
    return bg;
  }
  const bad = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  for (let t = walker.nextNode(); t; t = walker.nextNode()) {
    if (!t.textContent.trim()) continue;
    const el = t.parentElement; if (!el || seen.has(el)) continue; seen.add(el);
    if (el.closest('[inert], [hidden], script, style, noscript')) continue;
    const r = el.getBoundingClientRect(); if (r.width === 0 || r.height === 0) continue;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (el.closest('.sr-only')) continue;
    let op = 1; for (let n = el; n; n = n.parentElement) op *= Number(getComputedStyle(n).opacity);
    if (op === 0) continue;
    let fg = rgba(cs.color); const bg = backdrop(el); fg = over([fg[0], fg[1], fg[2], fg[3] * op], bg);
    const size = parseFloat(cs.fontSize), bold = Number(cs.fontWeight) >= 700;
    const need = size >= 24 || (size >= 18.66 && bold) ? 3 : 4.5;
    const got = ratio(fg, bg);
    if (got < need) bad.push(`${got.toFixed(2)} < ${need}: "${t.textContent.trim().slice(0, 40)}" (${cs.color} on ${el.tagName.toLowerCase()})`);
  }
  return bad.slice(0, 8);
})()
"""

LAYOUT_JS = r"""
(() => {
  const de = document.documentElement, w = de.clientWidth, out = [];
  if (de.scrollWidth > w) out.push(`html scrollWidth ${de.scrollWidth} > ${w}`);
  if (document.body.scrollWidth > w) out.push(`body scrollWidth ${document.body.scrollWidth} > ${w}`);
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('[inert], .sr-only') || el.closest('[aria-hidden="true"] svg')) continue;
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && r.right > w + 1 && getComputedStyle(el).position !== 'fixed') {
      const clip = el.closest('[class*="overflow-x-auto"], [class*="overflow-hidden"], [class*="overflow-x-clip"], [class*="overflow-x-hidden"]');
      if (!clip || clip === el) { out.push(`${el.tagName.toLowerCase()}.${String(el.className).slice(0, 40)} right ${Math.round(r.right)} > ${w}`); if (out.length > 5) break; }
    }
  }
  const nav = document.querySelector('nav');
  if (nav) { const r = nav.getBoundingClientRect(); if (r.left < -1 || r.right > w + 1) out.push(`nav sticks out: ${Math.round(r.left)}..${Math.round(r.right)} of ${w}`); }
  return out;
})()
"""

SET_VALUE_JS = """
window.__setVal = (el, v) => {
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  set.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true }));
};
window.__byText = (sel, text) => [...document.querySelectorAll(sel)].find(e => e.textContent.trim().includes(text));
true
"""


class Tab:
    def __init__(self, ws_url: str):
        self.ws = connect(ws_url, max_size=None)
        self.n = 0
        self.errors: list[str] = []

    def call(self, method: str, **params):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            self.note(msg)
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def note(self, msg: dict) -> None:
        m, p = msg.get("method"), msg.get("params", {})
        if m == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails", {})
            self.errors.append("exception: " + str(d.get("exception", {}).get("description") or d.get("text"))[:200])
        elif m == "Runtime.consoleAPICalled" and p.get("type") == "error":
            self.errors.append("console.error: " + " ".join(str(a.get("value", a.get("description", ""))) for a in p.get("args", []))[:200])
        elif m == "Log.entryAdded" and p.get("entry", {}).get("level") == "error":
            e = p["entry"]
            self.errors.append(f"log error: {e.get('text', '')[:120]} {e.get('url', '')[:100]}")
        elif m == "Network.loadingFailed" and not p.get("canceled"):
            self.errors.append(f"request failed: {p.get('errorText')}")
        elif m == "Network.responseReceived" and p.get("response", {}).get("status", 0) >= 400:
            r = p["response"]
            self.errors.append(f"HTTP {r['status']}: {r['url'][:120]}")

    def drain(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            try:
                self.note(json.loads(self.ws.recv(timeout=0.2)))
            except TimeoutError:
                pass
            except Exception:
                break

    def js(self, expression: str):
        result = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in result:
            raise RuntimeError("js: " + str(result["exceptionDetails"].get("exception", {}).get("description", result["exceptionDetails"]))[:300])
        return result.get("result", {}).get("value")


class Browser:
    def __init__(self, port: int = 9444):
        self.profile = tempfile.mkdtemp(prefix="finn-check-")
        self.proc = subprocess.Popen(
            [find_browser(), "--headless=new", "--disable-gpu", f"--remote-debugging-port={port}", f"--user-data-dir={self.profile}", "--no-first-run", "--hide-scrollbars", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.port = port
        for _ in range(60):
            try:
                self.targets = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=2).json()
                self.ws_url = next(t["webSocketDebuggerUrl"] for t in self.targets if t.get("type") == "page")
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise SystemExit("Could not reach the browser's DevTools port.")

    def tab(self) -> Tab:
        tab = Tab(self.ws_url)
        for domain in ("Page", "Runtime", "Log", "Network"):
            tab.call(f"{domain}.enable")
        tab.call("Emulation.setFocusEmulationEnabled", enabled=True)  # so focus and blur events fire in a headless page
        return tab

    def close(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Run:
    base: str
    shots: Path | None
    ignore: str = ""
    results: list[Result] = field(default_factory=list)

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        self.results.append(Result(name, ok, detail))
        print(("  ok   " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def open_page(tab: Tab, url: str, *, width: int, dark: bool, wait: float, clear_storage: bool = True) -> None:
    tab.call("Emulation.setDeviceMetricsOverride", width=width, height=844, deviceScaleFactor=2, mobile=True)
    tab.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark" if dark else "light"}])
    tab.errors.clear()
    if clear_storage:
        tab.call("Page.navigate", url=url.split("?")[0].rsplit("/", 1)[0] + "/")  # same origin first, to clear its storage
        time.sleep(0.8)
        tab.js("try { localStorage.clear(); sessionStorage.clear(); } catch (e) {} true")
    tab.call("Page.navigate", url=url)
    time.sleep(wait)
    tab.js(SET_VALUE_JS)


def sweep(run: Run, tab: Tab, label: str, *, width: int, dark: bool, contrast: bool = True) -> None:
    tab.drain(0.3)
    errors = [e for e in tab.errors if not (run.ignore and re.search(run.ignore, e))]
    run.record(f"{label}: no console or network errors", not errors, "; ".join(errors[:3]))
    layout = tab.js(LAYOUT_JS)
    run.record(f"{label}: no sideways scroll", not layout, "; ".join(layout or []))
    if contrast:
        low = tab.js(CONTRAST_JS)
        run.record(f"{label}: text contrast", not low, "; ".join(low or []))


def shot(tab: Tab, path: Path, width: int, max_height: int = 2600) -> None:
    """A tall picture of the page as the reader sees it. The window is made as tall as the page for a moment (not captured "beyond
    the viewport", which makes the swipeable tabs snap back to the first one) and every sideways-scrolled box is put back."""
    height = int(tab.js("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)") or 844)
    shown = min(max(height, 844), max_height)
    tab.js("window.__scrolled = [...document.querySelectorAll('*')].filter(e => e.scrollLeft > 0).map(e => [e, e.scrollLeft]); true")
    if height > 844:
        tab.js("document.querySelectorAll('nav').forEach(n => { n.style.visibility = 'hidden' }); true")
    tab.call("Emulation.setDeviceMetricsOverride", width=width, height=shown, deviceScaleFactor=2, mobile=True)
    time.sleep(0.5)
    tab.js("window.__scrolled.forEach(([e, left]) => { e.scrollLeft = left }); true")
    time.sleep(0.3)
    data = tab.call("Page.captureScreenshot", format="png", clip={"x": 0, "y": 0, "width": width, "height": shown, "scale": 1})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(data["data"]))
    tab.call("Emulation.setDeviceMetricsOverride", width=width, height=844, deviceScaleFactor=2, mobile=True)
    tab.js("document.querySelectorAll('nav').forEach(n => { n.style.visibility = '' }); true")


EXPAND_ALL = """
(async () => {
  for (let round = 0; round < 4; round++) {
    const closed = [...document.querySelectorAll('article button[aria-expanded="false"], button[aria-expanded="false"][aria-controls]')].filter(b => !b.closest('[inert]') && !b.closest('nav'));
    if (!closed.length) break;
    closed.forEach(b => b.click());
    await new Promise(r => setTimeout(r, 300));
  }
  return document.querySelectorAll('button[aria-expanded="true"]').length;
})()
"""

# Each scenario: (key, path, steps run after load [JS strings], extra checks [(label, JS that returns true when fine)], screenshot name)
SCENARIOS: dict[str, dict] = {}


def scenario(key: str, path: str, *, steps: list[str] | None = None, expand: bool = False, checks: list[tuple[str, str]] | None = None,
             wait: float = 4.0, shot_name: str | None = None, contrast: bool = True, keep_storage: bool = False, setup: list[str] | None = None,
             init: list[str] | None = None) -> None:
    """`init` scripts run in the page before any of its own scripts (to fake the device clock, say); `setup` runs on the site's origin before the page is opened."""
    SCENARIOS[key] = dict(path=path, steps=steps or [], expand=expand, checks=checks or [], wait=wait, shot=shot_name, contrast=contrast, keep_storage=keep_storage, setup=setup or [], init=init or [])


def load_scenarios() -> None:
    import importlib

    importlib.import_module("live_scenarios").define(scenario)


def run_scenarios(base: str, only: set[str] | None, shots: Path | None, widths: list[int], themes: list[bool], ignore: str = "") -> Run:
    run = Run(base.rstrip("/"), shots, ignore)
    browser = Browser(port=int(os.environ.get("FINN_CHECK_PORT", "9444")))  # a different port lets two checks run side by side
    try:
        tab = browser.tab()
        for key, sc in SCENARIOS.items():
            if only and key not in only:
                continue
            for width in widths:
                for dark in themes:
                    label = f"{key} @{width} {'dark' if dark else 'light'}"
                    print(label)
                    init_ids: list[str] = []
                    try:
                        # Storage is set up on the site's own origin, before the page that reads it is opened.
                        open_page(tab, run.base + "/", width=width, dark=dark, wait=1.0, clear_storage=not sc["keep_storage"])
                        for js in sc["setup"]:
                            tab.js(js)
                        init_ids = [tab.call("Page.addScriptToEvaluateOnNewDocument", source=js)["identifier"] for js in sc["init"]]
                        tab.call("Page.navigate", url=run.base + sc["path"])
                        time.sleep(sc["wait"])
                        tab.js(SET_VALUE_JS)
                        for js in sc["steps"]:
                            tab.js(js)
                            time.sleep(0.7)
                        sweep(run, tab, label, width=width, dark=dark, contrast=sc["contrast"])
                        if sc["expand"]:
                            opened = tab.js(EXPAND_ALL)
                            time.sleep(0.5)
                            sweep(run, tab, label + " (all open)", width=width, dark=dark, contrast=sc["contrast"])
                        for check_label, js in sc["checks"]:
                            if width == widths[0] and not dark or "@all" in check_label:
                                try:
                                    run.record(f"{key}: {check_label.replace('@all', '').strip()}", bool(tab.js(js)))
                                except Exception as exc:
                                    run.record(f"{key}: {check_label}", False, str(exc))
                        if shots and sc["shot"] and width == 390:
                            shot(tab, shots / (sc["shot"] + ("-dark" if dark else "-light") + ".png"), width)
                    except Exception as exc:
                        run.record(label + ": ran", False, f"{type(exc).__name__}: {exc}")
                    finally:
                        for identifier in init_ids:
                            try:
                                tab.call("Page.removeScriptToEvaluateOnNewDocument", identifier=identifier)
                            except Exception:
                                pass
    finally:
        browser.close()
    return run


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # the rupee sign and arrows must not crash a Windows console
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("--only", default="", help="comma-separated scenario keys")
    parser.add_argument("--shots", type=Path, default=None, help="folder for 390 px screenshots")
    parser.add_argument("--widths", default="360,390")
    parser.add_argument("--light-only", action="store_true")
    parser.add_argument("--ignore", default="", help="regex of console or network errors to leave out (a local run has no backend on :8000)")
    args = parser.parse_args()
    load_scenarios()
    only = {k for k in args.only.split(",") if k} or None
    themes = [False] if args.light_only else [False, True]
    run = run_scenarios(args.base, only, args.shots, [int(w) for w in args.widths.split(",")], themes, args.ignore)
    failed = [r for r in run.results if not r.ok]
    print(f"\n{len(run.results) - len(failed)} of {len(run.results)} checks passed")
    for r in failed:
        print(f"FAILED: {r.name}  [{r.detail}]")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
