#!/usr/bin/env python3
"""
Election Prediction Game 2026 — Evaluation Tool

Usage:
    python evaluate.py add <vote_code>              Add a single prediction
    python evaluate.py add --file predictions.txt   Add from file (one code per line)
    python evaluate.py list                         List all predictions
    python evaluate.py evaluate FI TI DK MH MK      Compare against actual results
    python evaluate.py report FI TI DK MH MK        Generate HTML results report
"""

import argparse
import base64
import json
import math
import re
import sys
from pathlib import Path
from datetime import datetime

PREDICTIONS_FILE = Path("predictions.json")
PARTY_KEYS = ["fidesz", "tisza", "dk", "mhm", "mkkp"]
PARTY_NAMES = {
    "fidesz": "FIDESZ", "tisza": "TISZA", "dk": "DK",
    "mhm": "MHM", "mkkp": "MKKP",
}
PARTY_COLORS = {
    "fidesz": "#f47920", "tisza": "#22b8cf", "dk": "#3b82f6",
    "mhm": "#16a34a", "mkkp": "#a855f7",
}
FILL_ORDER = ["dk", "mkkp", "tisza", "mhm", "fidesz"]
TOTAL_SEATS = 199


# ── Codec ──────────────────────────────────────────────────────

def extract_code(text: str) -> str:
    """Extract a TIPP- code from text (e.g. a chat message)."""
    m = re.search(r"TIPP-[A-Za-z0-9+/=]+", text)
    return m.group(0) if m else text.strip()


def decode_vote(code: str) -> dict:
    b64 = code.removeprefix("TIPP-")
    raw = base64.b64decode(b64).decode("utf-8")
    d = json.loads(raw)
    return {
        "name": d["n"],
        "fidesz": d["fi"],
        "tisza": d["ti"],
        "dk": d["dk"],
        "mhm": d["mh"],
        "mkkp": d["mk"],
        "timestamp": d.get("d", ""),
    }


# ── Storage ────────────────────────────────────────────────────

def load_predictions() -> list:
    if PREDICTIONS_FILE.exists():
        return json.loads(PREDICTIONS_FILE.read_text())
    return []


def save_predictions(preds: list):
    PREDICTIONS_FILE.write_text(json.dumps(preds, indent=2, ensure_ascii=False))


# ── Commands ───────────────────────────────────────────────────

def cmd_add(args):
    preds = load_predictions()

    codes = []
    if args.file:
        lines = Path(args.file).read_text().strip().splitlines()
        codes = [extract_code(l) for l in lines if l.strip()]
    elif args.code:
        codes = [extract_code(args.code)]
    else:
        print("Provide a vote code or --file.")
        return

    for code in codes:
        try:
            data = decode_vote(code)
        except Exception as e:
            print(f"  [!] Failed to decode: {code[:40]}... ({e})")
            continue
        # Upsert by name
        preds = [p for p in preds if p["name"] != data["name"]]
        preds.append(data)
        total = sum(data[k] for k in PARTY_KEYS)
        ts = data["timestamp"][:10] if data["timestamp"] else "?"
        print(f"  + {data['name']:<16} "
              + " ".join(f"{PARTY_NAMES[k]}={data[k]}" for k in PARTY_KEYS)
              + f"  (total={total}, date={ts})")

    save_predictions(preds)
    print(f"\n{len(preds)} prediction(s) stored in {PREDICTIONS_FILE}")


def cmd_list(args):
    preds = load_predictions()
    if not preds:
        print("No predictions yet. Use 'add' to add vote codes.")
        return

    hdr = f"{'Name':<16}" + "".join(f"{PARTY_NAMES[k]:>8}" for k in PARTY_KEYS) + f"{'Date':>12}"
    print(hdr)
    print("-" * len(hdr))
    for p in sorted(preds, key=lambda x: x["name"].lower()):
        row = f"{p['name']:<16}"
        row += "".join(f"{p[k]:>8}" for k in PARTY_KEYS)
        ts = p["timestamp"][:10] if p.get("timestamp") else "?"
        row += f"{ts:>12}"
        print(row)


def evaluate_predictions(preds: list, actual: dict) -> list:
    """Score each prediction, return sorted results (best first)."""
    results = []
    actual_winner = max(PARTY_KEYS, key=lambda k: actual[k])

    for p in preds:
        errors = {k: abs(p[k] - actual[k]) for k in PARTY_KEYS}
        tae = sum(errors.values())
        max_err = max(errors.values())
        rmse = math.sqrt(sum(e ** 2 for e in errors.values()) / len(errors))

        pred_winner = max(PARTY_KEYS, key=lambda k: p[k])
        pred_order = sorted(PARTY_KEYS, key=lambda k: -p[k])
        actual_order = sorted(PARTY_KEYS, key=lambda k: -actual[k])

        results.append({
            "name": p["name"],
            "prediction": {k: p[k] for k in PARTY_KEYS},
            "errors": errors,
            "tae": tae,
            "max_error": max_err,
            "rmse": round(rmse, 2),
            "correct_winner": pred_winner == actual_winner,
            "correct_order": pred_order == actual_order,
            "timestamp": p.get("timestamp", ""),
        })

    results.sort(key=lambda r: (r["tae"], r["max_error"]))
    return results


