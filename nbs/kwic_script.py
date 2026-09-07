import pandas as pd

import string
from collections import Counter
from collections import OrderedDict
import json
from pathlib import Path

"""
script for getting the context for key charcters in RE.
List of relevant characters: 

Resident evil 2:
- Leon S. Kennedy (Protagonist)
- Claire Redfield (Protagonist)
- Shelly Birkin (Story relevant Character)
- William Birkin (Story relevant Character / villain spoiler oops, also called "G" or "Stage 1-4 G" (each number exists)
- Ada Wong (Story relevant Character)
- Tyrant (also called Mr. X, same dude)

Resident evil 3:
- Jill Valentine (protagonist)
- Carlos Oliveira (protagonist)
- Nemesis (villain enemy)
- Nicholai Ginovaef (story related character)
- Brad Vickers (story related character)
- Mikhail Viktor (story related character)

Both:
Robert Kendo
Chris Redfield (just mentioned, but plot driving / relevant)
"""


def remove_punctuation(text: string) -> string:
    """
    make punctuation white space, both the punctuations from the string package, as well as custom punctuations found in debugging
    """
    try:
        punct = f"{string.punctuation}’´"
        # clean_text = text.translate(str.maketrans("", "", f"{string.punctuation}’´"))
        clean_text = text.translate(str.maketrans(punct, " " * len(punct)))
    except AttributeError:
        clean_text = text

    return clean_text


def create_out_paths(game, root_out_path):
    """
    create and out path for hits and misses, and make sure the directories exist
    """
    hits_out_path = root_out_path.joinpath(f"{game}/hits/")
    hits_out_path.mkdir(exist_ok=True, parents=True)

    misses_out_path = root_out_path.joinpath(f"{game}/misses/")
    misses_out_path.mkdir(exist_ok=True, parents=True)

    return hits_out_path, misses_out_path


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df["clean_review"] = df["review"].str.lower()
    df["clean_review"] = df["clean_review"].str.replace("\n", " ")
    df["clean_review"] = df["clean_review"].apply(remove_punctuation)

    return df


def main():
    CHARACTERS = [
        "leon",
        "claire",
        "shelly",
        "william",
        "ada",
        "tyrant",
        "mr",
        "jill",
        "carlos",
        "nemesis",
        "nicholai",
        "brad",
        "mikhail",
        "robert",
        "kendo",
        "chris",
        "redfield",
    ]
    CONTEXT_WINDOW = 5

    DATA_PATH = Path("raw_reviews")
    OUT_PATH = Path("results")

    # load data
    re2 = pd.read_csv(DATA_PATH.joinpath("resident_evil_2_remake.csv"))
    re3 = pd.read_csv(DATA_PATH.joinpath("resident_evil_3_remake.csv"))

    # concatenate data
    re2["game"] = "re2"
    re3["game"] = "re3"

    df = pd.concat([re2, re3])

    # clean reviews
    df = clean_dataframe(df)

    # main loop, for each game, for each character, we want the context window
    for game in ["re2", "re3"]:
        game_df = df.loc[df["game"] == game]

        hits_out_path, misses_out_path = create_out_paths(game, OUT_PATH)

        for name in CHARACTERS:
            name_mentions_df = game_df.loc[
                game_df["clean_review"].str.contains(f"{name}")
            ]

            print("-------------------------")
            print(
                f"[INFO]: total RAW HITS for {name} in {game}: {name_mentions_df.shape[0]}"
            )
            # for saving results
            context_hits = []
            context_misses = []

            # looping over each review where the character is mentioned and getting the context
            for review in list(name_mentions_df["clean_review"]):
                tokenized_review = review.split(" ")
                # remove empty tokens that arise bc of double spaces
                clean_tokenized_review = [
                    token for token in tokenized_review if token != ""
                ]

                # let's get the index for the character of interest
                try:
                    name_index = clean_tokenized_review.index(name)
                except ValueError:
                    # sometimes people write "name's" which turns into "names" - so we check for that as well
                    try:
                        name_index = clean_tokenized_review.index(f"{name}s")
                    except ValueError:
                        # if none of those work, save the review in the misses and make manual evaluation later
                        context_misses.append(review)
                        continue

                # if we did get an index, we want the surrounding context
                if name_index - CONTEXT_WINDOW < 0:
                    context_lower_bound = 0  # sometimes the name is early in the review, in that case we just start from the beginning
                else:
                    context_lower_bound = name_index - CONTEXT_WINDOW
                context_upper_bound = name_index + CONTEXT_WINDOW

                # now we get the full context, turn it into a string, and save it
                name_context_list = clean_tokenized_review[
                    context_lower_bound : context_upper_bound + 1
                ]
                name_context_string = " ".join(name_context_list)

                context_hits.append(name_context_string)

            print(
                f"""[INFO]: total CONTEXT HITS for {name} in {game}: {len(context_hits)}
        total CONTEXT MISSES for {name} in {game}: {len(context_misses)}"""
            )

            # now we count all the different contexts, and save the results as a csv
            name_context_counts = Counter(context_hits)
            name_context_df = pd.DataFrame.from_records(
                name_context_counts.most_common(), columns=["context", "count"]
            )
            name_context_df.to_csv(hits_out_path.joinpath(f"{name}.csv"), index=False)

            # we also save the misses for manual evaluation
            with open(misses_out_path.joinpath(f"{name}.txt"), "w") as f:
                for item in context_misses:
                    f.write(item)
                    f.write("\n")


if __name__ == "__main__":
    main()
