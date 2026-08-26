"""Generate synthetic logistics interactions and evaluate top-k recommenders."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2026
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
K = 5


def generate_interactions(users: int = 320, items: int = 80, events_per_user: int = 18) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    categories = np.repeat(np.arange(8), items // 8)
    popularity = rng.lognormal(0, 0.7, items)
    rows = []
    for user in range(users):
        preferred = rng.choice(8, size=2, replace=False)
        weights = popularity * np.where(np.isin(categories, preferred), 5.0, 0.35)
        weights = weights / weights.sum()
        selected = rng.choice(items, events_per_user, replace=True, p=weights)
        for step, item in enumerate(selected):
            rows.append((user, int(item), int(categories[item]), step))
    return pd.DataFrame(rows, columns=["user_id", "item_id", "category_id", "event_order"])


def hit_rate(recommendations: dict[int, list[int]], truth: dict[int, int], k: int = K) -> float:
    return float(np.mean([truth[user] in recommendations[user][:k] for user in truth]))


def reciprocal_rank(recommendations: dict[int, list[int]], truth: dict[int, int], k: int = K) -> float:
    scores = []
    for user, target in truth.items():
        ranked = recommendations[user][:k]
        scores.append(1 / (ranked.index(target) + 1) if target in ranked else 0)
    return float(np.mean(scores))


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    interactions = generate_interactions()
    interactions.to_csv(DATA_DIR / "synthetic_interactions.csv", index=False)

    last_index = interactions.groupby("user_id")["event_order"].idxmax()
    test = interactions.loc[last_index]
    train = interactions.drop(last_index)
    truth = dict(zip(test["user_id"], test["item_id"]))
    global_rank = [item for item, _ in Counter(train["item_id"]).most_common()]

    history = train.groupby("user_id")["item_id"].apply(list).to_dict()
    cooccurrence: dict[int, Counter] = defaultdict(Counter)
    for items in history.values():
        unique = set(items)
        for source in unique:
            cooccurrence[source].update(unique - {source})

    popularity_recs = {}
    item_recs = {}
    for user, seen_items in history.items():
        seen = set(seen_items)
        popularity_recs[user] = [item for item in global_rank if item not in seen][:K]
        scores = Counter()
        for source in seen:
            scores.update(cooccurrence[source])
        ranked = [item for item, _ in scores.most_common() if item not in seen]
        ranked.extend(item for item in global_rank if item not in seen and item not in ranked)
        item_recs[user] = ranked[:K]

    metrics = {
        "project_type": "educational synthetic-data demonstration",
        "seed": SEED,
        "interactions": int(len(interactions)),
        "users": int(interactions["user_id"].nunique()),
        "items": int(interactions["item_id"].nunique()),
        "evaluation": "leave-last-interaction-out",
        "k": K,
        "popularity_hit_rate_at_5": hit_rate(popularity_recs, truth),
        "popularity_mrr_at_5": reciprocal_rank(popularity_recs, truth),
        "item_cooccurrence_hit_rate_at_5": hit_rate(item_recs, truth),
        "item_cooccurrence_mrr_at_5": reciprocal_rank(item_recs, truth),
    }
    (OUTPUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    pd.DataFrame(
        [{"user_id": user, "held_out_item": truth[user], "recommendations": "|".join(map(str, item_recs[user]))} for user in sorted(truth)]
    ).to_csv(OUTPUT_DIR / "recommendations.csv", index=False)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
