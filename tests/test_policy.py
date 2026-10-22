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
# Held-out paraphrases written after the thresholds were calibrated (22 Oct 2026). Not used for
# tuning, except that they exposed the "credit card" -> refund synonym bug. Lexical retrieval
# answers few of these confidently; the guarantee that matters is that it is never confidently wrong.
HELD_OUT = {
    "how long do we keep KYC records": "AML-3.1",
    "what are the cash transaction report rules": "AML-2.1",
    "customer splits payments to avoid reporting limits": "AML-2.2",
    "what must a blocked payment SMS contain": "CP-1.2",
    "can we show the risk score to the customer": "FRF-2.2",
    "how quickly must analysts look at review alerts": "FRF-1.2",
    "how long is the old model kept after a new one is promoted": "FRF-3.4",
    "limits on transfers from a newly registered phone": "TL-2.1",
    "rules for paying crypto exchanges": "TL-3.1",
    "customer was tricked into paying a scammer, what do we do": "FRF-4.4",
    "what if the customer reports fraud late": "CP-2.2",
    "what is the interest rate on fixed deposits": None,
    "who approves new credit card applications": None,
    "how often do we audit branch cash vaults": None,
    "what is the penalty for late loan repayment": None,
    "how often should high-value customers have KYC refreshed": None,
}
P = PolicyIndex(Path(__file__).resolve().parent.parent / "policies")


def _top(q):
    a = P.answer(q)
    return None if a["abstained"] else a["citations"][0]["id"]


def test_high_confidence_answers_are_always_correct():
    for q, want in {**EVAL, **HELD_OUT}.items():
        a = P.answer(q)
        if a["confidence"] == "high":
            assert a["citations"][0]["id"] == want, q


def test_overall_accuracy_and_abstention():
    correct = sum(_top(q) == w for q, w in EVAL.items())
    assert correct / len(EVAL) >= 0.9          # 11/12; "high risk customers reviewed" gets a low-confidence TL-3.1
    assert P.answer("what is the capital of France")["abstained"]


def test_every_answer_cites_a_clause():
    a = P.answer("when do we file an STR?")
    assert "[AML-1.1]" in a["answer"]


def test_held_out_accuracy_does_not_regress():
    correct = sum(_top(q) == w for q, w in HELD_OUT.items())
    assert correct >= 6, f"{correct}/{len(HELD_OUT)}"   # measured 6/16 on 22 Oct 2026


def test_credit_card_is_not_a_refund_question():
    assert _top("who approves new credit card applications") != "CP-2.3"
    assert _top("will the disputed amount be credited back") == "CP-2.3"
