# Resident Evil Steam Reviews

Analyzing Steam reviews of Resident Evil 2 Remake and Resident Evil 3 Remake (topic modeling, character mentions, and cross-game references) to see what players actually talk about and how it differs between the two games.

## What's in this repo

```
resident_evil_steam_games.csv   List of Resident Evil games, their Steam App IDs, and release info
                                 (used to decide which games to scrape reviews for)

scripts/
  steam_reviews.py               Downloads reviews for ONE game from Steam's review API
  run_all_reviews.py             Runs steam_reviews.py for every game listed in the CSV above
  kwic_script.py                 Finds mentions of specific characters (Leon, Jill, Nemesis, etc.)
                                  and saves the surrounding text for each mention

raw_reviews/
  resident_evil_2_remake.csv     Downloaded reviews for RE2 Remake
  resident_evil_3_remake.csv     Downloaded reviews for RE3 Remake

nbs/
  ResidentEvil_Turftopic.ipynb   Fits the topic model, labels topics,
                                  builds every chart, and verifies the numbers used in the write-up
  review_quality_checks.ipynb    Pass on the raw review CSVs (row counts, missing values,
                                  duplicates, per-file and cross-file comparisons)

results/                         Everything the notebook and scripts produce
  topic_labels.csv               The 30 topics (name, description, and top keywords for each)
  reviews_with_topic_scores.csv  Every review, with its score on each of the 30 topics attached
  vizualizations/                All figures
  re2/, re3/                     Output of kwic_script.py for each character, a hits/ CSV of
                                  their mention contexts and a misses/ list for manual review
```

## Data and time boundaries

### Collection / snapshot
- **Source:** Steam's public review endpoint (`store.steampowered.com/appreviews/<appid>`), paged with `filter=recent` until no further cursor is returned, via `scripts/run_all_reviews.py` (exact command in that script's docstring).
- **Games:** RE2 Remake (App ID 883710, released 25 Jan 2019) and RE3 Remake (App ID 952060, released 3 Apr 2020).
- **Snapshot date:** reviews were collected on **2 September 2026**, so that is the latest review date in both files. Each file is a snapshot of how the reviews looked that day. Reviews deleted or hidden before then are missing. For reviews edited before then, only the latest text and thumbs-up/down are stored.
- **Time window:** everything from each game's launch day up to the snapshot:
  - RE2R: 25 Jan 2019 – 2 Sep 2026 (~7 years 7 months)
  - RE3R: 3 Apr 2020 – 2 Sep 2026 (~6 years 5 months)

### What the 124,775 reviews are
| Filter | Setting used | Meaning |
|---|---|---|
| Language | `english` | Only reviews whose author marked them as English on Steam (Steam's language label, not automatic detection). The reviews do contain some non-English text. |
| Review type | `all` | Both positive and negative reviews |
| Purchase type | `all` | Steam purchases **and** keys bought elsewhere (about 72% are Steam purchases) |
| Off-topic activity | `filter_offtopic_activity=0` | **Review-bomb periods are included.** Steam's default would hide them. |
| Received for free | kept | About 2% of reviews in each game |

| | Downloaded | Empty review text (dropped) | Analysed |
|---|---:|---:|---:|
| RE2R | 80,416 | 298 | 80,118 |
| RE3R | 44,799 | 142 | 44,657 |
| **Total** | 125,215 | 440 | **124,775** |

Rows with empty text are dropped in `ResidentEvil_Turftopic.ipynb` (`dropna` on `review`). Nothing else is filtered: there is no cutoff on length, playtime or language detection. About 31% of RE2R reviews and 23% of RE3R reviews are 20 characters or shorter (e.g. "scary", "10/10").

### Duplicates, edited, off-topic and review-bombed reviews
- **Same person reviewing the same game twice:** not possible on Steam (one review per account per game). The data confirms this: each game has 0 duplicate `author_number`s.
- **Reviewers of both games:** 19,060 accounts reviewed both games. They are kept in both corpora, so the two games' reviews are **not independent samples**. These pairs are analysed on purpose in the "sentiment flip" chart. Authors appear only as salted SHA-256 hashes (`author_id`) and sequential `author_number`s, never as Steam IDs.
- **Identical review text:** many short reviews share the same text (13,102 repeated texts in RE2R, 4,749 in RE3R, e.g. "good game"). These are different authors and are kept.
- **Edited reviews:** 7.9% of RE2R and 9.1% of RE3R reviews have `date_updated` ≠ `date_created`. The text and sentiment are the **latest edit**, but every time-based chart uses `date_created`. So a review written at launch and edited years later counts at launch with its later text.
- **Off-topic / review-bombed reviews:** included and not flagged (see `filter_offtopic_activity=0` above). There was no manual or automatic removal of off-topic or joke reviews.

### Topic weights: normalization and corpus imbalance
- **One pooled model:** a single KeyNMF model (K=30, `paraphrase-mpnet-base-v2` embeddings, `top_n=25` keywords per review) is fitted on both games together. RE2R makes up 64% of the documents, so it has more influence on which topics are found, though likely not to a large extent. This imbalance was deliberately left in. The corpus is the full set of English reviews, not a sample, so the imbalance is real. Downsampling RE2R would throw away data, and separate models per game would give topics that can't be compared across the games.
- **Per-game prevalence** is the **mean weight per review** within each game. Each game's average is therefore not inflated by having more reviews. For the topic-group shares (e.g. "fear topics = 13.3% vs 4.9%"), each game's group weight is divided by that game's total topic weight.
- **Not normalized for review length.** A review's topic weights do **not** add up to 1, and they grow with length. The average total weight is 0.014 for the shortest fifth of reviews (≤13 characters) and 0.24 for the longest fifth (>279 characters). RE3R reviews are longer on average (median 85 vs 48 characters), so RE3R's raw average weights are somewhat higher overall. However, weights were deliberately left unnormalized. Rescaling each review to sum to 1 would make very short reviews (e.g. "scary") count as fully about one topic. Review length is also partly a real difference between the games, since longer reviews tend to be complaints. As such, differences *within* a game (between topics) are more reliable than raw differences *between* the games. 