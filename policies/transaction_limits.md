# Transaction Limits and Velocity Controls (sample)
> **Illustrative sample policy.** Written for the SentinelAI demo. It is NOT an official RBI, FIU-IND or NPCI document and must not be relied on for compliance. Replace this folder with your institution's approved policies; the retrieval engine indexes whatever Markdown files are placed here.

## TL-1 Velocity controls
TL-1.1 More than 5 payments to new payees within 24 hours triggers manual review.
TL-1.2 Spend in one hour exceeding 5 times the customer's typical transaction value triggers review.
TL-1.3 A single transaction exceeding 150% of the customer's prior 12-month maximum is held for review.

## TL-2 New device and new payee cooling-off
TL-2.1 For the first 24 hours after a new device is registered, outgoing transfers are capped at a lower cooling-off limit set by the bank.
TL-2.2 High-value transfers to a payee added in the last 24 hours require additional authentication.

## TL-3 Restricted categories
TL-3.1 Payments to high-risk categories (crypto exchanges, online gaming wallets) above the customer's typical spend require step-up authentication.
