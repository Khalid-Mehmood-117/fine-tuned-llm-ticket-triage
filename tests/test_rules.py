import pytest

from triage.rules import apply_rules

BASE = {
    "category": "technical_issue",
    "priority": "low",
    "sentiment": "neutral",
    "needs_human": False,
    "suggested_action": "reply_with_kb_article",
    "reason": "Placeholder reason.",
}


def fired(ticket, triage=None):
    output, hits = apply_rules(ticket, triage or BASE)
    return output, [h.rule for h in hits]


@pytest.mark.parametrize("ticket", [
    "My charger started smoking last night and the cable melted.",
    "The heater overheated and my son got a burn on his hand.",
    "El cargador se quemó y salió humo.",
    "Le chargeur a pris feu dans la cuisine.",
    "Das Gerät ist überhitzt und hat einen Stromschlag gegeben.",
    "O carregador pegou fogo ontem.",
    "charger se dhuan nikal raha tha aur aag lag gayi",
    "My daughter had an allergic reaction to the food you delivered.",
    "We both got really sick after the curry and my husband needed medical attention.",
    "My throat is swelling after eating the salad you said was nut free.",
])
def test_safety_forces_urgent_escalation(ticket):
    output, rules = fired(ticket)
    assert "R1_SAFETY" in rules
    assert output["priority"] == "urgent"
    assert output["needs_human"] is True
    assert output["suggested_action"] == "escalate_to_safety_legal"


@pytest.mark.parametrize("ticket", [
    "If this is not fixed my lawyer will be in touch.",
    "I will take legal action against your company.",
    "Under GDPR I request that you delete my personal data.",
    "Voy a hablar con mi abogado.",
    "Je vais contacter un avocat.",
    "Ich werde Sie verklagen.",
    "Vou processar a empresa e falar com o Procon.",
    "main wakeel se baat karunga",
    "Fix this or I will seek legal advice.",
    "Please erase my personal data from all your systems.",
    "Quero a exclusão de todos os meus dados.",
    "Bitte meine Daten löschen, alle.",
])
def test_legal_forces_urgent_escalation(ticket):
    output, rules = fired(ticket)
    assert "R2_LEGAL" in rules
    assert output["priority"] == "urgent"
    assert output["suggested_action"] == "escalate_to_safety_legal"


@pytest.mark.parametrize("ticket", [
    "My account was hacked and the email was changed.",
    "There are unauthorized charges on my card from your app.",
    "Hay cargos no autorizados en mi tarjeta.",
    "Mein Konto wurde gehackt.",
])
def test_security_raises_to_high_and_needs_human(ticket):
    output, rules = fired(ticket)
    assert "R3_SECURITY" in rules
    assert output["priority"] == "high"
    assert output["needs_human"] is True
    assert output["suggested_action"] == BASE["suggested_action"]


@pytest.mark.parametrize("ticket", [
    "Refund me today or I file a chargeback.",
    "If I do not hear back I am disputing the charge.",
])
def test_chargeback_raises_to_high(ticket):
    output, rules = fired(ticket)
    assert "R4_CHARGEBACK" in rules
    assert output["priority"] == "high"
    assert output["needs_human"] is True


def test_rules_never_lower_priority():
    output, _ = fired("Someone hacked my account.", {**BASE, "priority": "urgent"})
    assert output["priority"] == "urgent"


def test_escalation_action_forces_needs_human():
    output, rules = fired("I want to speak to a manager.",
                          {**BASE, "suggested_action": "escalate_to_supervisor"})
    assert rules == ["R5_ESCALATION_CONSISTENCY"]
    assert output["needs_human"] is True


def test_hit_records_what_changed():
    _, hits = apply_rules("The battery caught fire.", BASE)
    assert hits[0].to_dict() == {
        "rule": "R1_SAFETY",
        "matched": "caught fire",
        "changes": {
            "needs_human": [False, True],
            "priority": ["low", "urgent"],
            "suggested_action": ["reply_with_kb_article", "escalate_to_safety_legal"],
        },
    }


def test_input_is_not_mutated():
    original = dict(BASE)
    apply_rules("It caught fire.", original)
    assert original == BASE


@pytest.mark.parametrize("ticket", [
    "I was shocked by the price increase this month.",
    "Can I get the brand new model in blue?",
    "Das Gericht war kalt, als es ankam.",
    "Bless you all, the support was great.",
    "Your app keeps crashing when I open settings.",
    "Thanks, Sue from accounting",
    "Of course I paid, here is the receipt.",
    "The firewall settings page will not load.",
    "Quem pode me ajudar com a fatura?",
    "I am sick of waiting for my parcel.",
    "Can I delete my saved address?",
])
def test_ordinary_tickets_fire_no_rules(ticket):
    output, rules = fired(ticket)
    assert rules == []
    assert output == BASE
