"""MCP server: exposes SentinelAI as tools any MCP client (Claude Desktop, Claude Code, custom
agents) can call. Run with `python -m sentinelai mcp` (stdio transport).

The tools share one engine, so context persists across calls: a transaction scored by one
agent is immediately visible to another agent's investigation, drift check or policy lookup.
"""
try:                                   # MCP Python SDK 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:                    # MCP Python SDK 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from .engine import SentinelEngine

mcp = _Server("sentinelai", instructions=(
    "Fraud operations tools for an Indian bank. Amounts are in INR. Always cite policy clause IDs "
    "returned by lookup_policy, and never reveal model scores to customers."))
_engine = None


def eng():
    global _engine
    if _engine is None:
        _engine = SentinelEngine()
    return _engine


@mcp.tool()
def score_transaction(user_id: str, amount: float, city: str, device_id: str,
                      category: str = "online_shopping", channel: str = "upi", merchant: str = "",
                      payee: str = "") -> dict:
    """Score a payment in INR. For a p2p_transfer pass the beneficiary's UPI ID as payee. Returns fraud
    probability, decision (ALLOW/REVIEW/BLOCK), plain-English reasons, and a case_id when a case was
    opened and investigated."""
    txn = {"user_id": user_id, "amount": amount, "city": city, "device_id": device_id,
           "category": category, "channel": channel}
    if merchant:
        txn["merchant"] = merchant
    if payee:
        txn["payee"] = payee
    return eng().score(txn, actor="mcp")


@mcp.tool()
def get_case(case_id: int) -> dict:
    """Full case file: transaction, reasons, priority, recommended actions, policy citations and the
    investigation agent's tool-call trace."""
    c = eng().get_case(case_id)
    c["transaction"].pop("features", None); c["transaction"].pop("contributions", None)
    return c


@mcp.tool()
def list_open_cases(limit: int = 20) -> dict:
    """Open fraud cases, most urgent first."""
    cases = [{k: c[k] for k in ("case_id", "txn_id", "priority", "decision", "amount", "user_id", "city", "score")}
             for c in eng().list_cases("open", limit)]
    return {"count": len(cases), "cases": cases}


@mcp.tool()
def resolve_case(case_id: int, is_fraud: bool, analyst: str, notes: str = "") -> dict:
    """Record an analyst decision. The label feeds the next retraining run."""
    return eng().resolve_case(case_id, is_fraud, analyst, notes)


@mcp.tool()
def get_user_history(user_id: str, limit: int = 20) -> dict:
    """Recent transactions for a customer with scores, decisions and analyst labels."""
    rows = eng().user_history(user_id, limit)
    return {"user_id": user_id, "count": len(rows), "transactions": rows}


@mcp.tool()
def lookup_policy(question: str) -> dict:
    """Answer a question from the institution's policy documents with clause citations.
    Abstains when no clause matches."""
    return eng().ask_policy(question)


@mcp.tool()
def check_drift(window: int = 2000) -> dict:
    """Population Stability Index for every model feature and the score distribution,
    and whether policy recommends retraining."""
    return eng().drift(window)


@mcp.tool()
def live_metrics(window_s: int = 3600) -> dict:
    """Volume, alert rate, blocked amount and case counts for the recent window."""
    return eng().live_metrics(window_s)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
