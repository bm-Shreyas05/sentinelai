"""Retrieval evaluation. The key guarantee: high-confidence answers must be correct."""
from pathlib import Path

from sentinelai.policy import PolicyIndex

EVAL = {
    "when do we file an STR?": "AML-1.1",
    "How fast must we file a suspicious transaction report?": "AML-1.1",
    "can we tell the customer about the STR": "AML-1.2",
    "what if a card is used in two cities quickly": "FRF-4.2",
    "customer reported unauthorised transaction, what is their liability": "CP-2.1",
    "what PSI triggers retraining": "FRF-3.2",
    "is the customer refunded while we investigate": "CP-2.3",
    "what happens with devices used by many accounts": "FRF-4.3",
    "do we release a payment wrongly blocked": "CP-3.1",
    "what is the capital of France": None,
    "what is the minimum balance for a savings account": None,
    "how often are high risk customers reviewed": None,
}
P = PolicyIndex(Path(__file__).resolve().parent.parent / "policies")


def test_high_confidence_answers_are_always_correct():
    for q, want in EVAL.items():
        a = P.answer(q)
        if a["confidence"] == "high":
            assert a["citations"][0]["id"] == want, q


def test_overall_accuracy_and_abstention():
    correct = sum((None if P.answer(q)["abstained"] else P.answer(q)["citations"][0]["id"]) == w
                  for q, w in EVAL.items())
    assert correct / len(EVAL) >= 0.9
    assert P.answer("what is the capital of France")["abstained"]


def test_every_answer_cites_a_clause():
    a = P.answer("when do we file an STR?")
    assert "[AML-1.1]" in a["answer"]
