# Fraud Detection Risk Framework (sample)
> **Illustrative sample policy.** Written for the SentinelAI demo. It is NOT an official RBI, FIU-IND or NPCI document and must not be relied on for compliance. Replace this folder with your institution's approved policies; the retrieval engine indexes whatever Markdown files are placed here.

## FRF-1 Decision tiers
FRF-1.1 Transactions scored at or above the BLOCK threshold are held and the customer is contacted through a registered channel before release.
FRF-1.2 Transactions scored between the REVIEW and BLOCK thresholds are processed but placed in the analyst queue for review within 2 hours.
FRF-1.3 Thresholds are set on a validation window: BLOCK targets at least 90% precision; REVIEW targets at least 85% recall.

## FRF-2 Explainability and audit
FRF-2.1 Every REVIEW or BLOCK decision must store the model version, score, feature values and per-feature contributions.
FRF-2.2 Customer-facing messages must state the reason in plain language and must never include the model score.
FRF-2.3 Analyst resolutions (confirmed fraud or false positive) are recorded with the analyst identity and notes and are used as training labels.

## FRF-3 Monitoring and retraining
FRF-3.1 Feature drift is measured daily with the Population Stability Index. PSI above 0.10 is a warning; above 0.25 is critical.
FRF-3.2 Retraining is triggered when two or more features are critical, when score-distribution PSI exceeds 0.15, or every 30 days.
FRF-3.3 A challenger model replaces the champion only if PR-AUC improves by at least 0.003 and review-tier recall does not fall by more than 1 percentage point.
FRF-3.4 The previous champion is retained for 30 days to allow immediate rollback.

## FRF-4 Scenario handling
FRF-4.1 Card testing: when a burst of small payments is followed by a larger one, the card is blocked and reissued.
FRF-4.2 Impossible travel: a card used in two cities faster than physically possible is treated as cloned; the card is blocked.
FRF-4.3 Suspected mule accounts (devices shared by many accounts) are escalated to the AML team, not only the fraud team.
FRF-4.4 Social-engineering (authorised push payment) scams: the customer is called before release and reminded that the bank never asks for OTPs or remote-access apps.
