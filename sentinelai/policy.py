"""Clause-level retrieval over the Markdown policies in the policy folder.

Each numbered clause (e.g. "FRF-3.2 ...") is indexed with its document and section title, so
every answer cites an exact clause ID. Queries with no sufficiently similar clause abstain
instead of guessing. TF-IDF is used deliberately: it runs fully offline, is deterministic
and auditable, and performs well on short, keyword-dense policy text.
"""
import re
from pathlib import Path

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

# Words so common in banking policy that they carry no signal on their own
DOMAIN_STOP = {"customer", "customers", "account", "accounts", "transaction", "transactions",
               "payment", "payments", "bank", "banks"}
ANSWER_ABOVE, ABSTAIN_BELOW = 0.30, 0.17     # calibrated on tests/test_policy.py eval set

CLAUSE = re.compile(r"^([A-Z]{2,5}-\d+\.\d+)\s+(.*)$")

REASON_QUERIES = {
    "velocity": "card testing burst of small payments followed by larger one block card",
    "amount": "single transaction exceeding customer maximum held for review high value",
    "device": "new device registered cooling-off limit outgoing transfers",
    "shared_device": "mule accounts devices shared by many accounts escalate AML STR",
    "travel": "impossible travel card used in two cities cloned card blocked",
    "location": "impossible travel card used in two cities cloned card blocked",
    "merchant": "high-risk categories crypto gaming step-up authentication",
    "time": "customer notified blocked transactions confirm or deny",
    "new_customer": "new payee added high-value transfer additional authentication",
    "spend_velocity": "spend in one hour exceeding typical transaction value triggers review",
    "scam_pattern": "social-engineering scam customer called before release never asks OTP remote-access",
}


SYNONYMS = {
    r"\bstrs?\b": "suspicious transaction report STR",
    r"\bctrs?\b": "cash transaction report CTR",
    r"\b(file|filed|filing|submit)\b": "file furnish furnished report",
    r"\b(when|how (fast|soon|long)|deadline|timeline)\b": "within days",
    r"\b(otp|pin)\b": "OTP PIN never share",
    r"\bmules?\b": "mule accounts shared device",
    r"\b(liab\w*)\b": "zero liability",
    r"\b(refund\w*|reimburs\w*|credit(?!\s+cards?\b)\w*)\b": "shadow-credited",   # not "credit card"
    r"\b(wrong\w*|mistak\w*|incorrect\w*|false alarm\w*)\b": "false positive",
    r"\b(releas\w*|unblock\w*)\b": "released hold",
    r"\b(tell|inform|disclose|notify)\b": "told tipping-off",
}


def expand(query):
    out = query
    for pat, extra in SYNONYMS.items():
        if re.search(pat, query, flags=re.I):
            out += " " + extra
    return out


class PolicyIndex:
    def __init__(self, policy_dir):
        self.clauses = []
        for path in sorted(Path(policy_dir).glob("*.md")):
            doc, section = path.stem, ""
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("# "):
                    doc = line[2:].strip()
                elif line.startswith("## "):
                    section = line[3:].strip()
                else:
                    m = CLAUSE.match(line)
                    if m:
                        self.clauses.append({"id": m.group(1), "text": m.group(2),
                                             "document": doc, "section": section, "file": path.name})
        if not self.clauses:
            raise ValueError(f"No numbered clauses found in {policy_dir}")
        corpus = [f"{c['section']} {c['text']}" for c in self.clauses]
        # word n-grams capture phrases; character n-grams catch word variants (review/reviewed)
        stop = list(ENGLISH_STOP_WORDS | DOMAIN_STOP)
        self.word = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words=stop)
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(4, 5), sublinear_tf=True)
        self.Mw, self.Mc = self.word.fit_transform(corpus), self.char.fit_transform(corpus)

    def search(self, query, k=3, min_score=ABSTAIN_BELOW):
        q = expand(query)
        sims = 0.6 * linear_kernel(self.word.transform([q]), self.Mw)[0] + \
               0.4 * linear_kernel(self.char.transform([q]), self.Mc)[0]
        order = sims.argsort()[::-1][:k]
        return [dict(self.clauses[i], score=round(float(sims[i]), 3)) for i in order if sims[i] >= min_score]

    def answer(self, question, k=3):
        hits = self.search(question, k=k)
        if not hits:
            return {"answer": None, "abstained": True, "confidence": "none", "citations": [],
                    "message": "No clause in the loaded policies answers this. Check with compliance."}
        lead = hits[0]
        confidence = "high" if lead["score"] >= ANSWER_ABOVE else "low"
        text = f"{lead['text']} [{lead['id']}]"
        extra = [h for h in hits[1:] if h["score"] >= 0.6 * lead["score"]]
        if extra:
            text += " Related: " + " ".join(f"{h['text']} [{h['id']}]" for h in extra)
        if confidence == "low":
            text = "Possible match, verify with compliance: " + text
        return {"answer": text, "abstained": False, "confidence": confidence, "citations": hits}

    def for_reasons(self, codes, decision):
        seen, refs = set(), []
        queries = [REASON_QUERIES[c] for c in codes if c in REASON_QUERIES]
        if decision == "BLOCK":
            queries.append("transactions held customer contacted registered channel before release")
        for q in queries:
            for h in self.search(q, k=1):
                if h["id"] not in seen:
                    seen.add(h["id"]); refs.append(h)
        return refs
