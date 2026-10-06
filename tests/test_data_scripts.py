import random
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from dedup_split import connected_groups, normalize  # noqa: E402
from generate_data import needs_human_for, sample_spec  # noqa: E402
from hand_check import parse_corrections  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402
from triage.schema import Triage  # noqa: E402


def test_normalize_ignores_order_numbers_case_and_accents():
    assert normalize("Pedido #12345 NÃO chegou!") == normalize("pedido 98765 nao chegou")


def test_connected_groups_links_chains():
    sims = np.array([[0, 0.9, 0], [0.9, 0, 0.8], [0, 0.8, 0]], dtype=float)
    groups = connected_groups(sims, 0.7)
    assert groups[0] == groups[1] == groups[2]
    assert len(set(connected_groups(sims, 0.95))) == 3


def test_every_scenario_produces_valid_labels():
    for scenario in SCENARIOS:
        for priority in scenario.priorities:
            for sentiment in scenario.sentiments:
                Triage.model_validate({
                    "category": scenario.category, "priority": priority, "sentiment": sentiment,
                    "needs_human": needs_human_for(scenario, priority),
                    "suggested_action": scenario.action, "reason": "check",
                })


def test_sampler_is_deterministic_and_consistent():
    first = [sample_spec(random.Random(42), i) for i in range(1, 4)]
    second = [sample_spec(random.Random(42), i) for i in range(1, 4)]
    assert first == second
    for spec in [sample_spec(random.Random(s), 1) for s in range(300)]:
        if spec["style"] == "angry":
            assert spec["labels"]["sentiment"] == "negative"
        if spec["labels"]["priority"] == "urgent" or spec["flag"] in {"safety", "legal", "security", "chargeback"}:
            assert spec["labels"]["needs_human"] is True


def test_parse_corrections():
    assert parse_corrections("priority=high; needs_human=true") == {"priority": "high", "needs_human": True}
    assert parse_corrections("") == {}
    with pytest.raises(ValueError):
        parse_corrections("urgency=high")
