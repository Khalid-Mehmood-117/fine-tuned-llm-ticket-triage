"""Scenario catalog for synthetic ticket generation.

Each scenario fixes the category and suggested action and lists the priorities and sentiments
that fit it. The sampler picks one, so the label is decided before the ticket is written.
Flags mark tickets that must use wording the business rules react to (safety, legal, security,
chargeback) and hard cases (negation: trigger words used to say the danger is absent).
"""

from dataclasses import dataclass, field

PRODUCTS = {
    "tasknest": "TaskNest, a project management web app and mobile app sold as a monthly or yearly team subscription",
    "threadline": "Threadline, an online fashion store selling clothes and shoes with home delivery",
    "zephyr": "Zephyr Mobile, a mobile phone carrier selling SIM plans, phones and home internet",
    "kestrel": "Kestrel Bank, a mobile banking app with cards, transfers and bill payments",
    "glowhome": "Glowhome, a smart home brand selling smart plugs, thermostats, cameras, space heaters and a companion app",
    "dashbite": "Dashbite, a food delivery app that delivers restaurant meals and groceries",
}
ALL = list(PRODUCTS)
PHYSICAL = ["threadline", "zephyr", "glowhome", "dashbite"]
SUBSCRIPTION = ["tasknest", "zephyr", "glowhome", "dashbite"]

PROBLEM = {"negative": 0.75, "neutral": 0.25}
QUESTION = {"neutral": 0.7, "positive": 0.2, "negative": 0.1}
WARM = {"positive": 0.8, "neutral": 0.2}
ANGRY = {"negative": 1.0}


@dataclass
class Scenario:
    id: str
    category: str
    action: str
    situation: str
    priorities: list[str]
    sentiments: dict = field(default_factory=lambda: PROBLEM)
    products: list[str] = field(default_factory=lambda: ALL)
    flag: str | None = None
    needs_human: bool | None = None  # None means derive from the label definitions


