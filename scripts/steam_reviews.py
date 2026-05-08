#!/usr/bin/env python3
# GPLv3 License
# Copyright (c) 2025 Nicola Mustone
# Author: Nicola Mustone (https://nicolamustone.blog)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import sys
import argparse
import csv
import time
import requests
from datetime import datetime
from urllib.parse import quote
from tqdm import tqdm


if sys.version_info >= (3, 11):
    from datetime import UTC
    UTC_TZ = UTC
else:
    from datetime import timezone
    UTC_TZ = timezone.utc

def as_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, UTC_TZ).date().isoformat() if ts else ""


def b(x) -> int:
    return 1 if bool(x) else 0


def fetch_reviews(
    app_id: int,
    out_csv: str,
    language: str = "all",
    delay: float = 0.25,
    purchase_type: str = "all",
    review_type: str = "all",
    filter_offtopic_activity: int = 0,
    start_cursor: str = "*",
):
    base = f"https://store.steampowered.com/appreviews/{app_id}"
    url = (
        f"{base}?json=1&num_per_page=100&filter=recent&number=0"
        f"&purchase_type={purchase_type}&language={language}"
        f"&filter_offtopic_activity={filter_offtopic_activity}&review_type={review_type}"
        f"&cursor={quote(start_cursor, safe='')}"
    )

    fieldnames = [
        "review",
        "review_length",
        "sentiment",
        "purchased",
        "received_for_free",
        "votes_up",
        "votes_funny",
        "date_created",
        "date_updated",
        "author_num_games_owned",
        "author_num_reviews",
        "author_playtime_forever_min",
        "author_playtime_at_review_min",
    ]

    written = 0
    checked = 0
    seen_ids = set()
    seen_cursors = set()
    pbar = None

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        while True:
            try:
                data = requests.get(url, timeout=30).json()
            except Exception:
                time.sleep(5)
                continue

            if data.get("success") != 1:
                time.sleep(1)
                continue

            # Initialize progress bar on first successful response
            if pbar is None:
                total = (data.get("query_summary") or {}).get("total_reviews", 0)
                pbar = tqdm(total=total, unit="rev", desc=f"App {app_id}")

            reviews = data.get("reviews") or []
            checked += len(reviews)

            for rv in reviews:
                if language != "all" and rv.get("language") != language:
                    continue
                rid = rv.get("recommendationid")
                if not rid or rid in seen_ids:
                    continue
                seen_ids.add(rid)

                a = rv.get("author") or {}
                review_text = (rv.get("review") or "").strip()
                w.writerow(
                    {
                        "review": review_text,
                        "review_length": len(review_text),
                        "sentiment": b(rv.get("voted_up")),
                        "purchased": b(rv.get("steam_purchase")),
                        "received_for_free": b(rv.get("received_for_free")),
                        "votes_up": rv.get("votes_up"),
                        "votes_funny": rv.get("votes_funny"),
                        "date_created": as_date(rv.get("timestamp_created")),
                        "date_updated": as_date(rv.get("timestamp_updated")),
                        "author_num_games_owned": a.get("num_games_owned"),
                        "author_num_reviews": a.get("num_reviews"),
                        "author_playtime_forever_min": a.get("playtime_forever"),
                        "author_playtime_at_review_min": a.get("playtime_at_review"),
                    }
                )
                written += 1
                pbar.update(1)

            pbar.set_postfix(written=written, checked=checked)

            cursor = data.get("cursor")
            num_reviews = (data.get("query_summary") or {}).get("num_reviews", 0)
            if num_reviews == 0 or not cursor or cursor in seen_cursors:
                break

            seen_cursors.add(cursor)
            url = (
                f"{base}?json=1&num_per_page=100&filter=recent&number=0"
                f"&purchase_type={purchase_type}&language={language}"
                f"&filter_offtopic_activity={filter_offtopic_activity}&review_type={review_type}"
                f"&cursor={quote(cursor, safe='')}"
            )

            time.sleep(delay)

    if pbar is not None:
        pbar.close()

    return written, checked


def main():
    p = argparse.ArgumentParser(description="Export Steam app reviews to CSV for NLP.")
    p.add_argument("--app-id", type=int, required=True, help="Steam app ID (required)")
    p.add_argument("--out", type=str, default="steam_reviews.csv", help="Output CSV path")
    p.add_argument("--delay", type=float, default=0.25, help="Delay between requests in seconds")
    p.add_argument("--language", type=str, default="all", help='Review language (e.g., "english" or "all")')
    p.add_argument("--purchase-type", type=str, default="all", help='Purchase type: "all", "steam", or "non_steam"')
    p.add_argument("--review-type", type=str, default="all", help='Review type: "all", "positive", or "negative"')
    p.add_argument("--filter-offtopic-activity", type=int, default=0, help="1 to filter offtopic activity, else 0")
    p.add_argument("--cursor", type=str, default="*", help="Starting cursor token ('*' means begin)")
    args = p.parse_args()

    written, checked = fetch_reviews(
        app_id=args.app_id,
        out_csv=args.out,
        language=args.language,
        delay=args.delay,
        purchase_type=args.purchase_type,
        review_type=args.review_type,
        filter_offtopic_activity=args.filter_offtopic_activity,
        start_cursor=args.cursor,
    )
    print(f"Written ({args.language}): {written} | Checked (all): {checked}")


if __name__ == "__main__":
    main()