def cmd_evaluate(args):
    actual = dict(zip(PARTY_KEYS, [args.fidesz, args.tisza, args.dk, args.mhm, args.mkkp]))
    total = sum(actual.values())
    if total != TOTAL_SEATS:
        print(f"Warning: actual seats sum to {total}, expected {TOTAL_SEATS}")

    preds = load_predictions()
    if not preds:
        print("No predictions. Use 'add' first.")
        return

    results = evaluate_predictions(preds, actual)
    medals = {0: "\U0001f947", 1: "\U0001f948", 2: "\U0001f949"}

    print("\n  ELECTION PREDICTION RESULTS\n")
    print("  Actual: " + "  ".join(f"{PARTY_NAMES[k]}={actual[k]}" for k in PARTY_KEYS))
    print()

    print(f"  {'Rank':<6}{'Name':<16}{'Error':>7}{'MaxErr':>8}{'RMSE':>7}{'Winner':>8}{'Order':>7}")
    print("  " + "-" * 59)
    for i, r in enumerate(results):
        medal = medals.get(i, f"{i+1}.")
        wm = "yes" if r["correct_winner"] else "-"
        om = "yes" if r["correct_order"] else "-"
        print(f"  {medal:<6}{r['name']:<16}{r['tae']:>7}{r['max_error']:>8}{r['rmse']:>7}{wm:>8}{om:>7}")

    print("\n  Per-person breakdown:")
    for r in results:
        print(f"\n  {r['name']}:")
        for k in PARTY_KEYS:
            pred = r["prediction"][k]
            act = actual[k]
            err = r["errors"][k]
            arrow = "\u2191" if pred > act else ("\u2193" if pred < act else "=")
            print(f"    {PARTY_NAMES[k]:<8}  predicted {pred:>3}  actual {act:>3}  error {err:>3} {arrow}")

    # Fun awards
    print("\n  Awards:")
    for k in PARTY_KEYS:
        best = min(results, key=lambda r: r["errors"][k])
        print(f"    Closest {PARTY_NAMES[k]:<8} prediction: {best['name']} (off by {best['errors'][k]})")


# ── HTML report ────────────────────────────────────────────────

def _svg_parliament(counts: dict, w: int = 500, h: int = 260) -> str:
    """Generate an SVG parliament visualization string."""
    rows = [(9,85),(13,105),(17,125),(21,145),(23,165),(25,185),(27,205),(29,225),(35,245)]
    scale = w / 600
    cx, cy = w / 2, h - 15 * scale
    dot_r = 7 * scale
    pad = 0.12
    parts = [f'<svg viewBox="0 0 {w} {h}" width="{w}" xmlns="http://www.w3.org/2000/svg">']

    # Build color map
    color_map = {}
    idx = 0
    for party in FILL_ORDER:
        for _ in range(counts.get(party, 0)):
            color_map[idx] = PARTY_COLORS[party]
            idx += 1

    idx = 0
    for n_seats, radius in rows:
        r = radius * scale
        for i in range(n_seats):
            angle = (math.pi - pad) - i * (math.pi - 2 * pad) / (n_seats - 1) if n_seats > 1 else math.pi / 2
            x = cx + r * math.cos(angle)
            y = cy - r * math.sin(angle)
            color = color_map.get(idx, "#dfe4ea")
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{dot_r:.1f}" fill="{color}"/>')
            idx += 1

    parts.append("</svg>")
    return "\n".join(parts)


