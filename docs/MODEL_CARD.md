# Model card

**Model.** LightGBM binary classifier over 19 behavioural features (see `sentinelai/features.py`).
Exact TreeSHAP contributions are produced with every prediction.

**Intended use.** Ranking payments by fraud risk to decide ALLOW / REVIEW / BLOCK and to explain the
decision to analysts and customers. Not intended for credit decisions or for any decision about a
person without human review of BLOCK outcomes.

**Training data.** Bootstrapped on simulated Indian payment events (legitimate behaviour including
phone upgrades, travel, rent transfers to known payees, new payees including popular vendors, bill
splitting; fraud including UPI social-engineering scams, account takeover, card testing, cloned cards
and mule rings, with scams and mules paying collector accounts). Replace with institutional data.

**Evaluation.** Time-ordered 70/15/15 split; thresholds chosen on validation (block: precision ≥ 90%;
review: recall ≥ 85%) and evaluated on the untouched test slice. Public-data check of the same
recipe: ULB credit-card fraud, PR-AUC 0.751 (logistic baseline 0.694) on one split and seed. Robustness
checks on the same data (`benchmark/ulb_robustness.py`) show this is optimistic: 0.687 to 0.752
across seeds, no consistent win over logistic regression on rolling time windows (PR-AUC 0.57 to
0.84). The product's previous hyperparameters reached only 0.656, so since 2026-10-23 it trains
with the benchmark recipe. ULB has none of the product's behavioural
features, so the deployed model itself has not been evaluated on real data. See the README.

**Results on simulated data** (`benchmark/product_eval.py`, test slice of 37,501 events with 313
frauds): PR-AUC 0.925; review tier 72.5% precision / 86.9% recall; block tier 92.3% precision /
80.8% recall. Caught at review tier or above: card testing 99.3% (150 frauds), cloned card and mule
ring 100%, account takeover 70.3% (37 frauds), UPI scam 61.8% (76 frauds). Without the two payee
features, on the same events: PR-AUC 0.872, review tier 46.6% precision / 85.9% recall.

**Known weaknesses.** Social-engineering scams on the customer's own device are the hardest case
(62% caught at review, 38% at block). Account takeover via malware on the customer's own phone is
next (70% at review). About 3 in 10 review alerts are legitimate payments. The payee signals rely on
the simulator's payee behaviour, which was designed alongside them; expect a smaller gain on real
data. Cold-start customers (no
history) receive more alerts; the drift monitor flags a rise in the share of payments from
customers with fewer than 3 prior payments.

**Fairness and privacy.** Features are behavioural (amounts, timing, devices, locations, merchant
categories); no demographic attributes are used. Location is city-level. Customer messages never
show scores.
