"""SentinelAI operations console.

    streamlit run dashboard/app.py

Live panels use st.fragment(run_every=...), so each refreshes on its own timer without
rerunning the page: KPIs stay live on every page and form inputs are never interrupted.
"""
import html, json, sys, time
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sentinelai.config import get_settings            # noqa: E402
from sentinelai.engine import SentinelEngine          # noqa: E402
from sentinelai.model import Registry                 # noqa: E402
from sentinelai.reasons import customer_message, inr  # noqa: E402
from sentinelai.synthetic import Simulator            # noqa: E402

st.set_page_config(page_title="SentinelAI", page_icon="🛡", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.kpi { background:#141920; border:1px solid #232a33; border-top:2px solid var(--c,#30363d); padding:.8rem 1rem; }
.kpi .l { color:#8b949e; font-size:.78rem; }
.kpi .v { font-family:'IBM Plex Mono',monospace; font-size:1.55rem; font-weight:600; color:#e6edf3; }
.card { background:#141920; border:1px solid #232a33; border-left:3px solid var(--c,#ff5a4f); padding:.8rem 1rem; margin-bottom:.5rem; }
.card h4 { margin:0 0 .35rem 0; font-size:.98rem; color:#e6edf3; }
.pair { display:grid; grid-template-columns:1fr 1fr; gap:.5rem; margin:.3rem 0; font-family:'IBM Plex Mono',monospace; font-size:.82rem; }
.pair div { background:#0f1318; padding:.35rem .55rem; } .pair small { color:#6e7681; display:block; font-size:.7rem; }
.muted { color:#8b949e; font-size:.86rem; }
.banner { padding:1rem 1.2rem; border:1px solid var(--c); background:#12161c; margin-bottom:1rem; }
.mono { font-family:'IBM Plex Mono',monospace; }
.trace { margin:.2rem 0 .4rem 0; }
.step { display:grid; grid-template-columns:1.7rem 1fr auto; gap:.15rem .6rem; padding:.3rem 0 .3rem .2rem;
        border-left:2px solid #232a33; margin-left:.6rem; }
.step .n { margin-left:-1.05rem; width:1.5rem; height:1.5rem; border-radius:50%; background:#1c232c; color:#8b949e;
           font:600 .72rem 'IBM Plex Mono',monospace; display:flex; align-items:center; justify-content:center; }
.step .t { font:600 .84rem 'IBM Plex Mono',monospace; color:#e6edf3; }
.step .ms { font:.74rem 'IBM Plex Mono',monospace; color:#6e7681; }
.step .io { grid-column:2 / 4; font:.76rem 'IBM Plex Mono',monospace; color:#8b949e; word-break:break-word; }
.step .io b { color:#6e7681; font-weight:400; }
.step.notify .n { background:#3a1d1b; color:#ff5a4f; } .step.decide .n { background:#2d2412; color:#f0a500; }
</style>""", unsafe_allow_html=True)

DECISION_COLOR = {"BLOCK": "#ff5a4f", "REVIEW": "#f0a500", "ALLOW": "#3fb950"}
PRIORITY_ICON = {"critical": "🔴", "high": "🟠", "normal": "🟡"}


# ── engine and demo traffic (shared across browser sessions) ─────────────────
@st.cache_resource(show_spinner="Starting SentinelAI (first run trains the model, ~20 s)…")
def get_engine():
    s = get_settings()
    if Registry(s.model_dir).current_version() is None:
        from sentinelai.retrain import train_initial
        train_initial(s)
    eng = SentinelEngine(s)
    sim = Simulator(n_users=1500, seed=int(time.time()) % 1000, fraud_rate=0.006)
    stream = sim.stream(10**9)
    if eng.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0:
        import logging; logging.getLogger("sentinelai.alerts").setLevel(logging.ERROR)
        for _ in range(6000):                     # warm up customer histories so the demo isn't all cold-start
            e = next(stream); e["txn_id"] = f"B-{e['txn_id']}"; eng.score(e, actor="bootstrap")
    return eng, {"stream": stream, "running": False, "rate": 5}


eng, traffic = get_engine()

# ── sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🛡 SentinelAI")
    st.caption(f"Model {eng.bundle.version}")
    if "goto" in st.session_state:            # set by open_case; applied before the radio is drawn
        st.session_state.page = st.session_state.pop("goto")
    page = st.radio("Go to", ["Operations", "Case queue", "Investigation", "Agent activity", "Monitoring & model",
                              "Policy assistant", "Connect (API & MCP)"], key="page", label_visibility="collapsed")
    st.divider()
    st.markdown("**Demo traffic**")
    c1, c2 = st.columns(2)
    if c1.button("▶ Start", use_container_width=True): traffic["running"] = True
    if c2.button("⏸ Stop", use_container_width=True): traffic["running"] = False
    traffic["rate"] = st.slider("Transactions per second", 1, 30, traffic["rate"])
    st.caption("Traffic is simulated. In production, transactions arrive through "
               "`POST /v1/transactions` or the webhook endpoint.")


@st.fragment(run_every=1.0)
def traffic_pump():
    if traffic["running"]:
        for _ in range(traffic["rate"]):
            e = next(traffic["stream"]); e["txn_id"] = f"L-{e['txn_id']}"
            eng.score(e, actor="demo")


@st.fragment(run_every=2.0)
def kpi_strip():
    m = eng.live_metrics(3600)
    open_cases = m["cases"].get("open", 0)
    cols = st.columns(5)
    for col, (label, value, color) in zip(cols, [
        ("Transactions, last hour", f"{m['transactions']:,}", "#58a6ff"),
        ("Alert rate", f"{m['alert_rate']:.2%}", "#f0a500"),
        ("Blocked", f"{m['block']:,}", "#ff5a4f"),
        ("Amount held", inr(m["blocked_amount"]), "#ff5a4f"),
        ("Open cases", f"{open_cases:,}", "#a371f7")]):
        col.markdown(f'<div class="kpi" style="--c:{color}"><div class="l">{label}</div>'
                     f'<div class="v">{value}</div></div>', unsafe_allow_html=True)
    st.caption(("🟢 live" if traffic["running"] else "⚪ traffic paused") + f" · model {m['model_version']}")


def open_case(case_id):
    st.session_state.case_id = case_id
    st.session_state.goto = "Investigation"


def _brief(v, limit=150):
    if isinstance(v, dict):
        v = ", ".join(f"{k}={_brief(x, 40)}" for k, x in v.items())
    elif isinstance(v, list):
        v = ", ".join(_brief(x, 40) for x in v) or "none"
    v = str(v)
    return v if len(v) <= limit else v[:limit - 1] + "…"


def render_trace(trace):
    """The investigation agent's tool calls as a step timeline: tool, latency, input and output."""
    steps = []
    for s in trace:
        kind = "notify" if s["tool"].startswith("notify_") else "decide" if s["tool"] == "assess_priority" else ""
        ms = "" if s["ms"] is None else f"{s['ms']:.2f} ms"
        steps.append(f'<div class="step {kind}"><div class="n">{s["step"]}</div>'
                     f'<div class="t">{html.escape(s["tool"])}</div><div class="ms">{ms}</div>'
                     f'<div class="io"><b>in</b> {html.escape(_brief(s["input"]))}<br>'
                     f'<b>out</b> {html.escape(_brief(s["output"]))}</div></div>')
    st.markdown(f'<div class="trace">{"".join(steps)}</div>', unsafe_allow_html=True)


traffic_pump()
kpi_strip()


# ── pages ────────────────────────────────────────────────────────────────────
def page_operations():
    @st.fragment(run_every=2.0)
    def feed():
        rows = eng.conn.execute("SELECT txn_id, created_at, user_id, amount, category, city, channel, score, decision "
                                "FROM transactions ORDER BY created_at DESC LIMIT 25").fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        if df.empty:
            st.info("No transactions yet. Press ▶ Start in the sidebar."); return
        df["time"] = pd.to_datetime(df.created_at, unit="s").dt.tz_localize("UTC").dt.tz_convert("Asia/Kolkata").dt.strftime("%H:%M:%S")
        df["amount"] = df.amount.map(inr)
        df["category"] = df.category.str.replace("_", " ")
        st.dataframe(df[["time", "txn_id", "user_id", "amount", "category", "city", "channel", "score", "decision"]],
                     hide_index=True, use_container_width=True, height=560,
                     column_config={"score": st.column_config.ProgressColumn("Risk", min_value=0, max_value=1, format="%.3f")})

    @st.fragment(run_every=5.0)
    def trend():
        rows = eng.conn.execute("SELECT CAST(created_at/60 AS INT)*60 AS minute, decision, COUNT(*) n FROM transactions "
                                "WHERE created_at >= ? GROUP BY minute, decision", (time.time() - 1800,)).fetchall()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows]).pivot_table(index="minute", columns="decision", values="n", fill_value=0)
            df.index = pd.to_datetime(df.index, unit="s").tz_localize("UTC").tz_convert("Asia/Kolkata")
            st.bar_chart(df[[c for c in ("REVIEW", "BLOCK") if c in df]], height=220,
                         color=[DECISION_COLOR[c] for c in ("REVIEW", "BLOCK") if c in df])

    left, right = st.columns([2.2, 1])
    with left:
        st.subheader("Live transactions"); feed()
    with right:
        st.subheader("Alerts per minute"); trend()
        st.subheader("Most urgent cases")
        for c in eng.list_cases("open", 6):
            st.button(f"{PRIORITY_ICON[c['priority']]} {inr(c['amount'])} · {c['city']} · {c['decision']}",
                      key=f"u{c['case_id']}", on_click=open_case, args=(c["case_id"],), use_container_width=True)
        st.caption("Opening a case takes you to Investigation.")


def page_cases():
    status = st.segmented_control("Status", ["open", "confirmed_fraud", "false_positive"], default="open")
    cases = eng.list_cases(status or "open", 200)
    st.caption(f"{len(cases)} case(s), most urgent first")
    for c in cases:
        a, b, cc, d, e = st.columns([0.5, 1.4, 1.6, 1.2, 1])
        a.markdown(PRIORITY_ICON[c["priority"]])
        b.markdown(f"**{inr(c['amount'])}** · {c['decision']}")
        cc.markdown(f"{c['user_id']} · {c['city']}")
        d.markdown(f"<span class='muted'>{time.strftime('%d %b %H:%M', time.localtime(c['created_at']))}</span>",
                   unsafe_allow_html=True)
        e.button("Open", key=f"c{c['case_id']}", on_click=open_case, args=(c["case_id"],))


def page_investigation():
    cid = st.session_state.get("case_id")
    if not cid:
        st.info("Pick a case from Operations or the Case queue."); return
    c = eng.get_case(cid); t = c["transaction"]; r = t["reasons"]
    col = DECISION_COLOR[t["decision"]]
    head = {"BLOCK": "Payment held. Contact the customer before release.",
            "REVIEW": "Payment processed. Review within 2 hours."}.get(t["decision"], "Allowed.")
    st.markdown(f"""<div class="banner" style="--c:{col}">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:1rem">
        <div><div class="mono" style="color:{col};font-size:1.6rem;font-weight:600">{t['decision']} · {PRIORITY_ICON[c['priority']]} {c['priority']} priority</div>
        <div style="font-size:1.05rem;margin-top:.2rem">{head}</div>
        <div class="muted mono">Case {cid} · {t['txn_id']} · {t['user_id']} · model {t['model_version']} · status {c['status']}</div></div>
        <div style="text-align:right"><div class="mono" style="font-size:1.6rem;font-weight:600">{inr(t['amount'])}</div>
        <div class="muted">{t.get('payee') if t['category'] == 'p2p_transfer' and t.get('payee') else t['merchant']} · {t['city']} · {t['channel'].upper()}</div></div>
      </div></div>""", unsafe_allow_html=True)

    if r.get("policy_override"):
        st.info(r["policy_override"])
    if r.get("strength") == "single" and t["decision"] == "REVIEW":
        st.warning("Only one weak signal. This is likely a false positive: verify before any customer impact.")

    left, right = st.columns([1.35, 1])
    with left:
        st.subheader("What happened")
        for x in r.get("risk", []):
            st.markdown(f"""<div class="card"><h4>{x['title']}</h4>
              <div class="pair"><div><small>This payment</small>{x['observed']}</div>
              <div><small>Normal for this customer</small>{x['normal']}</div></div>
              <div class="muted">{x['detail']}</div></div>""", unsafe_allow_html=True)
        if r.get("reassuring"):
            st.markdown(f"""<div class="card" style="--c:#3fb950"><h4>Reassuring</h4>
              <div class="muted">{' · '.join(r['reassuring'])}</div></div>""", unsafe_allow_html=True)
        st.subheader("Model contributions")
        contrib = pd.Series(t["contributions"]).sort_values()
        contrib = contrib[contrib.abs() > 0.05]
        st.bar_chart(contrib.rename("log-odds"), horizontal=True, height=320, color="#f0a500")
        st.caption("Exact TreeSHAP values from LightGBM. Positive pushes towards fraud.")
    with right:
        st.subheader("Recommended actions")
        for a in c["summary"]["actions"]:
            st.markdown(f"- {a}")
        st.subheader("Policy")
        for p in c["policy_refs"]:
            st.markdown(f"**{p['id']}** {p['text']}")
        st.subheader("Customer message")
        st.code(customer_message(t, t["decision"], r), language=None, wrap_lines=True)
        st.subheader("Agent trace")
        render_trace(c["trace"])
        if c["status"] == "open":
            st.subheader("Resolve")
            with st.form(f"resolve{cid}"):
                analyst = st.text_input("Analyst", value=st.session_state.get("analyst", ""))
                notes = st.text_area("Notes", placeholder="e.g. customer confirmed on call")
                f1, f2 = st.columns(2)
                fraud = f1.form_submit_button("Confirm fraud", type="primary", use_container_width=True)
                legit = f2.form_submit_button("False positive", use_container_width=True)
            if (fraud or legit) and not analyst.strip():
                st.error("Enter the analyst name for the audit trail.")
            elif fraud or legit:
                st.session_state.analyst = analyst
                eng.resolve_case(cid, bool(fraud), analyst.strip(), notes)
                st.success("Resolved. The label will be used in the next retraining run."); st.rerun()
        else:
            st.success(f"Resolved as {c['status'].replace('_', ' ')} by {c['assignee']}. {c['resolution_notes'] or ''}")

    st.subheader(f"Recent activity for {t['user_id']}")
    h = pd.DataFrame(eng.user_history(t["user_id"], 15))
    h["time"] = pd.to_datetime(h.ts, unit="s").dt.tz_localize("UTC").dt.tz_convert("Asia/Kolkata").dt.strftime("%d %b %H:%M")
    h["amount"] = h.amount.map(inr)
    st.dataframe(h[["time", "txn_id", "amount", "category", "payee", "city", "device_id", "score", "decision", "label"]],
                 hide_index=True, use_container_width=True)


def page_agent():
    st.caption("Every REVIEW or BLOCK opens a case and the investigation agent works it: transaction, customer "
               "history, policy lookup, priority, notifications. Each step is shown as it was recorded.")
    actors = [r[0] for r in eng.conn.execute("SELECT DISTINCT actor FROM audit_log WHERE action='case_opened'")]
    triggers = st.segmented_control("Triggered by", ["all", *sorted(a for a in actors if a)], default="all")

    @st.fragment(run_every=2.0)
    def activity():
        hour = eng.recent_investigations(1000, since=time.time() - 3600)
        a, b, c, d = st.columns(4)
        a.metric("Investigations, last hour", len(hour))
        b.metric("Critical or high", sum(r["priority"] in ("critical", "high") for r in hour))
        c.metric("Notifications sent", sum(len(r["notified"]) for r in hour))
        ms = sorted(r["agent_ms"] for r in hour)
        d.metric("Agent time, median", f"{ms[len(ms) // 2]:.1f} ms" if ms else "n/a")

        feed = [r for r in eng.recent_investigations(40) if triggers in (None, "all") or r["actor"] == triggers][:12]
        if not feed:
            st.info("No investigations yet. Start demo traffic, score a payment through the API, "
                    "or have an MCP client call score_transaction."); return
        for i, r in enumerate(feed):
            when = time.strftime("%H:%M:%S", time.localtime(r["created_at"]))
            title = (f"{PRIORITY_ICON[r['priority']]} Case {r['case_id']} · {r['decision']} · {inr(r['amount'])} · "
                     f"{r['city']} · {r['priority']} · {len(r['trace'])} steps in {r['agent_ms']:.1f} ms · "
                     f"{when} via {r['actor'] or 'unknown'}")
            with st.expander(title, expanded=(i == 0)):
                render_trace(r["trace"])
                if st.button("Open case", key=f"a{r['case_id']}"):   # inside a fragment: rerun the whole app
                    open_case(r["case_id"]); st.rerun()

    activity()


def page_monitoring():
    st.subheader("Feature drift (PSI against the training reference)")
    d = eng.drift()
    if not d["ready"]:
        st.info(f"Need {d['needed']} scored transactions on this model; have {d['rows']}.")
    else:
        a, b, c = st.columns(3)
        a.metric("Score PSI", d["score_psi"], d["score_status"], delta_color="off")
        b.metric("Critical features", d["critical_features"])
        c.metric("Retraining", "recommended" if d["retrain_recommended"] else "not needed")
        df = pd.DataFrame(d["features"]).set_index("feature")
        st.bar_chart(df["psi"], horizontal=True, height=420, color="#58a6ff")
        st.caption("PSI < 0.10 stable · 0.10–0.25 warning · > 0.25 critical (policy FRF-3.1).")

    st.subheader("Model versions")
    rows = [{"version": v["version"], "PR-AUC": v["metrics"]["pr_auc"],
             "block precision": v["metrics"]["block"]["precision"], "block recall": v["metrics"]["block"]["recall"],
             "review recall": v["metrics"]["review"]["recall"],
             "decision": v["metrics"].get("comparison", {}).get("decision", "initial"),
             "serving": "✅" if v["version"] == eng.bundle.version else ""} for v in eng.registry.versions()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    labels = eng.conn.execute("SELECT COUNT(*) FROM transactions WHERE label IS NOT NULL").fetchone()[0]
    st.caption(f"{labels} analyst label(s) available for retraining.")
    if st.button("Run champion/challenger retraining"):
        from sentinelai.retrain import retrain
        with st.spinner("Training challenger and comparing with champion…"):
            out = retrain(eng.settings, n_events=150_000)
        (st.success if out["decision"] == "PROMOTED" else st.warning)(f"{out['decision']}: {out['reason']}")
        if out["decision"] == "PROMOTED":
            eng.reload_model()

    bench = Path(__file__).resolve().parent.parent / "benchmark" / "results.json"
    if bench.exists():
        st.subheader("Public benchmark (ULB credit-card fraud, time-ordered split)")
        b = json.loads(bench.read_text())
        st.dataframe(pd.DataFrame([{"model": k, "PR-AUC": v["pr_auc"], "ROC-AUC": v["roc_auc"],
                                    "block precision": v["block"]["precision"], "block recall": v["block"]["recall"],
                                    "review recall": v["review"]["recall"]} for k, v in b["models"].items()]),
                     hide_index=True, use_container_width=True)
        st.caption(f"{b['rows']:,} real transactions, {b['test_frauds']} frauds in the test period.")


def page_policy():
    st.subheader("Ask the policy documents")
    st.caption("Answers come only from the Markdown files in `policies/` and always cite a clause.")
    quick = ["When do we file an STR?", "What if a card is used in two cities quickly?",
             "Is the customer refunded while we investigate?", "What PSI triggers retraining?"]
    cols = st.columns(len(quick))
    for col, q in zip(cols, quick):
        if col.button(q, use_container_width=True):
            st.session_state.policy_q = q
    with st.form("ask", clear_on_submit=False):
        q = st.text_input("Question", value=st.session_state.get("policy_q", ""))
        asked = st.form_submit_button("Search", type="primary")
    q = q if asked else st.session_state.get("policy_q")
    if q:
        a = eng.ask_policy(q)
        if a["abstained"]:
            st.warning(a["message"])
        else:
            (st.success if a["confidence"] == "high" else st.warning)(a["answer"])
            for h in a["citations"]:
                st.caption(f"{h['id']} · {h['document']} · similarity {h['score']}")


def page_connect():
    s = eng.settings
    st.subheader("REST API")
    st.code("python -m sentinelai serve   # then open http://localhost:8000/docs", language="bash")
    st.code("""curl -X POST http://localhost:8000/v1/transactions \\
  -H "X-API-Key: $SENTINEL_API_KEY" -H "Content-Type: application/json" \\
  -d '{"user_id":"U00042","amount":84000,"city":"Kolkata","device_id":"new-phone","category":"electronics","channel":"upi"}'""",
            language="bash")
    st.subheader("MCP (Claude Desktop, Claude Code or any MCP client)")
    st.code(json.dumps({"mcpServers": {"sentinelai": {
        "command": "python", "args": ["-m", "sentinelai", "mcp"],
        "cwd": str(Path(__file__).resolve().parent.parent),
        "env": {"SENTINEL_DB_PATH": str(Path(s.db_path).resolve()),
                "SENTINEL_MODEL_DIR": str(Path(s.model_dir).resolve())}}}}, indent=2), language="json")
    st.caption("Tools: score_transaction, get_case, list_open_cases, resolve_case, get_user_history, "
               "lookup_policy, check_drift, live_metrics. They share this database, so an agent sees the same cases you do.")


{"Operations": page_operations, "Case queue": page_cases, "Investigation": page_investigation,
 "Agent activity": page_agent,
 "Monitoring & model": page_monitoring, "Policy assistant": page_policy,
 "Connect (API & MCP)": page_connect}[page]()
