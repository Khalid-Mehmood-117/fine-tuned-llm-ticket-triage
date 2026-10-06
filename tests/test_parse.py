import json

import pytest

from triage.parse import parse_triage

VALID = {
    "category": "shipping", "priority": "medium", "sentiment": "neutral", "needs_human": False,
    "suggested_action": "route_to_shipping", "reason": "Parcel is a week late.",
}


def test_valid_json_parses_with_surrounding_whitespace():
    triage, error = parse_triage("\n " + json.dumps(VALID) + " \n")
    assert error is None
    assert triage == VALID


@pytest.mark.parametrize("text,expected", [
    ("```json\n" + json.dumps(VALID) + "\n```", "not JSON"),
    ("Here you go: " + json.dumps(VALID), "not JSON"),
    (json.dumps(VALID) + " Hope this helps", "not JSON"),
    ("[1, 2]", "not a JSON object"),
    (json.dumps({**VALID, "priority": "critical"}), "schema: priority"),
    (json.dumps({k: v for k, v in VALID.items() if k != "reason"}), "schema: reason"),
    ('{"category": "shipping", "priority": "med', "not JSON"),
])
def test_invalid_outputs_are_rejected_with_reason(text, expected):
    triage, error = parse_triage(text)
    assert triage is None
    assert error.startswith(expected)
