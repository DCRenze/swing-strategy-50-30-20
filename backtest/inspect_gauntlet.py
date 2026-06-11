"""Print a readable digest of gauntlet JSONs."""

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"

strategies = sys.argv[1:] or [
    p.stem.replace("gauntlet_", "")
    for p in RESULTS.glob("gauntlet_*.json")
]

for s in strategies:
    d = json.load(open(RESULTS / f"gauntlet_{s}.json"))
    print("=" * 25, s)
    for w in ("full", "is", "oos"):
        x = d["windows"][w]
        print(
            f"  {w:4} cagr={x['cagr']:7.4f} sharpe={x['sharpe']:5.2f} dd={x['max_dd']:8.4f} "
            f"pf={x['profit_factor']} wr={x['win_rate']} n={x['trades']:5d} "
            f"expo={x['exposure']} spySh={x['bench_sharpe']}"
        )
    print("  regimes :", json.dumps(d["regimes"]))
    print("  mc_dd   :", json.dumps(d.get("mc_drawdown")))
    print("  pass    :", json.dumps(d["pass_bar"]))
    for k, v in d["variants"].items():
        print(
            f"    var {k:12} sharpe={v['sharpe']:5.2f} pf={v['profit_factor']} "
            f"dd={v['max_dd']:8.4f} wr={v['win_rate']} n={v['trades']}"
        )
