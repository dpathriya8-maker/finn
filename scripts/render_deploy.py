"""Deploys the backend on Render through its API, waits until it is live, then checks /health.

    backend/.venv/Scripts/python scripts/render_deploy.py

Reads RENDER_API_KEY, RENDER_SERVICE_ID and RENDER_URL from .env (never printed, never logged). Neither Render nor Vercel deploys on
push, so this is how the backend is updated. It prints only the deploy's status and the commit it built.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.render.com/v1"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    env = read_env()
    key, service, url = env.get("RENDER_API_KEY"), env.get("RENDER_SERVICE_ID"), env.get("RENDER_URL")
    if not (key and service and url):
        print("RENDER_API_KEY, RENDER_SERVICE_ID and RENDER_URL must be in .env")
        return 2
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "Content-Type": "application/json"}
    started = requests.post(f"{API}/services/{service}/deploys", headers=headers, json={"clearCache": "do_not_clear"}, timeout=30)
    if started.status_code not in (200, 201, 202):
        print(f"Render refused the deploy: HTTP {started.status_code}")
        return 1
    deploy = started.json()
    deploy_id = deploy.get("id") or deploy.get("deploy", {}).get("id")
    print(f"Deploy {deploy_id} started")
    status = ""
    for _ in range(120):  # up to 20 minutes
        time.sleep(10)
        info = requests.get(f"{API}/services/{service}/deploys/{deploy_id}", headers=headers, timeout=30)
        if info.status_code != 200:
            continue
        body = info.json()
        if body.get("status") != status:
            status = body.get("status", "")
            commit = (body.get("commit") or {}).get("id", "")[:7]
            print(f"  {status}" + (f" (commit {commit})" if commit else ""))
        if status in ("live", "build_failed", "update_failed", "canceled", "pre_deploy_failed"):
            break
    if status != "live":
        print(f"The deploy did not go live: {status}")
        return 1
    for attempt in range(12):
        try:
            health = requests.get(url.rstrip("/") + "/health", timeout=30)
            print(f"/health: HTTP {health.status_code} {health.text[:120]}")
            if health.status_code == 200:
                return 0
        except requests.RequestException as exc:
            print(f"  waiting for the engine ({type(exc).__name__})")
        time.sleep(10)
    return 1


if __name__ == "__main__":
    sys.exit(main())
