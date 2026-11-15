"""Screenshots at phone width, light or dark, by driving Edge/Chrome over the DevTools protocol (no extra dependencies:
`websockets` and `requests` are already in backend/requirements.txt).

    backend/.venv/Scripts/python scripts/shoot.py URL OUT.png [--dark] [--width 390] [--wait 4] [--js "document.querySelector('button').click()"]

--js runs in the page after it has loaded and before the picture is taken (to open a sheet, say). The picture is the
whole page, not only what fits on the screen.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from websockets.sync.client import connect

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]


def find_browser() -> str:
    for path in BROWSERS:
        if Path(path).exists():
            return path
    found = shutil.which("chrome") or shutil.which("chromium") or shutil.which("msedge")
    if not found:
        sys.exit("No Edge or Chrome found.")
    return found


class Page:
    def __init__(self, ws_url: str):
        self.ws = connect(ws_url, max_size=None)
        self.n = 0

    def call(self, method: str, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") == self.n:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    def evaluate(self, expression: str):
        return self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True).get("result", {}).get("value")


def shoot(url: str, out: Path, *, dark: bool, width: int, height: int, wait: float, js: list[str], max_height: int = 0, reduced_motion: bool = False, port: int = 9333) -> None:
    profile = tempfile.mkdtemp(prefix="finn-shoot-")
    proc = subprocess.Popen(
        [find_browser(), "--headless=new", "--disable-gpu", f"--remote-debugging-port={port}", f"--user-data-dir={profile}", "--no-first-run", "--hide-scrollbars", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = None
        for _ in range(50):
            try:
                targets = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=2).json()
                ws_url = next(t["webSocketDebuggerUrl"] for t in targets if t.get("type") == "page")
                break
            except Exception:
                time.sleep(0.2)
        if not ws_url:
            sys.exit("Could not reach the browser's DevTools port.")
        page = Page(ws_url)
        page.call("Page.enable")
        page.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=2, mobile=True)
        page.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark" if dark else "light"}, {"name": "prefers-reduced-motion", "value": "reduce" if reduced_motion else "no-preference"}])
        page.call("Page.navigate", url=url)
        time.sleep(wait)
        for script in js:
            page.evaluate(script)
            time.sleep(0.8)
        full_height = int(page.evaluate("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)") or height)
        if full_height > height:  # a tall capture: the fixed bottom bar would be pasted into the middle of the picture
            page.evaluate("document.querySelectorAll('nav').forEach(n => { n.style.visibility = 'hidden' })")
        shown = max(full_height, height)
        if max_height:
            shown = min(shown, max_height)  # a long page (a company with many promises) is cut here
        shot = page.call("Page.captureScreenshot", format="png", captureBeyondViewport=True, clip={"x": 0, "y": 0, "width": width, "height": shown, "scale": 1})
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(base64.b64decode(shot["data"]))
        print(f"{out} ({width}px wide, {shown}px of {full_height}px, {'dark' if dark else 'light'})")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("out", type=Path)
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--width", type=int, default=390)
    parser.add_argument("--height", type=int, default=844)
    parser.add_argument("--wait", type=float, default=4.0)
    parser.add_argument("--reduced-motion", action="store_true", help="emulate prefers-reduced-motion (animations and smooth scrolling off)")
    parser.add_argument("--max-height", type=int, default=0, help="cut a long page at this many pixels")
    parser.add_argument("--js", action="append", default=[])
    args = parser.parse_args()
    shoot(args.url, args.out, dark=args.dark, width=args.width, height=args.height, wait=args.wait, js=args.js, max_height=args.max_height, reduced_motion=args.reduced_motion)


if __name__ == "__main__":
    main()