SCENARIOS = [
    # billing
    Scenario("bill_double", "billing", "route_to_billing", "was charged twice for the same bill or order", ["medium", "high"], products=ALL),
    Scenario("bill_promo_end", "billing", "route_to_billing", "the price went up unexpectedly, probably because a promotion ended, and wants it checked", ["low", "medium"], products=SUBSCRIPTION),
    Scenario("bill_invoice", "billing", "reply_with_kb_article", "needs a copy of an invoice or receipt with company or tax details", ["low"], QUESTION),
    Scenario("bill_card_declined", "billing", "route_to_billing", "cannot update the payment card, it keeps being declined although the card works elsewhere", ["medium"]),
    Scenario("bill_fraud", "billing", "route_to_billing", "sees a charge they never made and suspects fraud or an unauthorized charge", ["high"], flag="security"),
    Scenario("bill_after_cancel", "billing", "route_to_billing", "was charged again after already cancelling", ["medium", "high"], products=SUBSCRIPTION),
    Scenario("bill_cycle_question", "billing", "reply_with_kb_article", "asks how the billing cycle or proration works when changing plans", ["low"], QUESTION, products=SUBSCRIPTION),
    # refund
    Scenario("ref_damaged", "refund", "start_refund_review", "an item arrived broken or defective and they want their money back, not a replacement", ["medium"], products=PHYSICAL),
    Scenario("ref_wrong_item", "refund", "start_refund_review", "received the wrong item and wants a refund", ["medium"], products=["threadline", "zephyr", "glowhome"]),
    Scenario("ref_outage_credit", "refund", "start_refund_review", "lost service for days because of an outage and wants a partial refund or credit", ["medium"], products=["tasknest", "zephyr"]),
    Scenario("ref_never_received", "refund", "escalate_to_supervisor", "was promised a refund weeks ago, has contacted support several times and still has not received it", ["high"], ANGRY),
    Scenario("ref_policy", "refund", "reply_with_kb_article", "asks about the refund policy or how long a refund takes", ["low"], QUESTION),
    Scenario("ref_missing_food", "refund", "start_refund_review", "food order arrived with items missing and wants money back for them", ["medium"], products=["dashbite"]),
    Scenario("ref_chargeback", "refund", "start_refund_review", "wants a refund and says they will file a chargeback with their bank if it is not done", ["high"], ANGRY, flag="chargeback"),
    # shipping
    Scenario("ship_delayed", "shipping", "route_to_shipping", "the parcel is late, past the estimated delivery date", ["medium"], products=["threadline", "zephyr", "glowhome"]),
    Scenario("ship_delivered_missing", "shipping", "route_to_shipping", "tracking says delivered but the parcel never arrived", ["medium", "high"], products=["threadline", "zephyr", "glowhome"]),
    Scenario("ship_change_address", "shipping", "route_to_shipping", "needs to change the delivery address before the order ships", ["medium"], QUESTION, products=["threadline", "zephyr", "glowhome"]),
    Scenario("ship_status", "shipping", "reply_with_kb_article", "simply asks where the order is or how to track it", ["low"], QUESTION, products=["threadline", "zephyr", "glowhome"]),
    Scenario("ship_event_deadline", "shipping", "route_to_shipping", "needs the order for an event within two days and it has not shipped yet", ["high"], products=["threadline", "glowhome", "zephyr"]),
    Scenario("ship_driver_late", "shipping", "route_to_shipping", "the delivery driver is very late or lost and the food has not arrived", ["medium"], products=["dashbite"]),
    # account_access
    Scenario("acc_reset_email", "account_access", "reset_account_access", "forgot the password and the reset email never arrives", ["medium"]),
    Scenario("acc_locked_work", "account_access", "reset_account_access", "account locked after failed logins and needs access today for work or a payment", ["high"]),
    Scenario("acc_lost_2fa", "account_access", "reset_account_access", "lost or replaced the phone that had the two factor codes", ["high", "medium"]),
    Scenario("acc_hacked", "account_access", "reset_account_access", "the account was hacked, the email or password was changed by someone else", ["high"], flag="security"),
    Scenario("acc_change_email", "account_access", "reply_with_kb_article", "asks how to change the login email or username", ["low"], QUESTION),
    Scenario("acc_bank_blocked", "account_access", "reset_account_access", "is locked out of the banking app and cannot pay rent or a bill due today", ["urgent"], ANGRY, products=["kestrel"]),
    # technical_issue
    Scenario("tech_crash", "technical_issue", "route_to_technical", "the app crashes on startup since the last update", ["medium", "high"], products=["tasknest", "kestrel", "glowhome", "dashbite", "zephyr"]),
    Scenario("tech_error_msg", "technical_issue", "route_to_technical", "a specific feature shows an error message when used", ["medium"]),
    Scenario("tech_outage", "technical_issue", "route_to_technical", "the whole service is down and their team cannot work", ["high"], products=["tasknest"]),
    Scenario("tech_wifi", "technical_issue", "reply_with_kb_article", "a smart device will not connect to the home wifi during setup", ["low", "medium"], products=["glowhome"]),
    Scenario("tech_sync", "technical_issue", "route_to_technical", "data is missing or not syncing between devices", ["medium"], products=["tasknest", "glowhome", "kestrel"]),
    Scenario("tech_overheat", "technical_issue", "escalate_to_safety_legal", "a device overheated, smoked, sparked or burned something or someone", ["urgent"], {"negative": 1.0}, products=["glowhome", "zephyr"], flag="safety"),
    Scenario("tech_no_signal", "technical_issue", "route_to_technical", "no mobile signal or mobile data at home for several days", ["medium", "high"], products=["zephyr"]),
    Scenario("tech_vague", "technical_issue", "ask_for_details", "says something does not work but gives no detail about what, where or which product", ["low", "medium"]),
    Scenario("tech_negation", "technical_issue", "route_to_technical", "a device makes a strange noise or flickers; they say clearly there is no smoke, no burning smell and nothing overheating, it is just annoying", ["low", "medium"], {"neutral": 0.6, "negative": 0.4}, products=["glowhome", "zephyr"], flag="negation"),
    # product_question
    Scenario("pq_compat", "product_question", "reply_with_kb_article", "asks if a product works with something they already own before buying", ["low"], QUESTION, products=["glowhome", "zephyr", "tasknest"]),
    Scenario("pq_howto", "product_question", "reply_with_kb_article", "asks how to use a specific feature", ["low"], QUESTION),
    Scenario("pq_size", "product_question", "reply_with_kb_article", "asks about sizing, fit or materials", ["low"], QUESTION, products=["threadline"]),
    Scenario("pq_plan", "product_question", "reply_with_kb_article", "asks which plan or option fits their needs", ["low"], QUESTION, products=["tasknest", "zephyr", "kestrel"]),
    Scenario("pq_allergen", "product_question", "reply_with_kb_article", "asks whether a dish contains nuts or gluten before ordering", ["low"], QUESTION, products=["dashbite"]),
    Scenario("pq_unclear", "product_question", "ask_for_details", "asks a question but does not say which product or what exactly they mean", ["low"], QUESTION),
    # cancellation
    Scenario("can_subscription", "cancellation", "process_cancellation", "wants to cancel the subscription or plan", ["medium"], {"neutral": 0.6, "negative": 0.3, "positive": 0.1}, products=SUBSCRIPTION),
    Scenario("can_order", "cancellation", "process_cancellation", "wants to cancel an order that has not shipped yet", ["medium", "high"], {"neutral": 0.6, "negative": 0.4}, products=["threadline", "glowhome", "zephyr", "dashbite"]),
    Scenario("can_moving", "cancellation", "process_cancellation", "is moving abroad, wants to cancel and asks about early termination fees", ["medium"], QUESTION, products=["zephyr", "kestrel", "tasknest"]),
    Scenario("can_repeat_fail", "cancellation", "escalate_to_supervisor", "tried to cancel several times, is still being charged and threatens to leave a public review", ["high"], ANGRY, products=SUBSCRIPTION),
    Scenario("can_howto", "cancellation", "reply_with_kb_article", "only asks how to cancel, has not decided yet", ["low"], QUESTION, products=SUBSCRIPTION),
    # complaint
    Scenario("comp_rude_agent", "complaint", "escalate_to_supervisor", "a support agent or driver was rude to them", ["medium"], ANGRY),
    Scenario("comp_policy", "complaint", "reply_with_kb_article", "is unhappy about a policy or fee change and wants to vent", ["low", "medium"]),
    Scenario("comp_compensation", "complaint", "escalate_to_supervisor", "has had repeated problems, demands compensation and threatens to switch to a competitor", ["high"], ANGRY),
    Scenario("comp_cold_food", "complaint", "escalate_to_supervisor", "food arrived cold and late again and they want a voucher", ["medium"], products=["dashbite"]),
    Scenario("comp_legal", "complaint", "escalate_to_safety_legal", "is so unhappy with how they were treated that they threaten legal action or a lawyer", ["urgent"], ANGRY, flag="legal"),
    Scenario("comp_allergy", "complaint", "escalate_to_safety_legal", "had an allergic reaction or got sick after eating an order that was supposed to be allergen free", ["urgent"], {"negative": 1.0}, products=["dashbite"], flag="safety"),
    # feature_request
    Scenario("feat_simple", "feature_request", "reply_with_kb_article", "suggests a new feature such as dark mode, an export option or a widget", ["low"], {"neutral": 0.5, "positive": 0.4, "negative": 0.1}, products=["tasknest", "kestrel", "glowhome", "dashbite"]),
    Scenario("feat_must_have", "feature_request", "reply_with_kb_article", "asks for an integration and says the team may switch tools without it", ["medium"], {"neutral": 0.6, "negative": 0.4}, products=["tasknest"]),
    Scenario("feat_praise", "feature_request", "reply_with_kb_article", "loves the product and enthusiastically suggests an improvement", ["low"], WARM),
    # other
    Scenario("oth_thanks", "other", "reply_with_kb_article", "just writes to say thank you for good service", ["low"], WARM),
    Scenario("oth_wrong_company", "other", "reply_with_kb_article", "clearly writes to the wrong company about a product this company does not sell", ["low"], QUESTION),
    Scenario("oth_partnership", "other", "reply_with_kb_article", "sends a partnership, advertising or job inquiry", ["low"], {"neutral": 0.6, "positive": 0.4}),
    Scenario("oth_gdpr", "other", "escalate_to_safety_legal", "formally requests deletion of all their personal data under data protection law such as GDPR", ["urgent"], {"neutral": 0.7, "negative": 0.3}, flag="legal"),
    Scenario("oth_hello", "other", "ask_for_details", "writes only a greeting or 'help' or 'are you there' with no actual issue", ["low"], {"neutral": 0.8, "negative": 0.2}),
]

