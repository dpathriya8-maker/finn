"""Run every source probe for a few companies and print a table.

From the backend folder:   python -m probes.run_probes [SYMBOL ...]
Default symbols: RELIANCE KAYNES BAJFINANCE CDSL. A JSON copy of the report goes to probes/out/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from probes.probes import PROBES, report

DEFAULT_SYMBOLS = ["RELIANCE", "KAYNES", "BAJFINANCE", "CDSL"]
OUT = Path(__file__).resolve().parent / "out"


def main(argv: list[str]) -> int:
    symbols = [s.upper() for s in argv] or DEFAULT_SYMBOLS
    reports = {s: report(s) for s in symbols}

    width = max(len(n) for n in PROBES) + 2
    print("".ljust(width) + "".join(s.ljust(14) for s in symbols))
    for name in PROBES:
        cells = []
        for s in symbols:
            r = next(x for x in reports[s]["results"] if x["name"] == name)
            cells.append(f"{'ok' if r['ok'] else 'FAIL'} {r['ms']}ms".ljust(14))
        print(name.ljust(width) + "".join(cells))

    print()
    for s in symbols:
        for r in reports[s]["results"]:
            print(f"[{s}] {r['name']}: {'ok  ' if r['ok'] else 'FAIL'} {r['detail']}")

    OUT.mkdir(exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    return 0 if all(r["ok"] for rep in reports.values() for r in rep["results"]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
