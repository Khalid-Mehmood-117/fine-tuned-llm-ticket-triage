import json

from triage.prompts import FINETUNED_SYSTEM_PROMPT, finetuned_messages, target_json
from triage.schema import Action, Category, Triage

LABELS = {
    "reason": "Charged twice for one order.",
    "suggested_action": "start_refund_review",
    "needs_human": True,
    "sentiment": "negative",
    "priority": "high",
    "category": "refund",
}


def test_system_prompt_lists_every_label():
    for member in [*Category, *Action]:
        assert member.value in FINETUNED_SYSTEM_PROMPT


def test_messages_have_system_then_ticket():
    messages = finetuned_messages("My parcel is late.")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[1]["content"] == "My parcel is late."


def test_target_json_has_fixed_key_order_and_validates():
    text = target_json(LABELS)
    assert list(json.loads(text)) == ["category", "priority", "sentiment", "needs_human",
                                      "suggested_action", "reason"]
    assert '"needs_human": true' in text
    Triage.model_validate_json(text)


def test_target_json_keeps_non_ascii():
    assert "é" in target_json({**LABELS, "reason": "Café order was cold."})
