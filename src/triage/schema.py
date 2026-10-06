"""Output schema shared by every system: fixed label sets and one Pydantic model."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Category(str, Enum):
    billing = "billing"
    refund = "refund"
    shipping = "shipping"
    account_access = "account_access"
    technical_issue = "technical_issue"
    product_question = "product_question"
    cancellation = "cancellation"
    complaint = "complaint"
    feature_request = "feature_request"
    other = "other"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class Sentiment(str, Enum):
    negative = "negative"
    neutral = "neutral"
    positive = "positive"


class Action(str, Enum):
    reply_with_kb_article = "reply_with_kb_article"
    ask_for_details = "ask_for_details"
    route_to_billing = "route_to_billing"
    route_to_technical = "route_to_technical"
    route_to_shipping = "route_to_shipping"
    start_refund_review = "start_refund_review"
    reset_account_access = "reset_account_access"
    process_cancellation = "process_cancellation"
    escalate_to_supervisor = "escalate_to_supervisor"
    escalate_to_safety_legal = "escalate_to_safety_legal"


PRIORITY_ORDER = [Priority.low, Priority.medium, Priority.high, Priority.urgent]
ESCALATION_ACTIONS = {Action.escalate_to_supervisor, Action.escalate_to_safety_legal}
MAX_REASON_WORDS = 25
FIELDS = ["category", "priority", "sentiment", "needs_human", "suggested_action", "reason"]
LABEL_FIELDS = FIELDS[:-1]


class Triage(BaseModel):
    """One triage decision. Extra keys and values outside the label sets are rejected."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    category: Category
    priority: Priority
    sentiment: Sentiment
    needs_human: bool = Field(strict=True)
    suggested_action: Action
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def reason_is_short(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason is empty")
        if len(value.split()) > MAX_REASON_WORDS:
            raise ValueError(f"reason is longer than {MAX_REASON_WORDS} words")
        return value


def raise_priority(current: str, minimum: str) -> str:
    """Return the higher of two priorities."""
    order = [p.value for p in PRIORITY_ORDER]
    return order[max(order.index(current), order.index(minimum))]
