"""Hand check of 50 test labels.

Steps:
    python scripts/hand_check.py sample
        Picks 5 test tickets per category (fixed seed), saves data/hand_check/sample_ids.json and
        writes data/hand_check/blind.jsonl with id, language and ticket only (no labels), so the
        first reviewer labels without seeing the dataset label.

    python scripts/hand_check.py build --first-pass data/hand_check/first_pass.jsonl
        Builds data/hand_check/test_50_review.csv: ticket, dataset label, first pass label,
        first pass note and blank columns for the confirming reviewer.

    python scripts/hand_check.py apply
        Reads the confirmed review file, applies corrections to data/splits/test.jsonl and writes
        data/hand_check/agreement.json with agreement rates per field.

Confirming reviewer, per row:
    confirm      Y if the dataset label is right, N if any field is wrong
    corrections  only when N: the correct values, for example "priority=high; needs_human=true"
    note         optional
"""

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from triage.schema import LABEL_FIELDS, Triage

TEST = Path("data/splits/test.jsonl")
OUT = Path("data/hand_check")
SAMPLE_IDS = OUT / "sample_ids.json"
BLIND = OUT / "blind.jsonl"
REVIEW = OUT / "test_50_review.csv"
AGREEMENT = OUT / "agreement.json"
PER_CATEGORY = 5
SEED = 7


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def sample() -> None:
    rows = load_jsonl(TEST)
    by_category = defaultdict(list)
    for row in rows:
        by_category[row["labels"]["category"]].append(row)
    rng = random.Random(SEED)
    picked = []
    for category in sorted(by_category):
        picked += rng.sample(by_category[category], PER_CATEGORY)
    rng.shuffle(picked)  # so the blind file is not ordered by category
    OUT.mkdir(parents=True, exist_ok=True)
    SAMPLE_IDS.write_text(json.dumps([r["id"] for r in picked], indent=2) + "\n", encoding="utf-8")
    write_jsonl(BLIND, [{"id": r["id"], "language": r["language"], "ticket": r["ticket"]} for r in picked])
    print(f"{len(picked)} tickets written to {BLIND}")


def label_text(labels: dict) -> str:
    return " | ".join(str(labels[f]).lower() for f in LABEL_FIELDS)


def build(first_pass_path: Path) -> None:
    ids = json.loads(SAMPLE_IDS.read_text(encoding="utf-8"))
    test = {r["id"]: r for r in load_jsonl(TEST)}
    first = {r["id"]: r for r in load_jsonl(first_pass_path)}
    columns = ["id", "language", "ticket", "english_gloss", "fields",
               "dataset_label", "first_pass_label", "first_pass_differs", "first_pass_note",
               "confirm", "corrections", "note"]
    with REVIEW.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row_id in ids:
            row, mine = test[row_id], first[row_id]
            Triage.model_validate({**mine["labels"], "reason": "check"})
            differs = [f for f in LABEL_FIELDS if row["labels"][f] != mine["labels"][f]]
            writer.writerow({
                "id": row_id,
                "language": row["language"],
                "ticket": row["ticket"],
                "english_gloss": mine.get("gloss", ""),
                "fields": " | ".join(LABEL_FIELDS),
                "dataset_label": label_text(row["labels"]),
                "first_pass_label": label_text(mine["labels"]),
                "first_pass_differs": ", ".join(differs),
                "first_pass_note": mine.get("note", ""),
                "confirm": "",
                "corrections": "",
                "note": "",
            })
    print(f"review file written to {REVIEW}")


def parse_corrections(text: str) -> dict:
    corrections = {}
    for part in filter(None, (p.strip() for p in text.split(";"))):
        field, value = (s.strip() for s in part.split("=", 1))
        if field not in LABEL_FIELDS:
            raise ValueError(f"unknown field {field!r}")
        corrections[field] = value.lower() == "true" if field == "needs_human" else value
    return corrections


def apply() -> None:
    with REVIEW.open(encoding="utf-8-sig", newline="") as f:
        reviewed = list(csv.DictReader(f))
    missing = [r["id"] for r in reviewed if r["confirm"].strip().upper() not in {"Y", "N"}]
    if missing:
        sys.exit(f"confirm column must be Y or N; missing or invalid for {missing}")

    test = load_jsonl(TEST)
    by_id = {r["id"]: r for r in test}
    field_correct = {f: 0 for f in LABEL_FIELDS}
    first_pass_correct = {f: 0 for f in LABEL_FIELDS}
    changed = []
    for row in reviewed:
        record = by_id[row["id"]]
        corrections = parse_corrections(row["corrections"]) if row["confirm"].strip().upper() == "N" else {}
        final = {**record["labels"], **corrections}
        Triage.model_validate(final)
        first_pass = dict(zip(LABEL_FIELDS, (v.strip() for v in row["first_pass_label"].split("|"))))
        for field in LABEL_FIELDS:
            field_correct[field] += field not in corrections
            first_pass_correct[field] += str(final[field]).lower() == first_pass[field]
        if corrections:
            record["labels"] = final
            record["hand_checked_correction"] = corrections
            changed.append(row["id"])
        record["hand_checked"] = True

    write_jsonl(TEST, test)
    n = len(reviewed)
    result = {
        "rows": n,
        "rows_fully_correct": n - len(changed),
        "row_agreement": round((n - len(changed)) / n, 3),
        "dataset_label_agreement_per_field": {f: round(c / n, 3) for f, c in field_correct.items()},
        "first_pass_agreement_with_final_per_field": {f: round(c / n, 3) for f, c in first_pass_correct.items()},
        "corrected_ids": changed,
    }
    AGREEMENT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["sample", "build", "apply"])
    parser.add_argument("--first-pass", type=Path, default=OUT / "first_pass.jsonl")
    args = parser.parse_args()
    {"sample": sample, "build": lambda: build(args.first_pass), "apply": apply}[args.step]()


if __name__ == "__main__":
    main()