FLAG_WORDING = {
    "safety": "Describe the physical danger plainly (for example smoke, fire, burn, sparks, overheating, injury or an allergic reaction).",
    "legal": "State the legal angle plainly (for example a lawyer, legal action, court, or a formal data deletion request under data protection law).",
    "security": "Say plainly that it looks like fraud, hacking or an unauthorized charge or login.",
    "chargeback": "Say plainly that they will file a chargeback or dispute the charge with their bank.",
    "negation": "Explicitly say that there is no smoke, no burning smell and no overheating.",
}

STYLES = {
    "formal": "Polite and formal, complete sentences, greeting and sign-off.",
    "casual": "Casual and friendly, like a quick message to a friend.",
    "angry": "Angry and frustrated, some capital letters or exclamation marks, no insults.",
    "very_short": "Very short, under 12 words, no greeting.",
    "rambling": "Long and rambling, with background detail before getting to the point.",
    "typos": "Typed fast: typos, little punctuation, lowercase.",
    "multi_issue": "Mentions two issues in one ticket. The main issue below is the most important; also mention a second, minor issue briefly.",
    "forwarded": "Pasted as an email with a subject line, a signature block and a short quoted earlier message.",
    "phone": "Written on a phone: short lines, an abbreviation or two, maybe an emoji.",
}

LANGUAGES = {
    "en": ("English", 0.85),
    "es": ("Spanish", 0.03),
    "fr": ("French", 0.03),
    "de": ("German", 0.03),
    "pt": ("Brazilian Portuguese", 0.03),
    "ur": ("Roman Urdu (Urdu written in Latin letters, mixed with some English words, as people in Pakistan text)", 0.03),
}

MINOR_ISSUES = [
    "also asks how to update their phone number on the account",
    "also mentions the app feels slow lately",
    "also asks whether there is a student discount",
    "also asks how to download past invoices",
    "also says the confirmation email went to spam",
    "also asks if they can add a second user",
    "also asks about opening hours of support",
]

PRIORITY_CUES = {
    "low": "No time pressure; it is a question, feedback or minor issue.",
    "medium": "A real inconvenience that needs action, but they are not fully blocked and there is no hard deadline.",
    "high": "Make clear it blocks them or costs them money now, or there is a deadline within 48 hours, or they are escalating after repeated contacts.",
    "urgent": "Make clear there is risk to safety or health, a legal threat, or they are fully blocked from money or an essential service right now.",
}
