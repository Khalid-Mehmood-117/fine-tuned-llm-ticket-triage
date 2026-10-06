"""Strict parsing of model output into a Triage decision.

The whole output (ignoring surrounding whitespace) must be one JSON object that passes the
Triage schema. Markdown fences, extra text, missing keys or labels outside the sets are invalid.
"""

import json

from pydantic import ValidationError

from triage.schema import Triage


def parse_triage(text: str) -> tuple[dict | None, str | None]:
    """Return (triage dict, None) when valid, or (None, short error) when not."""
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError as error:
        return None, f"not JSON: {error.msg}"
    if not isinstance(data, dict):
        return None, "not a JSON object"
    try:
        return Triage.model_validate(data).model_dump(), None
    except ValidationError as error:
        first = error.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "object"
        return None, f"schema: {field}: {first['msg']}"
