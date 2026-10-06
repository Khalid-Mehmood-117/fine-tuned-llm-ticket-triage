"""Prompts and target format for the fine-tuned model.

Training (notebooks/train.ipynb) and local inference import these same functions, so the model
always sees exactly the prompt it was trained on. The longer prompt with label definitions and
examples for the base model and gpt-4o-mini is added in M3.
"""

import json

from triage.schema import FIELDS, Action, Category, Priority, Sentiment


def _values(enum) -> str:
    return ", ".join(member.value for member in enum)


FINETUNED_SYSTEM_PROMPT = f"""You triage customer support tickets. Reply with one JSON object and nothing else.
Keys, in this order:
category: one of {_values(Category)}
priority: one of {_values(Priority)}
sentiment: one of {_values(Sentiment)}
needs_human: true or false
suggested_action: one of {_values(Action)}
reason: one English sentence, at most 25 words"""


def finetuned_messages(ticket: str) -> list[dict]:
    """Chat messages for one ticket, without the answer."""
    return [
        {"role": "system", "content": FINETUNED_SYSTEM_PROMPT},
        {"role": "user", "content": ticket},
    ]


def target_json(labels: dict) -> str:
    """The exact assistant answer the model is trained to produce: compact JSON, fixed key order."""
    return json.dumps({field: labels[field] for field in FIELDS}, ensure_ascii=False)
