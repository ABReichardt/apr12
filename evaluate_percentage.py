#!/usr/bin/env python3
"""
Election Prediction Game 2026 - Percentage Evaluation Tool

Usage:
    python evaluate_percentage.py add <vote_code>              Add a single prediction
    python evaluate_percentage.py add --file predictions.txt   Add from file (one code per line)
    python evaluate_percentage.py list                         List all predictions
    python evaluate_percentage.py evaluate FI TI DK MH MK      Compare against actual percentages
    python evaluate_percentage.py report FI TI DK MH MK        Generate HTML results report
"""

import argparse
import base64
import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path

PREDICTIONS_FILE = Path("predictions_percentage.json")
PREDICTIONS_CSV_FILE = Path("predictions_percentage.csv")
PARTY_KEYS = ["fidesz", "tisza", "dk", "mhm", "mkkp"]
PARTY_NAMES = {
    "fidesz": "FIDESZ",
    "tisza": "TISZA",
    "dk": "DK",
    "mhm": "MHM",
    "mkkp": "MKKP",
}
PARTY_COLORS = {
    "fidesz": "#f47920",
    "tisza": "#22b8cf",
    "dk": "#3b82f6",
    "mhm": "#16a34a",
    "mkkp": "#a855f7",
}
TOTAL_PERCENT = 100.0
TOTAL_TOLERANCE = 0.2


# -- Helpers -----------------------------------------------------------------

def fmt_num(value: float, places: int = 2) -> str:
    s = f"{float(value):.{places}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def extract_code(text: str) -> str:
    """Extract a PCT- code from a text input."""
    m = re.search(r"PCT-[A-Za-z0-9+/=_-]+", text)
    return m.group(0) if m else text.strip()


def _decode_payload(code: str) -> dict:
    payload = extract_code(code)
    if not payload.startswith("PCT-"):
        raise ValueError("Percentage evaluator only accepts PCT- vote codes")
    payload = payload[4:]

    if not payload:
        raise ValueError("Empty vote code payload")

    # Accept both regular and URL-safe base64, with or without '=' padding.
    payload = payload.replace("-", "+").replace("_", "/")
    padding = (-len(payload)) % 4
    if padding:
        payload += "=" * padding

    raw = base64.b64decode(payload, validate=False).decode("utf-8")
    return json.loads(raw)


def _parse_pct(d: dict, key: str) -> float:
    try:
        value = float(d[key])
    except KeyError as exc:
        raise ValueError(f"Missing '{key}' in vote data") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid '{key}' value") from exc

    if not math.isfinite(value):
        raise ValueError(f"Invalid '{key}' value: not finite")
    if value < 0 or value > 100:
        raise ValueError(f"Invalid '{key}' value: {value} (must be between 0 and 100)")

    return round(value, 4)


def decode_vote(code: str) -> dict:
    d = _decode_payload(code)
    name = str(d.get("n", "")).strip()
    if not name:
        raise ValueError("Missing or empty name ('n')")

    vote = {
        "name": name,
        "fidesz": _parse_pct(d, "fi"),
        "tisza": _parse_pct(d, "ti"),
        "dk": _parse_pct(d, "dk"),
        "mhm": _parse_pct(d, "mh"),
        "mkkp": _parse_pct(d, "mk"),
        "timestamp": str(d.get("d", "")),
    }

    return vote


# -- Storage -----------------------------------------------------------------

def load_predictions() -> list:
    if PREDICTIONS_FILE.exists():
        data = json.loads(PREDICTIONS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    return []


def save_predictions_csv(preds: list):
    with PREDICTIONS_CSV_FILE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "fidesz", "tisza", "dk", "mhm", "mkkp", "total", "timestamp"])
        for p in sorted(preds, key=lambda x: x["name"].lower()):
            total = sum(float(p[k]) for k in PARTY_KEYS)
            writer.writerow(
                [
                    p["name"],
                    fmt_num(p["fidesz"]),
                    fmt_num(p["tisza"]),
                    fmt_num(p["dk"]),
                    fmt_num(p["mhm"]),
                    fmt_num(p["mkkp"]),
                    fmt_num(total),
                    p.get("timestamp", ""),
                ]
            )


