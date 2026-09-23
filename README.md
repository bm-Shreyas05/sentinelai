# SentinelAI

Real-time fraud detection, explanation and case management for Indian payments (UPI, cards,
netbanking), with an MCP server so AI agents can operate it.

A payment comes in, SentinelAI scores it in a few milliseconds, decides **ALLOW / REVIEW / BLOCK**,
explains the decision in plain English ("₹1,20,000 vs ₹1,900 typical, from a device never seen before"),
and for anything flagged an investigation agent opens a case, pulls the customer's history, cites the
relevant policy clause, drafts the customer SMS and alerts analysts. Analyst verdicts become training
labels, and a champion/challenger gate decides whether a retrained model ships.

## Measured results

**Public benchmark: ULB credit-card fraud** (284,807 real transactions, 492 frauds). Time-ordered
70/15/15 split so the model never sees the future; thresholds chosen on validation and frozen.

| Model | PR-AUC | Block tier (precision / recall) | Review tier (precision / recall) |
|---|---|---|---|
| Logistic regression baseline | 0.694 | 97% / 63% | 51% / 75% |
| **SentinelAI recipe (LightGBM)** | **0.751** | **97% / 67%** | **57% / 75%** |

The test period contains only 52 frauds, so treat these as roughly ±0.05. Reproduce with
`python benchmark/ulb_benchmark.py --csv data/creditcard.csv`.

**Product model on simulated Indian payment events** (250,000 events, 5 fraud scenarios):
PR-AUC 0.84; block tier 89% precision / 72% recall. Per scenario at the review tier: card testing,
cloned cards and mule rings 100%; UPI social-engineering scams 78%; account takeover 81%. Scams are
hardest because the victim pays from their own phone at home.

**Latency** (engine, single thread, including features, TreeSHAP, SQLite write and agent investigation):
p50 2.5 ms, p99 8.2 ms, ~380 transactions/s. Through HTTP: p99 8.7 ms.

## What's in the box

| Capability | Where |
|---|---|
| Feature store (17 behavioural features, same code for training and serving, state persisted) | `sentinelai/features.py` |
| LightGBM model, time-ordered training, threshold selection, versioned registry | `sentinelai/model.py` |
| Exact TreeSHAP contributions → plain-English "this payment vs normal" reasons | `sentinelai/reasons.py` |
| Cost-sensitive decisions (small payments are never hard-blocked; overrides are audited) | `sentinelai/engine.py` |
| Investigation agent with a traced tool chain and optional LLM narrative | `sentinelai/agent.py` |
| Clause-level policy retrieval with citations and abstention | `sentinelai/policy.py` |
| PSI drift monitoring against a reference saved with each model | `sentinelai/drift.py` |
| Champion/challenger retraining with analyst labels | `sentinelai/retrain.py` |
| REST API with API keys, rate limiting, validation, webhook batch ingestion | `sentinelai/api.py` |
| MCP server (8 tools) for Claude Desktop, Claude Code or any MCP client | `sentinelai/mcp_server.py` |
| Operations console: live feed, case queue, investigation, monitoring, policy assistant | `dashboard/app.py` |
| 22 tests: engine regressions, policy retrieval eval, API, MCP | `tests/` |

## Quick start

```bash
pip install -r requirements.txt
python -m sentinelai train                 # trains and promotes the first model (~15 s)
streamlit run dashboard/app.py             # console on http://localhost:8501, press ▶ Start
python -m sentinelai serve                 # API on http://localhost:8000/docs
pytest -q                                  # 22 tests
```

Or with Docker: `cp .env.example .env && docker compose up --build`.

### Score a payment

```bash
curl -X POST localhost:8000/v1/transactions -H "X-API-Key: dev-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"U00042","amount":84000,"city":"Kolkata","device_id":"new-phone","category":"electronics","channel":"upi"}'
```

### Connect an AI agent over MCP

Copy `claude_desktop_config.example.json` into your Claude Desktop config (fix the paths). The agent
gets `score_transaction`, `get_case`, `list_open_cases`, `resolve_case`, `get_user_history`,
`lookup_policy`, `check_drift` and `live_metrics`, all sharing the same database as the console, so
an analyst and an agent work the same case queue.

## Design decisions

- **Benchmark on public data, train on the institution's data.** The ULB features are anonymised,
  so they cannot drive a product that sees raw events. The recipe is proven on ULB; the product model
  trains on each bank's own event schema, bootstrapped with the simulator until labels accumulate.
- **Time-ordered splits everywhere.** Random splits leak future fraud patterns and inflate scores.
- **The model decides risk; a cost layer decides friction.** Below `SENTINEL_MIN_BLOCK_AMOUNT` (₹500)
  a BLOCK becomes REVIEW, because a hard block costs the customer more than the money at risk. Card
  testing is still stopped: the burst is reviewed and the large follow-up payment is blocked.
- **Explanations come from the model**, not a parallel rule set, and are only shown when the
  underlying facts support them (e.g. "rapid burst" requires an actual burst).
- **Deterministic agent, optional LLM.** The investigation chain is reproducible and auditable. An
  LLM, if configured, only writes a narrative from the same evidence; it never changes a decision.
- **SQLite in WAL mode** keeps deployment to one file for a single node. Swap for PostgreSQL when
  scaling horizontally (all SQL is in `engine.py` and `db.py`).

## Limitations (read before any real use)

- `policies/` contains **illustrative sample policies**, not official RBI, FIU-IND or NPCI text.
  Replace them with your institution's approved documents.
- The product model is trained on **simulated** events. Real deployment needs the institution's
  labelled history; metrics will differ.
- Policy retrieval is lexical (TF-IDF with synonyms). It is precise when confident and says so when
  it isn't, but it does not understand paraphrases the way an embedding model would.
- No customer-facing reply handling (the YES/NO in the SMS), SSO for analysts, or PII encryption at
  rest yet. See `docs/ARCHITECTURE.md` for the roadmap.

## Project layout

```
sentinelai/     core package (engine, features, model, agent, policy, drift, API, MCP)
dashboard/      Streamlit operations console
policies/       Markdown policy documents indexed by clause ID (samples)
benchmark/      ULB benchmark script and results
tests/          pytest suite
docs/           architecture and model card
```

Licence: MIT. Dataset licence for the benchmark: ULB Credit Card Fraud, Open Database License.
