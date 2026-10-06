"""Deduplicate generated tickets and split them 80/10/10 with no near-duplicates across splits.

1. Exact duplicates: same text after normalizing (lowercase, no accents, digits and punctuation
   removed, so tickets that differ only by order number count as the same).
2. Near-duplicates: TF-IDF on character n-grams, cosine similarity. Pairs at or above
   --dup-threshold are duplicates; only the first ticket of each cluster is kept.
3. Grouping: pairs at or above --group-threshold are linked into groups. Whole groups go to one
   split, so no pair across splits reaches the group threshold.
4. Split: StratifiedGroupKFold with 10 folds stratified by category. Fold 0 is test, fold 1 is
   validation, the rest is train.

Usage:
    python scripts/dedup_split.py --stats        # print the similarity distribution only
    python scripts/dedup_split.py                # write data/splits/*.jsonl and data/dedup_report.json
"""

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import StratifiedGroupKFold

RAW = Path("data/raw/generated.jsonl")
SPLITS = Path("data/splits")
REPORT = Path("data/dedup_report.json")
SEED = 42
KEEP_FIELDS = ["id", "ticket", "labels", "language", "style", "product", "scenario", "flag"]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\d+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity_matrix(texts: list[str]) -> np.ndarray:
    vectors = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit_transform(texts)
    sims = cosine_similarity(vectors)
    np.fill_diagonal(sims, 0.0)
    return sims


def connected_groups(sims: np.ndarray, threshold: float) -> list[int]:
    """Union-find over pairs at or above the threshold. Returns a group id per row."""
    parent = list(range(len(sims)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in zip(*np.where(np.triu(sims) >= threshold)):
        parent[find(i)] = find(j)
    return [find(i) for i in range(len(sims))]


def load_rows() -> list[dict]:
    with RAW.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return sorted(rows, key=lambda r: r["id"])


def drop_exact(rows: list[dict]) -> tuple[list[dict], int]:
    seen, kept = set(), []
    for row in rows:
        key = normalize(row["ticket"])
        if key not in seen:
            seen.add(key)
            kept.append(row)
    return kept, len(rows) - len(kept)


def drop_near(rows: list[dict], threshold: float) -> tuple[list[dict], list[dict]]:
    sims = similarity_matrix([normalize(r["ticket"]) for r in rows])
    groups = connected_groups(sims, threshold)
    kept, dropped, seen = [], [], set()
    for row, group in zip(rows, groups):
        if group in seen:
            dropped.append(row)
        else:
            seen.add(group)
            kept.append(row)
    return kept, dropped


def print_stats(rows: list[dict]) -> None:
    sims = similarity_matrix([normalize(r["ticket"]) for r in rows])
    nearest = sims.max(axis=1)
    for q in [0.5, 0.9, 0.99, 0.999]:
        print(f"nearest neighbour similarity, quantile {q}: {np.quantile(nearest, q):.3f}")
    for t in [0.6, 0.7, 0.8, 0.85, 0.9, 0.95]:
        print(f"tickets with a neighbour >= {t}: {(nearest >= t).sum()}")
    i, j = np.unravel_index(np.argmax(sims), sims.shape)
    print(f"most similar pair {sims[i, j]:.3f}:\n  {rows[i]['ticket'][:200]!r}\n  {rows[j]['ticket'][:200]!r}")


def split(rows: list[dict], group_threshold: float) -> dict[str, list[dict]]:
    sims = similarity_matrix([normalize(r["ticket"]) for r in rows])
    groups = connected_groups(sims, group_threshold)
    categories = [r["labels"]["category"] for r in rows]
    folds = StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=SEED)
    fold_of = np.zeros(len(rows), dtype=int)
    for fold, (_, test_index) in enumerate(folds.split(rows, categories, groups)):
        fold_of[test_index] = fold
    names = {0: "test", 1: "validation"}
    out = {"train": [], "validation": [], "test": []}
    for row, fold in zip(rows, fold_of):
        out[names.get(fold, "train")].append({k: row[k] for k in KEEP_FIELDS})
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--dup-threshold", type=float, default=0.85)
    parser.add_argument("--group-threshold", type=float, default=0.7)
    args = parser.parse_args()

    rows = load_rows()
    if args.stats:
        print_stats(rows)
        return

    rows, exact = drop_exact(rows)
    rows, near = drop_near(rows, args.dup_threshold)
    splits = split(rows, args.group_threshold)

    SPLITS.mkdir(parents=True, exist_ok=True)
    for name, items in splits.items():
        with (SPLITS / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    report = {
        "generated": exact + len(near) + len(rows),
        "exact_duplicates_removed": exact,
        "near_duplicates_removed": len(near),
        "near_duplicate_ids_removed": [r["id"] for r in near],
        "kept": len(rows),
        "dup_threshold": args.dup_threshold,
        "group_threshold": args.group_threshold,
        "split_sizes": {name: len(items) for name, items in splits.items()},
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "near_duplicate_ids_removed"}, indent=2))
    for name, items in splits.items():
        print(name, dict(sorted(Counter(i["labels"]["category"] for i in items).items())))


if __name__ == "__main__":
    main()