def save_predictions(preds: list):
    PREDICTIONS_FILE.write_text(json.dumps(preds, indent=2, ensure_ascii=False), encoding="utf-8")
    save_predictions_csv(preds)


# -- Commands ----------------------------------------------------------------

def cmd_add(args):
    preds = load_predictions()

    if args.file:
        lines = Path(args.file).read_text(encoding="utf-8").splitlines()
        codes = [extract_code(line) for line in lines if line.strip()]
    elif args.code:
        codes = [extract_code(args.code)]
    else:
        print("Provide a vote code or --file.")
        return

    for code in codes:
        try:
            data = decode_vote(code)
        except Exception as exc:
            print(f"  [!] Failed to decode: {code[:40]}... ({exc})")
            continue

        preds = [p for p in preds if p["name"] != data["name"]]
        preds.append(data)

        total = sum(data[k] for k in PARTY_KEYS)
        total_note = ""
        if abs(total - TOTAL_PERCENT) > TOTAL_TOLERANCE:
            total_note = " [warn: total not 100%]"
        ts = data["timestamp"][:10] if data["timestamp"] else "?"

        print(
            f"  + {data['name']:<16} "
            + " ".join(f"{PARTY_NAMES[k]}={fmt_num(data[k])}%" for k in PARTY_KEYS)
            + f"  (total={fmt_num(total)}%, date={ts}){total_note}"
        )

    save_predictions(preds)
    print(f"\n{len(preds)} prediction(s) stored in {PREDICTIONS_FILE}")
    print(f"CSV export updated: {PREDICTIONS_CSV_FILE}")


def cmd_list(args):
    preds = load_predictions()
    if not preds:
        print("No predictions yet. Use 'add' to add vote codes.")
        return

    hdr = (
        f"{'Name':<18}"
        + "".join(f"{PARTY_NAMES[k]:>9}" for k in PARTY_KEYS)
        + f"{'Total':>9}{'Date':>12}"
    )
    print(hdr)
    print("-" * len(hdr))

    for p in sorted(preds, key=lambda x: x["name"].lower()):
        total = sum(float(p[k]) for k in PARTY_KEYS)
        row = f"{p['name']:<18}"
        row += "".join(f"{fmt_num(float(p[k])):>9}" for k in PARTY_KEYS)
        row += f"{fmt_num(total):>9}"
        ts = p.get("timestamp", "")[:10] if p.get("timestamp") else "?"
        row += f"{ts:>12}"
        print(row)


def evaluate_predictions(preds: list, actual: dict) -> list:
    """Score each prediction and return sorted results (best first)."""
    results = []
    actual_winner = max(PARTY_KEYS, key=lambda k: actual[k])
    actual_order = sorted(PARTY_KEYS, key=lambda k: -actual[k])

    for p in preds:
        prediction = {k: float(p[k]) for k in PARTY_KEYS}
        errors = {k: abs(prediction[k] - actual[k]) for k in PARTY_KEYS}
        tae = sum(errors.values())
        max_err = max(errors.values())
        rmse = math.sqrt(sum(e ** 2 for e in errors.values()) / len(errors))

        pred_winner = max(PARTY_KEYS, key=lambda k: prediction[k])
        pred_order = sorted(PARTY_KEYS, key=lambda k: -prediction[k])

        results.append(
            {
                "name": p["name"],
                "prediction": prediction,
                "errors": errors,
                "tae": tae,
                "max_error": max_err,
                "rmse": rmse,
                "correct_winner": pred_winner == actual_winner,
                "correct_order": pred_order == actual_order,
                "timestamp": p.get("timestamp", ""),
            }
        )

    results.sort(key=lambda r: (r["tae"], r["max_error"], r["rmse"], r["name"].lower()))
    return results


