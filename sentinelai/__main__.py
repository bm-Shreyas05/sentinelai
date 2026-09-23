"""Command line interface.

  python -m sentinelai train            train and promote the initial model
  python -m sentinelai simulate -n 2000  push simulated traffic through the engine
  python -m sentinelai serve            run the REST API (uvicorn)
  python -m sentinelai mcp              run the MCP server over stdio (for Claude Desktop etc.)
  python -m sentinelai retrain          champion/challenger retrain with analyst labels
  python -m sentinelai drift            print the drift report
"""
import argparse, json, logging, sys

from .config import get_settings


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sentinelai")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train"); t.add_argument("--events", type=int, default=250_000)
    s = sub.add_parser("simulate"); s.add_argument("-n", type=int, default=2000)
    s.add_argument("--seed", type=int, default=99); s.add_argument("--fraud-rate", type=float, default=0.005)
    v = sub.add_parser("serve"); v.add_argument("--host", default="0.0.0.0"); v.add_argument("--port", type=int, default=8000)
    sub.add_parser("mcp")
    r = sub.add_parser("retrain"); r.add_argument("--events", type=int, default=250_000); r.add_argument("--force", action="store_true")
    sub.add_parser("drift")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    settings = get_settings()

    if a.cmd == "train":
        from .retrain import train_initial
        b = train_initial(settings, a.events)
        print(json.dumps({"version": b.version, "thresholds": b.thresholds, "metrics": b.metrics}, indent=2))
    elif a.cmd == "simulate":
        from collections import Counter
        from .engine import SentinelEngine
        from .synthetic import Simulator
        logging.getLogger("sentinelai.alerts").setLevel(logging.ERROR)
        eng, c = SentinelEngine(settings), Counter()
        for e in Simulator(n_users=800, seed=a.seed, fraud_rate=a.fraud_rate).stream(a.n):
            e["txn_id"] = f"S{a.seed}-{e['txn_id']}"
            c[eng.score(e, actor="simulator")["decision"]] += 1
        print(json.dumps({"decisions": dict(c), "metrics": eng.live_metrics(10**9)}, indent=2))
    elif a.cmd == "serve":
        import uvicorn
        uvicorn.run("sentinelai.api:app", host=a.host, port=a.port)
    elif a.cmd == "mcp":
        from .mcp_server import main as mcp_main
        mcp_main()
    elif a.cmd == "retrain":
        from .retrain import retrain
        print(json.dumps(retrain(settings, a.events, force=a.force), indent=2))
    elif a.cmd == "drift":
        from .engine import SentinelEngine
        print(json.dumps(SentinelEngine(settings).drift(), indent=2))


if __name__ == "__main__":
    main()
