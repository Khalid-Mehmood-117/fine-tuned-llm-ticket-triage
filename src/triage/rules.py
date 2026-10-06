"""Deterministic business rules applied after the model.

Rules only escalate: they raise priority, set needs_human to true or switch the action to an
escalation. They never lower priority or clear needs_human. Every rule that triggers is returned
in rules_fired with the text it matched and the fields it changed.

Keyword lists cover English, Spanish, French, German, Portuguese and Roman Urdu. Text is
lowercased and accents are stripped before matching, so patterns are written without accents.
Negation ("this is not a fire hazard") is not understood; that is a known limitation.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from triage.schema import ESCALATION_ACTIONS, Action, Priority, raise_priority


def _compile(patterns: list[str]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(patterns) + r")\b")


SAFETY = _compile([
    # English
    r"injur\w*", r"fire", r"caught fire", r"smok(e|ed|ing)", r"burn(s|ed|t|ing)?",
    r"electric(al)? shock", r"shocked me", r"gave me a shock", r"chok(e|ed|ing)",
    r"overheat\w*", r"explod\w*", r"explosion", r"sparks?", r"sparking", r"melt(ed|ing)",
    r"hospital", r"allergic reaction", r"poison\w*", r"triggered my allerg\w*", r"anaphyla\w*",
    r"epipen", r"ambulance", r"emergency room", r"medical attention", r"hives",
    r"throat (is )?(swelling|swollen|closing)", r"(seriously|very|really|super|so) (ill|sick)",
    r"(got|made me|making me|became) (very |really |super |so |seriously )?(ill|sick)",
    r"almost died", r"(could|might) (have )?die(d)?",
    # Spanish
    r"incendio", r"fuego", r"humo", r"quem\w+", r"queim\w+", r"herid\w*", r"lesion(es)?",
    r"descarga electrica", r"sobrecalent\w*", r"explot\w*", r"reaccion alergica", r"intoxic\w*",
    # French
    r"incendie", r"feu", r"fumee", r"brul\w*", r"bless(e|es|ee|ees|ure|ures)", r"choc electrique", r"surchauff\w*",
    r"hopital", r"reaction allergique", r"intoxication",
    # German
    r"feuer", r"rauch\w*", r"brennt", r"brannte", r"verbrann\w*", r"verbrennung\w*", r"verletz\w*",
    r"stromschlag", r"uberhitz\w*", r"krankenhaus", r"allergische reaktion", r"vergiftung",
    # Portuguese
    r"fogo", r"fumaca", r"ferid\w*", r"lesao", r"choque eletrico", r"superaquec\w*",
    r"reacao alergica",
    # Roman Urdu
    r"aag", r"dhuan", r"dhuwan", r"jal (gaya|gya|gayi|gai)", r"zakhmi", r"chot", r"current laga",
])

LEGAL = _compile([
    # English
    r"lawyers?", r"attorneys?", r"lawsuit", r"sue (you|your|the company|them)", r"suing",
    r"will sue", r"court", r"legal (action|representation|help|advice|counsel|steps)",
    r"take legal", r"seek legal", r"small claims", r"gdpr", r"data deletion request",
    r"(delete|erase) (all )?(of )?my (personal )?(data|information)", r"right to (be forgotten|erasure)",
    r"complaint with the (appropriate |relevant )?authorities",
    r"data protection (authority|regulator|office)", r"regulator", r"ombudsman", r"trading standards",
    # Spanish
    r"abogados?", r"demandar(los|les)?", r"tribunal(es)?", r"accion(es)? legal(es)?", r"rgpd",
    r"proteccion de datos", r"(eliminar|borrar|suprimir) (todos )?mis datos",
    # French
    r"avocat", r"poursuites? judiciaires?", r"action en justice", r"cnil", r"protection des donnees",
    r"(supprimer|effacer) (toutes )?mes donnees",
    # German
    r"anwalt", r"rechtsanwalt", r"klage", r"verklagen", r"vor gericht", r"gerichtlich\w*", r"rechtliche schritte", r"dsgvo",
    r"datenschutzbehorde", r"loschung (meiner|aller meiner) (personenbezogenen )?daten",
    r"meine (personenbezogenen )?daten (zu )?loschen",
    # Portuguese
    r"advogado", r"processo judicial", r"acao judicial", r"lgpd", r"procon",
    r"processar (voces|a empresa|vcs)", r"vou processar",
    r"(exclusao|excluir|apagar|eliminar) (imediata )?(de )?(todos )?(os )?meus dados",
    # Roman Urdu
    r"wakeel", r"wakil", r"adalat", r"case kar(unga|ungi|enge)", r"legal notice",
])

SECURITY = _compile([
    # English
    r"hacked", r"hackers?", r"unauthori[sz]ed (charge|charges|login|logins|access|transaction|transactions|purchase|purchases|payment|payments)",
    r"someone (logged|got|broke) into my account", r"account (was |has been |got )?(compromised|stolen|taken over)",
    r"fraud\w*", r"phishing", r"identity theft",
    # Spanish
    r"hacke\w+", r"fraude", r"no autorizad[oa]s?", r"suplantacion",
    # French
    r"pirat\w+", r"non autorise(e|es|s)?",
    # German
    r"gehackt", r"betrug", r"nicht autorisiert\w*", r"unbefugt\w*",
    # Portuguese
    r"hackead[oa]", r"nao autorizad[oa]s?", r"invadid[oa]",
    # Roman Urdu
    r"hack (ho gaya|hogaya|ho gya|hogya)",
])

CHARGEBACK = _compile([
    r"chargebacks?", r"charge back",
    r"disput(e|ing) (it|this|the charge|this charge|the payment|the transaction)",
    r"contracargo", r"retrofacturation", r"ruckbuchung", r"rucklastschrift",
    r"contestar (a|essa|esta) (compra|cobranca) (com|no|junto ao) (meu )?(banco|cartao)",
])


@dataclass
class RuleHit:
    rule: str
    matched: str
    changes: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"rule": self.rule, "matched": self.matched, "changes": self.changes}


def normalize(text: str) -> str:
    """Lowercase and strip accents so 'Brûlé' matches 'brul'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _set(output: dict, key: str, value, changes: dict) -> None:
    if output[key] != value:
        changes[key] = [output[key], value]
        output[key] = value


