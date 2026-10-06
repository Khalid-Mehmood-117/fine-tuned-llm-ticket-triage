"""Generate synthetic support tickets with gpt-4o-mini.

The label comes first: a seeded sampler picks a scenario (category and action), a priority, a
sentiment, a product, a writing style and a language. gpt-4o-mini then writes a ticket that fits
that spec plus a one sentence reason. The label is the sampled spec, never a model guess.

Usage:
    python scripts/generate_data.py --n 30 --out data/raw/pilot.jsonl
    python scripts/generate_data.py --n 1700 --out data/raw/generated.jsonl

Re-running with the same --out resumes: tickets already in the file are skipped.
"""

import argparse
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from scenarios import (FLAG_WORDING, LANGUAGES, MINOR_ISSUES, PRIORITY_CUES, PRODUCTS,
                       SCENARIOS, STYLES)
from triage.schema import Triage

MODEL = "gpt-4o-mini"
# USD per 1M tokens, gpt-4o-mini list price. Checked again before M3.
PRICE_INPUT = 0.15
PRICE_OUTPUT = 0.60
SEED = 42

FIRST_NAMES = ["Aisha", "Ben", "Carlos", "Chloe", "Daniel", "Elena", "Fatima", "Grace", "Hassan",
               "Ines", "James", "Kenji", "Laura", "Mateo", "Mei", "Noah", "Olu", "Priya", "Rafael",
               "Sara", "Tom", "Usman", "Valeria", "Wei", "Yusuf", "Zoe", "Ayesha", "Bilal", "Hina",
               "Jonas", "Lea", "Lucas", "Ana", "Pierre", "Camille", "Felix"]

SYSTEM_PROMPT = """You write realistic customer support tickets for a synthetic training dataset.
Write exactly one ticket from the customer to the company's support team, following the spec.
Never mention labels, priorities, categories or the words "ticket" or "spec". Invent realistic
details (order numbers, dates, device names, amounts) when they help. Vary wording; do not start
with "I hope this message finds you well".

Also write a reason: one English sentence of at most 20 words, written for a support lead, that
names the concrete problem in this ticket and the key fact behind the urgency or routing. Do not
write phrases like "fits the category" or repeat label names.

Reply with JSON only: {"ticket": "...", "reason": "..."}"""


def needs_human_for(scenario, priority: str) -> bool:
    """needs_human follows labels.md: judgment or authority needed."""
    if scenario.needs_human is not None:
        return scenario.needs_human
    if scenario.action in {"start_refund_review", "escalate_to_supervisor", "escalate_to_safety_legal"}:
        return True
    if priority == "urgent":
        return True
    return scenario.flag in {"safety", "legal", "security", "chargeback"}


def pick(rng: random.Random, weights: dict) -> str:
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def sample_spec(rng: random.Random, index: int) -> dict:
    categories = sorted({s.category for s in SCENARIOS})
    category = rng.choice(categories)
    scenario = rng.choice([s for s in SCENARIOS if s.category == category])
    priority = rng.choice(scenario.priorities)
    sentiment = pick(rng, scenario.sentiments)
    styles = [s for s in STYLES if sentiment == "negative" or s != "angry"]
    style = rng.choice(styles)
    language = pick(rng, {code: weight for code, (_, weight) in LANGUAGES.items()})
    return {
        "id": f"t{index:05d}",
        "scenario": scenario.id,
        "flag": scenario.flag,
        "product": rng.choice(scenario.products),
        "style": style,
        "language": language,
        "customer_name": rng.choice(FIRST_NAMES),
        "minor_issue": rng.choice(MINOR_ISSUES) if style == "multi_issue" else None,
        "reference": reference(rng),
        "labels": {
            "category": scenario.category,
            "priority": priority,
            "sentiment": sentiment,
            "needs_human": needs_human_for(scenario, priority),
            "suggested_action": scenario.action,
        },
    }


