# Election Prediction Game 2026

This repository contains two prediction game flows for the Hungarian election:

- Seat-based predictions (199 seats total)
- Percentage-based predictions (100%)

You can collect participant vote codes from the browser pages, then evaluate and rank predictions with Python scripts.

## Project Files

- `election_prediction.html`
  - Browser UI for seat-based predictions
  - Generates `TIPP-...` vote codes
- `election_percentage_prediction.html`
  - Browser UI for percentage-based predictions
  - Generates `PCT-...` vote codes
- `evaluate.py`
  - Evaluator for seat-based predictions
  - Stores data in `predictions.json`
  - Creates HTML report (`results.html` by default)
- `evaluate_percentage.py`
  - Evaluator for percentage-based predictions
  - Accepts `PCT-...` and `TIPP-...` style prefixes
  - Handles base64 padding automatically
  - Stores data in `predictions_percentage.json`
  - Exports spreadsheet-friendly CSV to `predictions_percentage.csv`
  - Creates HTML report (`results_percentage.html` by default)
- `predictions`
  - Optional plain text input file with one vote code per line

## Requirements

- Python 3.9+
- No third-party Python packages are required (standard library only)

## Quick Start

### 1) Collect predictions

Open one of the HTML files in a browser:

- Seat game: `election_prediction.html`
- Percentage game: `election_percentage_prediction.html`

Participants generate and share vote codes.

### 2) Add predictions

Seat-based:

```bash
python3 evaluate.py add "TIPP-..."
python3 evaluate.py add --file predictions
```

Percentage-based:

```bash
python3 evaluate_percentage.py add "PCT-..."
python3 evaluate_percentage.py add --file predictions
```

### 3) List stored predictions

```bash
python3 evaluate.py list
python3 evaluate_percentage.py list
```

### 4) Evaluate with actual results

Seat-based input order:

`FI TI DK MH MK`

Example:

```bash
python3 evaluate.py evaluate 95 84 10 6 4
```

Percentage-based input order:

`FI TI DK MH MK`

Example:

```bash
python3 evaluate_percentage.py evaluate 42.5 40.0 7.5 5.0 5.0
```

### 5) Generate HTML report

Seat-based:

```bash
python3 evaluate.py report 95 84 10 6 4
# optional custom output
python3 evaluate.py report 95 84 10 6 4 --output my_seat_results.html
```

Percentage-based:

```bash
python3 evaluate_percentage.py report 42.5 40.0 7.5 5.0 5.0
# optional custom output
python3 evaluate_percentage.py report 42.5 40.0 7.5 5.0 5.0 --output my_pct_results.html
```

## Vote Code Payload

Both flows encode JSON payloads in base64 with a prefix.

Common payload keys:

- `n`: player name
- `fi`: FIDESZ value
- `ti`: TISZA value
- `dk`: DK value
- `mh`: MHM value
- `mk`: MKKP value
- `d`: ISO timestamp

Prefixes:

- Seat codes: `TIPP-...`
- Percentage codes: `PCT-...`

## Output Files

Seat workflow:

- `predictions.json`
- `results.html`

Percentage workflow:

- `predictions_percentage.json`
- `predictions_percentage.csv` (Excel/Sheets friendly)
- `results_percentage.html`

## Notes

- Predictions are upserted by player name (same name replaces previous entry).
- `evaluate.py` warns when seat totals are not 199.
- `evaluate_percentage.py` warns when totals are not close to 100%.
- The repository `.gitignore` ignores generated `predictions*` and `results*` files.


- **Fully vibecoded (Claude Opus 4.6, GPT-5.3-Codex-Xhigh)**