def cmd_report(args):
    actual = dict(zip(PARTY_KEYS, [args.fidesz, args.tisza, args.dk, args.mhm, args.mkkp]))
    preds = load_predictions()
    if not preds:
        print("No predictions.")
        return

    results = evaluate_predictions(preds, actual)
    medals = {0: "\U0001f947", 1: "\U0001f948", 2: "\U0001f949"}
    out = args.output or "results.html"

    # Build HTML
    rows_html = ""
    for i, r in enumerate(results):
        medal = medals.get(i, f"{i+1}.")
        wm = "\u2714" if r["correct_winner"] else "\u2718"
        rows_html += f"""<tr>
            <td>{medal}</td><td><strong>{r['name']}</strong></td>
            <td>{r['tae']}</td><td>{r['max_error']}</td><td>{r['rmse']}</td>
            <td>{wm}</td></tr>\n"""

    # Per-person detail cards
    detail_cards = ""
    for i, r in enumerate(results):
        medal = medals.get(i, f"#{i+1}")
        svg = _svg_parliament(r["prediction"], 400, 220)
        bars = ""
        for k in PARTY_KEYS:
            p_val = r["prediction"][k]
            a_val = actual[k]
            err = r["errors"][k]
            arrow = "\u2191" if p_val > a_val else ("\u2193" if p_val < a_val else "=")
            bars += f"""<div style="display:flex;align-items:center;gap:8px;margin:3px 0">
                <span style="width:55px;font-weight:700;color:{PARTY_COLORS[k]}">{PARTY_NAMES[k]}</span>
                <span style="width:35px;text-align:right">{p_val}</span>
                <span style="color:#a0aec0">{arrow}</span>
                <span style="width:35px;text-align:right;color:#718096">{a_val}</span>
                <span style="color:#e53e3e;font-size:.85em">(\u00b1{err})</span>
            </div>"""

        detail_cards += f"""
        <div style="background:#fff;border-radius:12px;padding:20px;margin:12px 0;
                     box-shadow:0 1px 6px rgba(0,0,0,.07)">
            <h3>{medal} {r['name']} <span style="color:#a0aec0;font-weight:400;font-size:.8em">
                (error: {r['tae']})</span></h3>
            <div style="display:flex;flex-wrap:wrap;gap:20px;align-items:start;margin-top:10px">
                <div>{svg}</div>
                <div>{bars}</div>
            </div>
        </div>"""

    # Actual results
    actual_svg = _svg_parliament(actual, 500, 260)
    actual_badges = " ".join(
        f'<span style="background:{PARTY_COLORS[k]};color:#fff;padding:5px 14px;'
        f'border-radius:20px;font-weight:700;font-size:.9em">'
        f'{PARTY_NAMES[k]} {actual[k]}</span>'
        for k in PARTY_KEYS
    )

    # Awards
    awards_html = ""
    for k in PARTY_KEYS:
        best = min(results, key=lambda r: r["errors"][k])
        awards_html += (f'<div style="margin:4px 0"><strong style="color:{PARTY_COLORS[k]}">'
                        f'{PARTY_NAMES[k]}</strong> closest: {best["name"]} '
                        f'(off by {best["errors"][k]})</div>')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Election Prediction Results 2026</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
      background:#f0f4f8;color:#2d3748;line-height:1.5;padding:20px}}
.container{{max-width:800px;margin:0 auto}}
h1{{text-align:center;margin-bottom:4px}}
.sub{{text-align:center;color:#718096;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;margin:16px 0}}
th,td{{padding:8px 12px;text-align:center;border-bottom:1px solid #e2e8f0}}
th{{background:#edf2f7;font-size:.9em}}
tr:hover{{background:#f7fafc}}
</style>
</head>
<body>
<div class="container">
<h1>Election Prediction Results 2026</h1>
<p class="sub">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

<div style="background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 10px rgba(0,0,0,.08);margin-bottom:20px">
<h2 style="text-align:center;margin-bottom:12px">Actual Results</h2>
<div style="text-align:center">{actual_svg}</div>
<div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:12px">
{actual_badges}
</div>
</div>

<div style="background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 10px rgba(0,0,0,.08);margin-bottom:20px">
<h2 style="text-align:center;margin-bottom:8px">Rankings</h2>
<table>
<tr><th>Rank</th><th>Name</th><th>Total Error</th><th>Max Error</th><th>RMSE</th><th>Winner?</th></tr>
{rows_html}
</table>
</div>

<div style="background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 10px rgba(0,0,0,.08);margin-bottom:20px">
<h2 style="text-align:center;margin-bottom:8px">Awards</h2>
{awards_html}
</div>

<h2 style="text-align:center;margin:20px 0 8px">Detailed Predictions</h2>
{detail_cards}

</div>
</body>
</html>"""

    Path(out).write_text(html, encoding="utf-8")
    print(f"Report saved to {out}")


# ── CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Election Prediction Game — Evaluation Tool")
    sub = parser.add_subparsers(dest="command")

    # add
    p_add = sub.add_parser("add", help="Add prediction(s)")
    p_add.add_argument("code", nargs="?", help="Vote code (TIPP-...)")
    p_add.add_argument("--file", "-f", help="File with one vote code per line")

    # list
    sub.add_parser("list", help="List all stored predictions")

    # evaluate
    p_eval = sub.add_parser("evaluate", help="Evaluate against actual results")
    p_eval.add_argument("fidesz", type=int, help="FIDESZ seats")
    p_eval.add_argument("tisza", type=int, help="TISZA seats")
    p_eval.add_argument("dk", type=int, help="DK seats")
    p_eval.add_argument("mhm", type=int, help="MHM seats")
    p_eval.add_argument("mkkp", type=int, help="MKKP seats")

    # report
    p_rep = sub.add_parser("report", help="Generate HTML results report")
    p_rep.add_argument("fidesz", type=int, help="FIDESZ seats")
    p_rep.add_argument("tisza", type=int, help="TISZA seats")
    p_rep.add_argument("dk", type=int, help="DK seats")
    p_rep.add_argument("mhm", type=int, help="MHM seats")
    p_rep.add_argument("mkkp", type=int, help="MKKP seats")
    p_rep.add_argument("--output", "-o", help="Output file (default: results.html)")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "report":
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
