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
import hashlib
import time
from pathlib import Path
import requests
from datetime import datetime
from urllib.parse import quote
from tqdm import tqdm

# Fixed so the same Steam author hashes to the same author_id across every
# game's export, letting cross-game author analysis work without storing
# the real steamid.
AUTHOR_ID_SALT = "resident-evil-reviews-v1"


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


def anonymize_author_id(steamid) -> str:
    if not steamid:
        return ""
    digest = hashlib.sha256(f"{AUTHOR_ID_SALT}:{steamid}".encode("utf-8")).hexdigest()
    return digest[:16]


class AuthorNumberMap:
    """Maps hashed author_id -> a short sequential 'author_000001'-style id,
    persisted to a CSV so the same person gets the same number across every
    game's export (and across resumed/interrupted runs)."""

    FIELDNAMES = ["author_id", "author_number"]

    def __init__(self, path: Path):
        self.path = path
        self.by_author_id = {}
        self.next_n = 1

        if path.exists():
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    n = int(row["author_number"].removeprefix("author_"))
                    self.by_author_id[row["author_id"]] = row["author_number"]
                    self.next_n = max(self.next_n, n + 1)

        self._file = open(path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self.FIELDNAMES)
        if self._file.tell() == 0:
            self._writer.writeheader()

    def get(self, author_id: str) -> str:
        if not author_id:
            return ""
        number = self.by_author_id.get(author_id)
        if number is None:
            number = f"author_{self.next_n:06d}"
            self.next_n += 1
            self.by_author_id[author_id] = number
            self._writer.writerow({"author_id": author_id, "author_number": number})
            self._file.flush()
        return number

    def close(self):
        self._file.close()


def fetch_reviews(
    app_id: int,
    out_csv: str,
    language: str = "all",
    delay: float = 0.25,
    purchase_type: str = "all",
    review_type: str = "all",
    filter_offtopic_activity: int = 0,
    start_cursor: str = "*",
    game_tag: str = None,
):
    tag = game_tag or str(app_id)
    base = f"https://store.steampowered.com/appreviews/{app_id}"
    url = (
        f"{base}?json=1&num_per_page=100&filter=recent&number=0"
        f"&purchase_type={purchase_type}&language={language}"
        f"&filter_offtopic_activity={filter_offtopic_activity}&review_type={review_type}"
        f"&cursor={quote(start_cursor, safe='')}"
    )

    author_map = AuthorNumberMap(Path(out_csv).parent / "author_id_map.csv")

    fieldnames = [
        "review_id",
        "author_id",
        "author_number",
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
    empty_streak = 0
    MAX_EMPTY_STREAK = 5

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
                author_id = anonymize_author_id(a.get("steamid"))
                w.writerow(
                    {
                        "review_id": f"{tag}_{rid}",
                        "author_id": author_id,
                        "author_number": author_map.get(author_id),
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

            if not cursor:
                print(f"\nStopping: no cursor returned (checked={checked}, written={written})")
                break

            if cursor in seen_cursors and num_reviews > 0:
                print(f"\nStopping: repeated cursor with non-empty page, likely an API anomaly (checked={checked}, written={written})")
                break

            if num_reviews == 0:
                empty_streak += 1
                if cursor in seen_cursors or empty_streak >= MAX_EMPTY_STREAK:
                    print(f"\nStopping: {empty_streak} consecutive empty/repeated pages (checked={checked}, written={written})")
                    break
            else:
                empty_streak = 0

            seen_cursors.add(cursor)
            url = (
                f"{base}?json=1&num_per_page=100&filter=recent&number=0"
                f"&purchase_type={purchase_type}&language={language}"
                f"&filter_offtopic_activity={filter_offtopic_activity}&review_type={review_type}"
                f"&cursor={quote(cursor, safe='')}"
            )

            time.sleep(delay if num_reviews else 2)

    if pbar is not None:
        pbar.close()
    author_map.close()

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
    p.add_argument("--game-tag", type=str, default=None, help="Short tag embedded in review_id instead of the app id (e.g. 're2r'). Defaults to the app id.")
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
        game_tag=args.game_tag,
    )
    print(f"Written ({args.language}): {written} | Checked (all): {checked}")


if __name__ == "__main__":
    main()