def cmd_evaluate(args):
    actual = dict(zip(PARTY_KEYS, [args.fidesz, args.tisza, args.dk, args.mhm, args.mkkp]))
    total = sum(actual.values())
    if abs(total - TOTAL_PERCENT) > TOTAL_TOLERANCE:
        print(f"Warning: actual percentages sum to {fmt_num(total)}%, expected 100%")

    preds = load_predictions()
    if not preds:
        print("No predictions. Use 'add' first.")
        return

    results = evaluate_predictions(preds, actual)

    print("\n  PERCENTAGE PREDICTION RESULTS\n")
    print("  Actual: " + "  ".join(f"{PARTY_NAMES[k]}={fmt_num(actual[k])}%" for k in PARTY_KEYS))
    print()

    print(f"  {'Rank':<6}{'Name':<18}{'Error':>10}{'MaxErr':>10}{'RMSE':>10}{'Winner':>9}{'Order':>8}")
    print("  " + "-" * 71)
    for i, r in enumerate(results, start=1):
        wm = "yes" if r["correct_winner"] else "-"
        om = "yes" if r["correct_order"] else "-"
        print(
            f"  {str(i)+'.':<6}{r['name']:<18}{fmt_num(r['tae']):>10}{fmt_num(r['max_error']):>10}"
            f"{fmt_num(r['rmse']):>10}{wm:>9}{om:>8}"
        )

    print("\n  Per-person breakdown:")
    for r in results:
        print(f"\n  {r['name']}:")
        for k in PARTY_KEYS:
            pred = r["prediction"][k]
            act = actual[k]
            err = r["errors"][k]
            arrow = "^" if pred > act else ("v" if pred < act else "=")
            print(
                f"    {PARTY_NAMES[k]:<8}  predicted {fmt_num(pred):>6}%  "
                f"actual {fmt_num(act):>6}%  error {fmt_num(err):>6}% {arrow}"
            )

    print("\n  Awards:")
    for k in PARTY_KEYS:
        best = min(results, key=lambda r: r["errors"][k])
        print(
            f"    Closest {PARTY_NAMES[k]:<8} prediction: {best['name']} "
            f"(off by {fmt_num(best['errors'][k])}%)"
        )


