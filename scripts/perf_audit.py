"""A mobile performance and accessibility audit of a running FINN page, over the DevTools protocol. No downloads, no extra packages.

    backend/.venv/Scripts/python scripts/perf_audit.py https://finn-mocha.vercel.app brief research --runs 3

(Pages are given by name, not as /paths, because Git Bash rewrites a lone / into a Windows path: brief is /, research is /research.)

THESE ARE NOT LIGHTHOUSE SCORES. Lighthouse was not run (it is a separate package to download). This measures the same things a user
feels on a real page load, in a real Chromium, with a slow-4G network (1.6 Mbps, 150 ms) and a CPU 4x slower than this machine, which are
the settings Lighthouse's mobile run simulates:
  FCP  first contentful paint            good at 1.8 s or less
  LCP  largest contentful paint          good at 2.5 s or less
  CLS  cumulative layout shift           good at 0.1 or less
  TBT  total blocking time (long tasks)  good at 200 ms or less
and, in the page: language, title, description, viewport, headings in order, every button, link and field has a name, images have alt text,
links go somewhere, `target=_blank` links are `noopener`, text is at least 12 px, tap targets are at least 44 px (24 px is Lighthouse's
limit), and nothing sideways scrolls. The median of several loads is reported.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_live import Browser  # noqa: E402

OBSERVERS = """
window.__m = { fcp: null, lcp: null, lcpEl: '', cls: 0, tasks: [], shifts: [] };
new PerformanceObserver(l => { for (const e of l.getEntries()) if (e.name === 'first-contentful-paint') window.__m.fcp = e.startTime; }).observe({ type: 'paint', buffered: true });
new PerformanceObserver(l => { for (const e of l.getEntries()) { window.__m.lcp = e.startTime; window.__m.lcpEl = (e.element ? e.element.tagName.toLowerCase() + ': ' + (e.element.textContent || e.element.src || '').trim().slice(0, 50) : ''); } }).observe({ type: 'largest-contentful-paint', buffered: true });
new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) { window.__m.cls += e.value; window.__m.shifts.push([Math.round(e.startTime), Math.round(e.value * 1000) / 1000, (e.sources || []).map(x => x.node ? ((x.node.tagName || x.node.parentElement?.tagName || '') + ' ' + (x.node.className || x.node.textContent || '').toString().trim().slice(0, 40)) : '?').join(' | ')]); } }).observe({ type: 'layout-shift', buffered: true });
new PerformanceObserver(l => { for (const e of l.getEntries()) window.__m.tasks.push([e.startTime, e.duration]); }).observe({ type: 'longtask', buffered: true });
"""

PAGE_AUDIT = r"""
(() => {
  const out = { fails: [], notes: [] };
  const fail = (m) => out.fails.push(m);
  const html = document.documentElement;
  if (!html.lang) fail('html has no lang');
  if (!document.title.trim()) fail('no <title>');
  if (!document.querySelector('meta[name=description]')?.content) fail('no meta description');
  const vp = document.querySelector('meta[name=viewport]')?.content || '';
  if (!vp) fail('no viewport meta'); else if (/user-scalable\s*=\s*(no|0)/.test(vp) || /maximum-scale\s*=\s*[01](\.|,|$)/.test(vp)) fail('zooming is disabled: ' + vp);
  if (document.querySelector('meta[name=robots][content*=noindex]')) out.notes.push('robots: noindex');
  if (!document.querySelector('main')) fail('no <main> landmark');
  const nameOf = (el) => (el.getAttribute('aria-label') || (el.getAttribute('aria-labelledby') ? [...el.getAttribute('aria-labelledby').split(' ')].map(i => document.getElementById(i)?.textContent || '').join(' ') : '') || el.textContent || el.getAttribute('title') || el.querySelector('img[alt]')?.alt || el.querySelector('svg[aria-label]')?.getAttribute('aria-label') || '').trim();
  let buttons = 0, links = 0, fields = 0, imgs = 0, tiny = 0, bigEnough = 0, targets = 0;
  for (const el of document.querySelectorAll('button, [role=button], [role=switch], [role=tab], [role=radio]')) { if (el.closest('[inert], .sr-only')) continue; buttons++; if (!nameOf(el)) fail('button without a name: ' + el.outerHTML.slice(0, 80)); }
  for (const el of document.querySelectorAll('a')) { if (el.closest('[inert]')) continue; links++; if (!el.getAttribute('href') || /^javascript:/i.test(el.getAttribute('href'))) fail('link that goes nowhere: ' + el.outerHTML.slice(0, 80)); else if (!nameOf(el)) fail('link without a name: ' + el.outerHTML.slice(0, 80)); if (el.target === '_blank' && !/noopener/.test(el.rel)) fail('target=_blank without noopener: ' + el.href); }
  for (const el of document.querySelectorAll('input:not([type=hidden]), select, textarea')) { if (el.closest('[inert]')) continue; fields++; const labelled = el.labels?.length || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby'); if (!labelled) fail('field without a label: ' + el.outerHTML.slice(0, 80)); }
  for (const el of document.querySelectorAll('img')) { imgs++; if (!el.hasAttribute('alt')) fail('image without alt: ' + el.src.slice(0, 80)); }
  for (const el of document.querySelectorAll('svg[role=img]')) { if (!el.getAttribute('aria-label') && !el.querySelector('title')) fail('svg role=img without a name'); }
  const ids = new Map(); for (const el of document.querySelectorAll('[id]')) ids.set(el.id, (ids.get(el.id) || 0) + 1);
  for (const [id, n] of ids) if (n > 1) fail('duplicate id: ' + id);
  for (const el of document.querySelectorAll('[aria-labelledby]')) for (const id of el.getAttribute('aria-labelledby').split(' ')) if (!document.getElementById(id)) fail('aria-labelledby points to nothing: ' + id);
  for (const el of document.querySelectorAll('[aria-controls]')) { if (el.getAttribute('aria-expanded') === 'true') for (const id of el.getAttribute('aria-controls').split(' ')) if (!document.getElementById(id)) fail('open control points to nothing: ' + id); }
  let last = 0; for (const h of document.querySelectorAll('h1,h2,h3,h4,h5,h6')) { if (h.closest('[inert]')) continue; const n = Number(h.tagName[1]); if (last && n > last + 1) fail(`heading jumps from h${last} to h${n}: ${h.textContent.trim().slice(0, 40)}`); last = n; }
  if (document.querySelectorAll('h1').length !== 1) fail('there should be exactly one h1 (found ' + document.querySelectorAll('h1').length + ')');
  if (document.querySelector('[tabindex]:not([tabindex="0"]):not([tabindex="-1"])')) fail('a positive tabindex');
  // text size: share of characters at 12 px or more
  let chars = 0, small = 0; const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t = walker.nextNode(); t; t = walker.nextNode()) { const s = t.textContent.trim(); if (!s) continue; const el = t.parentElement; if (el.closest('[inert], .sr-only, script, style')) continue; const r = el.getBoundingClientRect(); if (!r.width) continue; chars += s.length; if (parseFloat(getComputedStyle(el).fontSize) < 12) small += s.length; }
  out.textAtLeast12px = chars ? Math.round(1000 * (chars - small) / chars) / 10 : 100;
  if (out.textAtLeast12px < 60) fail('less than 60% of the text is 12 px or larger');
  // tap targets
  for (const el of document.querySelectorAll('button, a[href], input, select, textarea, [role=button], [role=switch], [role=tab], [role=radio]')) { if (el.closest('[inert], .sr-only')) continue; const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue; targets++; if (r.width >= 44 && r.height >= 44) bigEnough++; else if (r.width < 24 || r.height < 24) { tiny++; out.notes.push('small target ' + Math.round(r.width) + 'x' + Math.round(r.height) + ': ' + el.outerHTML.slice(0, 90)); } }
  out.tapTargets = { total: targets, atLeast44: bigEnough, under24: tiny };
  if (tiny) fail(tiny + ' tap targets are smaller than 24 px');
  out.counts = { buttons, links, fields, imgs };
  out.sidewaysScroll = html.scrollWidth > html.clientWidth;
  if (out.sidewaysScroll) fail('the page scrolls sideways');
  return out;
})()
"""


def one_load(tab, url: str, wait: float) -> dict:
    tab.errors.clear()
    tab.call("Network.setCacheDisabled", cacheDisabled=True)
    tab.call("Network.emulateNetworkConditions", offline=False, latency=150, downloadThroughput=int(1.6 * 1024 * 1024 / 8), uploadThroughput=int(750 * 1024 / 8))
    tab.call("Emulation.setCPUThrottlingRate", rate=4)
    sizes: dict[str, int] = {}
    urls: dict[str, str] = {}
    start = time.time()
    tab.call("Page.navigate", url=url)
    while time.time() - start < wait:
        try:
            msg = json.loads(tab.ws.recv(timeout=0.3))
        except TimeoutError:
            continue
        tab.note(msg)
        p = msg.get("params", {})
        if msg.get("method") == "Network.requestWillBeSent":
            urls[p["requestId"]] = p["request"]["url"]
        elif msg.get("method") == "Network.loadingFinished":
            sizes[p["requestId"]] = int(p.get("encodedDataLength", 0))
    m = json.loads(tab.js("JSON.stringify(window.__m)"))
    fcp = m["fcp"] or 0
    tbt = sum(max(0, d - 50) for s, d in m["tasks"] if s >= fcp)
    tab.call("Emulation.setCPUThrottlingRate", rate=1)
    tab.call("Network.emulateNetworkConditions", offline=False, latency=0, downloadThroughput=-1, uploadThroughput=-1)
    return {"shifts": m.get("shifts", []), "lcpEl": m.get("lcpEl", ""), "fcp": fcp, "lcp": m["lcp"] or 0, "cls": m["cls"], "tbt": tbt, "bytes": sum(sizes.values()), "requests": len(sizes), "errors": list(tab.errors)}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--wait", type=float, default=9.0)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    browser = Browser(port=9488)
    report: dict[str, dict] = {}
    try:
        tab = browser.tab()
        tab.call("Emulation.setDeviceMetricsOverride", width=412, height=823, deviceScaleFactor=1.75, mobile=True)
        tab.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"}])
        tab.call("Page.addScriptToEvaluateOnNewDocument", source=OBSERVERS)
        for path in args.paths:
            url = args.base.rstrip("/") + ("/" if path in ("brief", "home", "/") else "/" + path.lstrip("/"))
            runs = [one_load(tab, url, args.wait) for _ in range(args.runs)]
            audit = tab.js(PAGE_AUDIT)
            med = {k: statistics.median(r[k] for r in runs) for k in ("fcp", "lcp", "cls", "tbt", "bytes", "requests")}
            report[path] = {"median": med, "runs": runs, "audit": audit}
            print(f"\n{url}   (median of {args.runs} loads, slow 4G, CPU 4x slower)")
            print(f"  FCP {med['fcp'] / 1000:.2f} s   LCP {med['lcp'] / 1000:.2f} s   CLS {med['cls']:.3f}   TBT {med['tbt']:.0f} ms   {med['requests']:.0f} requests, {med['bytes'] / 1024:.0f} KB transferred")
            good = med["fcp"] <= 1800 and med["lcp"] <= 2500 and med["cls"] <= 0.1 and med["tbt"] <= 200
            print(f"  against Lighthouse's 'good' limits (FCP 1.8 s, LCP 2.5 s, CLS 0.1, TBT 200 ms): {'all good' if good else 'NOT all good'}")
            print(f"  accessibility and best practice in the page: {'no failures' if not audit['fails'] else str(len(audit['fails'])) + ' failures'}  "
                  f"(text 12 px or larger: {audit['textAtLeast12px']}%, tap targets 44 px or larger: {audit['tapTargets']['atLeast44']} of {audit['tapTargets']['total']}, under 24 px: {audit['tapTargets']['under24']})")
            print(f"  LCP element: {runs[0]['lcpEl']}")
            for when, value, who in sorted(runs[0]["shifts"], key=lambda x: -x[1])[:3]:
                print(f"  layout shift {value} at {when} ms: {who}")
            for f in audit["fails"][:10]:
                print("    - " + f)
            for n in audit["notes"][:4]:
                print("    note: " + n)
            for e in runs[0]["errors"][:3]:
                print("    console or network error: " + e)
    finally:
        browser.close()
    if args.json:
        args.json.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
