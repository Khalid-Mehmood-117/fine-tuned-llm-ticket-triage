import pytest
from pydantic import ValidationError

from triage.schema import Triage, raise_priority

VALID = {
    "category": "refund",
    "priority": "high",
    "sentiment": "negative",
    "needs_human": True,
    "suggested_action": "start_refund_review",
    "reason": "Customer was charged twice for one order and wants the duplicate back.",
}


def test_valid_output_parses():
    assert Triage.model_validate(VALID).model_dump() == VALID


@pytest.mark.parametrize("field,value", [
    ("category", "refunds"),
    ("priority", "critical"),
    ("sentiment", "angry"),
    ("suggested_action", "refund"),
    ("needs_human", "true"),
    ("needs_human", 1),
])
def test_value_outside_label_set_is_rejected(field, value):
    with pytest.raises(ValidationError):
        Triage.model_validate({**VALID, field: value})


def test_missing_field_is_rejected():
    data = dict(VALID)
    del data["sentiment"]
    with pytest.raises(ValidationError):
        Triage.model_validate(data)


def test_extra_field_is_rejected():
    with pytest.raises(ValidationError):
        Triage.model_validate({**VALID, "confidence": 0.9})


def test_long_reason_is_rejected():
    with pytest.raises(ValidationError):
        Triage.model_validate({**VALID, "reason": "word " * 26})


def test_raise_priority_never_lowers():
    assert raise_priority("low", "high") == "high"
    assert raise_priority("urgent", "high") == "urgent"