def cmd_report(args):
    actual = dict(zip(PARTY_KEYS, [args.fidesz, args.tisza, args.dk, args.mhm, args.mkkp]))
    preds = load_predictions()
    if not preds:
        print("No predictions.")
        return

    results = evaluate_predictions(preds, actual)
    out = args.output or "results_percentage.html"

    rows_html = ""
    for i, r in enumerate(results, start=1):
        wm = "yes" if r["correct_winner"] else "no"
        om = "yes" if r["correct_order"] else "no"
        rows_html += (
            "<tr>"
            f"<td>{i}</td><td><strong>{r['name']}</strong></td>"
            f"<td>{fmt_num(r['tae'])}</td><td>{fmt_num(r['max_error'])}</td><td>{fmt_num(r['rmse'])}</td>"
            f"<td>{wm}</td><td>{om}</td>"
            "</tr>\n"
        )

    detail_cards = ""
    for i, r in enumerate(results, start=1):
        bars = ""
        for k in PARTY_KEYS:
            p_val = r["prediction"][k]
            a_val = actual[k]
            err = r["errors"][k]
            p_w = max(0.0, min(100.0, p_val))
            a_pos = max(0.0, min(100.0, a_val))
            bars += f"""
            <div class="bar-row">
                <div class="bar-label"><span class="dot" style="background:{PARTY_COLORS[k]}"></span>{PARTY_NAMES[k]}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{p_w:.3f}%;background:{PARTY_COLORS[k]}"></div>
                    <div class="bar-marker" style="left:{a_pos:.3f}%"></div>
                </div>
                <div class="bar-values">{fmt_num(p_val)}% vs {fmt_num(a_val)}%</div>
                <div class="bar-error">off by {fmt_num(err)}%</div>
            </div>
            """

        detail_cards += f"""
        <div class="detail-card">
            <h3>#{i} {r['name']} <span class="meta">(total error: {fmt_num(r['tae'])})</span></h3>
            <div class="bars">{bars}</div>
        </div>
        """

    actual_badges = " ".join(
        f'<span class="badge" style="background:{PARTY_COLORS[k]}">{PARTY_NAMES[k]} {fmt_num(actual[k])}%</span>'
        for k in PARTY_KEYS
    )

    awards_html = ""
    for k in PARTY_KEYS:
        best = min(results, key=lambda r: r["errors"][k])
        awards_html += (
            f'<div class="award"><strong style="color:{PARTY_COLORS[k]}">{PARTY_NAMES[k]}</strong> '
            f'closest: {best["name"]} (off by {fmt_num(best["errors"][k])}%)</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Election Percentage Prediction Results 2026</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0f4f8;color:#2d3748;line-height:1.5;padding:20px}}
.container{{max-width:920px;margin:0 auto}}
h1{{text-align:center;margin-bottom:4px}}
.sub{{text-align:center;color:#718096;margin-bottom:18px}}
.card{{background:#fff;border-radius:12px;padding:22px;box-shadow:0 2px 10px rgba(0,0,0,.08);margin-bottom:18px}}
.actual-wrap{{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:8px}}
.badge{{color:#fff;padding:5px 14px;border-radius:20px;font-weight:700;font-size:.9em}}
table{{width:100%;border-collapse:collapse;margin-top:10px}}
th,td{{padding:9px 11px;text-align:center;border-bottom:1px solid #e2e8f0}}
th{{background:#edf2f7;font-size:.9em}}
tr:hover{{background:#f7fafc}}
.award{{margin:4px 0}}
.detail-card{{background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 6px rgba(0,0,0,.07);margin:12px 0}}
.detail-card h3{{margin-bottom:10px}}
.meta{{color:#718096;font-weight:400;font-size:.9em}}
.bars{{display:grid;gap:10px}}
.bar-row{{display:grid;grid-template-columns:120px 1fr 150px 120px;gap:10px;align-items:center}}
.bar-label{{font-weight:700;display:flex;align-items:center;gap:8px}}
.dot{{width:12px;height:12px;border-radius:3px;display:inline-block}}
.bar-track{{position:relative;height:12px;background:#e2e8f0;border-radius:999px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:999px}}
.bar-marker{{position:absolute;top:0;bottom:0;width:2px;background:#1a202c;transform:translateX(-1px)}}
.bar-values{{font-size:.88em;color:#4a5568}}
.bar-error{{font-size:.88em;color:#2d3748;font-weight:600}}
@media (max-width:820px){{
  .bar-row{{grid-template-columns:1fr;gap:6px}}
}}
</style>
</head>
<body>
<div class="container">
<h1>Election Percentage Prediction Results 2026</h1>
<p class="sub">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

<div class="card">
<h2 style="text-align:center;margin-bottom:8px">Actual Results</h2>
<div class="actual-wrap">{actual_badges}</div>
</div>

<div class="card">
<h2 style="text-align:center;margin-bottom:6px">Rankings</h2>
<table>
<tr><th>Rank</th><th>Name</th><th>Total Error</th><th>Max Error</th><th>RMSE</th><th>Winner?</th><th>Order?</th></tr>
{rows_html}
</table>
</div>

<div class="card">
<h2 style="text-align:center;margin-bottom:6px">Awards</h2>
{awards_html}
</div>

<h2 style="text-align:center;margin:20px 0 8px">Detailed Predictions</h2>
{detail_cards}

</div>
</body>
</html>"""

    Path(out).write_text(html, encoding="utf-8")
    print(f"Report saved to {out}")


# -- CLI ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Election Prediction Game - Percentage Evaluation Tool")
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="Add prediction(s)")
    p_add.add_argument("code", nargs="?", help="Vote code (PCT-...)")
    p_add.add_argument("--file", "-f", help="File with one vote code per line")

    sub.add_parser("list", help="List all stored predictions")

    p_eval = sub.add_parser("evaluate", help="Evaluate against actual percentages")
    p_eval.add_argument("fidesz", type=float, help="FIDESZ percentage")
    p_eval.add_argument("tisza", type=float, help="TISZA percentage")
    p_eval.add_argument("dk", type=float, help="DK percentage")
    p_eval.add_argument("mhm", type=float, help="MHM percentage")
    p_eval.add_argument("mkkp", type=float, help="MKKP percentage")

    p_rep = sub.add_parser("report", help="Generate HTML results report")
    p_rep.add_argument("fidesz", type=float, help="FIDESZ percentage")
    p_rep.add_argument("tisza", type=float, help="TISZA percentage")
    p_rep.add_argument("dk", type=float, help="DK percentage")
    p_rep.add_argument("mhm", type=float, help="MHM percentage")
    p_rep.add_argument("mkkp", type=float, help="MKKP percentage")
    p_rep.add_argument("--output", "-o", help="Output file (default: results_percentage.html)")

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