def reference(rng: random.Random) -> str:
    """A varied order or account reference so tickets do not all say #123456."""
    digits = "".join(rng.choice("0123456789") for _ in range(rng.choice([5, 6, 7, 8])))
    return rng.choice(["#", "ORD-", "", "A", "No. "]) + digits


def build_prompt(spec: dict) -> str:
    scenario = next(s for s in SCENARIOS if s.id == spec["scenario"])
    labels = spec["labels"]
    lines = [
        f"Company: {PRODUCTS[spec['product']]}",
        f"Customer first name (use it or not, as fits the style): {spec['customer_name']}",
        f"Order or account reference, if one fits: {spec['reference']}. Today is in September 2026.",
        f"Situation: the customer {scenario.situation}.",
        f"Urgency: {PRIORITY_CUES[labels['priority']]}",
        f"Tone: {labels['sentiment']}.",
        f"Style: {STYLES[spec['style']]}",
        f"Language of the ticket: {LANGUAGES[spec['language']][0]}.",
    ]
    if spec["minor_issue"]:
        lines.append(f"Second minor issue: the customer {spec['minor_issue']}.")
    if spec["flag"]:
        lines.append(f"Wording: {FLAG_WORDING[spec['flag']]}")
    if not spec["flag"]:
        lines.append("Do not mention injury, fire, smoke, lawyers, legal action, fraud, hacking or chargebacks.")
    lines.append(
        "Labels the reason must justify: "
        + ", ".join(f"{k}={v}" for k, v in labels.items())
    )
    return "\n".join(lines)


def generate_one(client: OpenAI, spec: dict, attempts: int = 3) -> dict:
    prompt = build_prompt(spec)
    usage = {"input_tokens": 0, "output_tokens": 0}
    last_error = None
    for attempt in range(attempts):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                temperature=1.0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": prompt}],
            )
            usage["input_tokens"] += response.usage.prompt_tokens
            usage["output_tokens"] += response.usage.completion_tokens
            data = json.loads(response.choices[0].message.content)
            ticket = data["ticket"].strip()
            labels = Triage.model_validate({**spec["labels"], "reason": data["reason"]}).model_dump()
            if not ticket:
                raise ValueError("empty ticket")
            return {**spec, "ticket": ticket, "labels": labels, "usage": usage}
        except (KeyError, ValueError, ValidationError, json.JSONDecodeError) as error:
            last_error = error
        except Exception as error:  # network or rate limit: back off and retry
            last_error = error
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{spec['id']} failed after {attempts} attempts: {last_error}")


def load_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        return {json.loads(line)["id"] for line in f if line.strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()

    load_dotenv()
    client = OpenAI()
    rng = random.Random(SEED)
    specs = [sample_spec(rng, i) for i in range(1, args.n + 1)]
    done = load_done(args.out)
    todo = [s for s in specs if s["id"] not in done]
    print(f"{len(done)} already generated, {len(todo)} to go")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    totals = {"input_tokens": 0, "output_tokens": 0, "failed": 0}
    with args.out.open("a", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(generate_one, client, spec) for spec in todo]
        for count, future in enumerate(as_completed(futures), start=1):
            try:
                record = future.result()
            except RuntimeError as error:
                totals["failed"] += 1
                print(error, file=sys.stderr)
                continue
            with lock:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                totals["input_tokens"] += record["usage"]["input_tokens"]
                totals["output_tokens"] += record["usage"]["output_tokens"]
            if count % 100 == 0:
                print(f"{count}/{len(todo)} done")

    cost = (totals["input_tokens"] * PRICE_INPUT + totals["output_tokens"] * PRICE_OUTPUT) / 1e6
    print(f"input tokens {totals['input_tokens']}, output tokens {totals['output_tokens']}, "
          f"failed {totals['failed']}, estimated cost ${cost:.4f}")


if __name__ == "__main__":
    main()