def _urgent_escalation(output: dict, changes: dict) -> None:
    _set(output, "needs_human", True, changes)
    _set(output, "priority", Priority.urgent.value, changes)
    _set(output, "suggested_action", Action.escalate_to_safety_legal.value, changes)


def _at_least_high(output: dict, changes: dict) -> None:
    _set(output, "needs_human", True, changes)
    _set(output, "priority", raise_priority(output["priority"], Priority.high.value), changes)


KEYWORD_RULES = [
    ("R1_SAFETY", SAFETY, _urgent_escalation),
    ("R2_LEGAL", LEGAL, _urgent_escalation),
    ("R3_SECURITY", SECURITY, _at_least_high),
    ("R4_CHARGEBACK", CHARGEBACK, _at_least_high),
]


def apply_rules(ticket: str, triage: dict) -> tuple[dict, list[RuleHit]]:
    """Return a new triage dict with the rules applied, plus every rule that triggered."""
    output = dict(triage)
    text = normalize(ticket)
    hits = []
    for rule_id, pattern, effect in KEYWORD_RULES:
        match = pattern.search(text)
        if match:
            hit = RuleHit(rule_id, match.group(0))
            effect(output, hit.changes)
            hits.append(hit)

    if output["suggested_action"] in {a.value for a in ESCALATION_ACTIONS}:
        hit = RuleHit("R5_ESCALATION_CONSISTENCY", output["suggested_action"])
        _set(output, "needs_human", True, hit.changes)
        if hit.changes:
            hits.append(hit)
    return output, hits
