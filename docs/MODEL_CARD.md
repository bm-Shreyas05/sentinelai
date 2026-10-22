# Model card

**Model.** LightGBM binary classifier over 17 behavioural features (see `sentinelai/features.py`).
Exact TreeSHAP contributions are produced with every prediction.

**Intended use.** Ranking payments by fraud risk to decide ALLOW / REVIEW / BLOCK and to explain the
decision to analysts and customers. Not intended for credit decisions or for any decision about a
person without human review of BLOCK outcomes.

**Training data.** Bootstrapped on simulated Indian payment events (legitimate behaviour including
phone upgrades, travel, rent transfers, bill splitting; fraud including UPI social-engineering scams,
account takeover, card testing, cloned cards and mule rings). Replace with institutional data.

**Evaluation.** Time-ordered 70/15/15 split; thresholds chosen on validation (block: precision ≥ 90%;
review: recall ≥ 85%) and evaluated on the untouched test slice. Public-data check of the same
recipe: ULB credit-card fraud, PR-AUC 0.751 (logistic baseline 0.694). See the README for figures.

**Results on simulated data** (`benchmark/product_eval.py`, test slice of 37,501 events with 315
frauds): PR-AUC 0.841; review tier 38.6% precision / 86.0% recall; block tier 89.0% precision /
71.8% recall. Caught at review tier or above: card testing, cloned card and mule ring 100%, account
takeover 76.7% (43 frauds), UPI scam 60.5% (86 frauds).

**Known weaknesses.** Social-engineering scams on the customer's own device are the hardest case
(60% caught at review, 24% at block). Account takeover via malware on the customer's own phone is
next. Review-tier precision is low (about 4 in 10 alerts are fraud). Cold-start customers (no
history) receive more alerts; the drift monitor flags a rise in the share of payments from
customers with fewer than 3 prior payments.

**Fairness and privacy.** Features are behavioural (amounts, timing, devices, locations, merchant
categories); no demographic attributes are used. Location is city-level. Customer messages never
show scores.
