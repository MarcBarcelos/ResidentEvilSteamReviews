#!/usr/bin/env python3
"""
Runner script that reads a CSV of Steam games and runs steam_reviews.py
for each entry, saving each game's reviews to its own CSV file.

Usage:
    python run_all_reviews.py --csv resident_evil_steam_games.csv --out-dir reviews/
    python run_all_reviews.py --csv games.csv --out-dir reviews/ --language english

Arguments:
    Here are all the arguments `run_all_reviews.py` accepts:

    **Required:**
    - `--csv` — Path to the CSV file with the games list (must have `Game` and `Steam App ID` columns)

    **Optional:**
    - `--out-dir` — Directory for output files (default: `reviews`)
    - `--script` — Path to `steam_reviews.py` (default: `steam_reviews.py` in current directory)
    - `--skip-existing` — Flag (no value); skip games whose output CSV already exists, useful for resuming interrupted runs

    **Passed through to `steam_reviews.py`:**
    - `--language` — Review language, e.g. `english` or `all` (default: `all`)
    - `--delay` — Seconds between API requests (default: `0.25`)
    - `--purchase-type` — `all`, `steam`, or `non_steam` (default: `all`)
    - `--review-type` — `all`, `positive`, or `negative` (default: `all`)
    - `--filter-offtopic-activity` — `1` to exclude review bombs, `0` to include them (default: `0`)

    A few example invocations:

    ```bash
    # Bare minimum
    python run_all_reviews.py --csv resident_evil_steam_games.csv

    # English only, custom output folder, exclude review bombs
    python run_all_reviews.py --csv games.csv --out-dir re_reviews --language english --filter-offtopic-activity 1

    # Resume after interruption
    python run_all_reviews.py --csv games.csv --skip-existing

    # Faster (riskier — Steam might rate-limit you)
    python run_all_reviews.py --csv games.csv --delay 0.1
    ```

    You can also run `python run_all_reviews.py --help` to get this list directly from the script.

IN THIS CASE:
    python run_all_reviews.py \
  --csv ../resident_evil_steam_games.csv \
  --language english \
  --out-dir ../raw_reviews \
  --skip-existing
"""

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path


def slugify(name: str) -> str:
    """Turn a game name into a safe filename."""
    # Replace anything that isn't alphanumeric with an underscore, collapse runs
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return slug or "game"


def main():
    p = argparse.ArgumentParser(
        description="Run steam_reviews.py for every game in a CSV."
    )
    p.add_argument(
        "--csv",
        type=str,
        required=True,
        help="Path to CSV with a 'Steam App ID' column and a 'Game' column.",
    )
    p.add_argument(
        "--out-dir",
        type=str,
        default="reviews",
        help="Directory to write per-game CSVs into (created if missing).",
    )
    p.add_argument(
        "--script",
        type=str,
        default="steam_reviews.py",
        help="Path to the steam_reviews.py script.",
    )
    p.add_argument(
        "--language",
        type=str,
        default="all",
        help='Review language passed to steam_reviews.py (e.g., "english" or "all").',
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="Delay between API requests (passed through to steam_reviews.py).",
    )
    p.add_argument(
        "--purchase-type",
        type=str,
        default="all",
        help='Purchase type: "all", "steam", or "non_steam".',
    )
    p.add_argument(
        "--review-type",
        type=str,
        default="all",
        help='Review type: "all", "positive", or "negative".',
    )
    p.add_argument(
        "--filter-offtopic-activity",
        type=int,
        default=0,
        help="1 to filter offtopic activity (review-bombs), else 0.",
    )
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip games whose output CSV already exists.",
    )
    args = p.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.is_file():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    script_path = Path(args.script)
    if not script_path.is_file():
        print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Read all rows up front so we can show progress like "[3/17]"
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("No rows found in CSV.", file=sys.stderr)
        sys.exit(1)

    # Validate required columns
    required = {"Game", "Steam App ID"}
    missing = required - set(rows[0].keys())
    if missing:
        print(f"ERROR: CSV is missing required column(s): {missing}", file=sys.stderr)
        sys.exit(1)

    total = len(rows)
    successes = 0
    failures = []
    skipped = 0

    for i, row in enumerate(rows, start=1):
        name = (row.get("Game") or "").strip()
        app_id_raw = (row.get("Steam App ID") or "").strip()

        if not name or not app_id_raw:
            print(f"[{i}/{total}] Skipping row with missing data: {row}")
            continue

        try:
            app_id = int(app_id_raw)
        except ValueError:
            print(f"[{i}/{total}] Skipping {name!r}: invalid App ID {app_id_raw!r}")
            failures.append((name, "invalid app id"))
            continue

        out_file = out_dir / f"{slugify(name)}_{app_id}.csv"

        if args.skip_existing and out_file.exists():
            print(f"[{i}/{total}] {name} -> already exists, skipping ({out_file})")
            skipped += 1
            continue

        print(f"\n[{i}/{total}] Fetching reviews for {name} (App ID {app_id})")
        print(f"           -> {out_file}")

        cmd = [
            sys.executable,
            str(script_path),
            "--app-id", str(app_id),
            "--out", str(out_file),
            "--language", args.language,
            "--delay", str(args.delay),
            "--purchase-type", args.purchase_type,
            "--review-type", args.review_type,
            "--filter-offtopic-activity", str(args.filter_offtopic_activity),
        ]

        try:
            subprocess.run(cmd, check=True)
            successes += 1
        except KeyboardInterrupt:
            print("\nInterrupted by user. Stopping.")
            break
        except subprocess.CalledProcessError as e:
            print(f"  FAILED for {name}: exit code {e.returncode}")
            failures.append((name, f"exit code {e.returncode}"))

    print("\n" + "=" * 60)
    print(f"Done. Success: {successes} | Skipped: {skipped} | Failed: {len(failures)}")
    if failures:
        print("Failures:")
        for name, reason in failures:
            print(f"  - {name}: {reason}")


if __name__ == "__main__":
    main()
