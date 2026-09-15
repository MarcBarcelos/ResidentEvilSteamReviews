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
