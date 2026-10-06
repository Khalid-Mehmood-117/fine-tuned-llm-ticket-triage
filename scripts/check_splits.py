"""Check the splits: valid labels, no shared ids or texts, no near-duplicates across splits.

Exits with code 1 if any check fails. Also prints the counts used in the data card.

Usage:
    python scripts/check_splits.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from dedup_split import normalize, similarity_matrix
from triage.schema import Triage

SPLITS = Path("data/splits")
REPORT = Path("data/dedup_report.json")
NAMES = ["train", "validation", "test"]


def load(name: str) -> list[dict]:
    with (SPLITS / f"{name}.jsonl").open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def count_table(splits: dict, key) -> None:
    values = sorted({key(r) for rows in splits.values() for r in rows}, key=str)
    print(f"{'':24}" + "".join(f"{n:>12}" for n in NAMES) + f"{'total':>12}")
    for value in values:
        counts = [sum(1 for r in splits[n] if key(r) == value) for n in NAMES]
        print(f"{str(value):24}" + "".join(f"{c:>12}" for c in counts) + f"{sum(counts):>12}")


def main() -> int:
    splits = {name: load(name) for name in NAMES}
    threshold = json.loads(REPORT.read_text(encoding="utf-8"))["group_threshold"]
    failures = []

    for name, rows in splits.items():
        for row in rows:
            Triage.model_validate(row["labels"])
    print("labels valid against schema: ok")

    ids = Counter(r["id"] for rows in splits.values() for r in rows)
    texts = Counter(normalize(r["ticket"]) for rows in splits.values() for r in rows)
    if any(c > 1 for c in ids.values()):
        failures.append("an id appears more than once")
    if any(c > 1 for c in texts.values()):
        failures.append("a normalized ticket text appears more than once")

    rows = [r for name in NAMES for r in splits[name]]
    split_of = np.array([name for name in NAMES for _ in splits[name]])
    sims = similarity_matrix([normalize(r["ticket"]) for r in rows])
    cross = sims[split_of[:, None] != split_of[None, :]]
    max_cross = float(cross.max())
    print(f"max cross-split similarity {max_cross:.3f} (must be below {threshold})")
    if max_cross >= threshold:
        failures.append(f"cross-split similarity {max_cross:.3f} >= {threshold}")

    print()
    count_table(splits, lambda r: "rows")
    for field in ["category", "priority", "sentiment", "needs_human", "suggested_action"]:
        print(f"\n{field}")
        count_table(splits, lambda r, f=field: r["labels"][f])
    for field in ["language", "style", "product", "flag"]:
        print(f"\n{field}")
        count_table(splits, lambda r, f=field: r[f])

    for failure in failures:
        print("FAIL:", failure)
    print("\nall checks passed" if not failures else "\nchecks failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
