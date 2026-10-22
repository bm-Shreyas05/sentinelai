import { ArrowRight, Dice5, FlaskConical, Loader2, Zap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { RiskGauge } from "../components/charts";
import { Button, DecisionBadge, Panel, cx } from "../components/ui";
import { api, scoreTransaction, useFeed, useModel } from "../lib/api";
import { human, inr } from "../lib/format";
import type { HistoryRow, ScoreResult } from "../lib/types";
import { PageHeader } from "./Command";

const CITIES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Kochi", "Chandigarh", "Nagpur", "Bhopal"];
const CATEGORIES = ["grocery", "restaurant", "fuel", "online_shopping", "electronics", "travel", "jewellery", "p2p_transfer", "gaming", "crypto", "atm", "utilities"];
const CHANNELS = ["upi", "card", "netbanking", "wallet"] as const;
const FAR: Record<string, string> = { Kolkata: "Mumbai", Mumbai: "Kolkata", Delhi: "Chennai", Chennai: "Delhi", Bengaluru: "Delhi", Kochi: "Delhi" };

interface Profile { user_id: string; home: string; device: string; typical: number }
type Txn = { user_id: string; amount: number; city: string; device_id: string; category: string; channel: string; payee?: string; merchant?: string; ts?: number };

function profileOf(user_id: string, h: HistoryRow[]): Profile {
  const count = (k: (r: HistoryRow) => string) => {
    const m = new Map<string, number>();
    h.forEach((r) => m.set(k(r), (m.get(k(r)) ?? 0) + 1));
    return [...m.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  };
  const amounts = h.map((r) => r.amount).sort((a, b) => a - b);
  return { user_id, home: count((r) => r.city) ?? "Mumbai", device: count((r) => r.device_id) ?? `${user_id}-phone`, typical: amounts[Math.floor(amounts.length / 2)] ?? 1500 };
}

const SCENARIOS: { id: string; name: string; blurb: string; steps: (p: Profile) => Txn[] }[] = [
  { id: "normal", name: "Everyday purchase", blurb: "Usual amount, home city, known phone.",
    steps: (p) => [{ user_id: p.user_id, amount: Math.round(p.typical * 0.9), city: p.home, device_id: p.device, category: "grocery", channel: "upi" }] },
  { id: "scam", name: "UPI scam transfer", blurb: "Victim's own phone and city, large transfer to a collector UPI ID.",
    steps: (p) => [{ user_id: p.user_id, amount: Math.round(p.typical * 9), city: p.home, device_id: p.device, category: "p2p_transfer", channel: "upi", payee: "COL017@upi" }] },
  { id: "takeover", name: "Account takeover", blurb: "New device, far-away city, big electronics purchase.",
    steps: (p) => [{ user_id: p.user_id, amount: Math.round(p.typical * 18), city: FAR[p.home] ?? "Kolkata", device_id: `X-${Date.now() % 1e6}`, category: "electronics", channel: "netbanking" }] },
  { id: "travel", name: "Cloned card", blurb: "A home purchase, then the same card 900+ km away 20 minutes later.",
    steps: (p) => {
      const now = Date.now() / 1000;
      return [
        { user_id: p.user_id, amount: Math.round(p.typical), city: p.home, device_id: p.device, category: "grocery", channel: "card", ts: now },
        { user_id: p.user_id, amount: Math.round(p.typical * 5), city: FAR[p.home] ?? "Kolkata", device_id: `POS-${Date.now() % 1e5}`, category: "jewellery", channel: "card", ts: now + 1200 },
      ];
    } },
  { id: "testing", name: "Card testing", blurb: "Five tiny payments in a minute from a new device, then the big one.",
    steps: (p) => {
      const now = Date.now() / 1000, dev = `X-${Date.now() % 1e6}`;
      return [
        ...Array.from({ length: 5 }, (_, i) => ({ user_id: p.user_id, amount: 20 + i * 15, city: p.home, device_id: dev, category: "online_shopping", channel: "card", ts: now + i * 12 })),
        { user_id: p.user_id, amount: Math.round(p.typical * 7), city: p.home, device_id: dev, category: "electronics", channel: "card", ts: now + 90 },
      ];
    } },
  { id: "mule", name: "Mule ring device", blurb: "Transfer from a device shared across many accounts.",
    steps: (p) => [{ user_id: p.user_id, amount: 42000, city: p.home, device_id: "MULE003", category: "p2p_transfer", channel: "upi" }] },
];

export function Playground() {
  const { data: feed } = useFeed(60);
  const thresholds = useModel().data?.thresholds ?? { review: 0.5, block: 0.9 };
  const [profile, setProfile] = useState<Profile | null>(null);
  const [form, setForm] = useState<Txn>({ user_id: "", amount: 2500, city: "Mumbai", device_id: "", category: "online_shopping", channel: "upi" });
  const [results, setResults] = useState<{ txn: Txn; res?: ScoreResult; err?: string }[]>([]);
  const [busy, setBusy] = useState(false);

  const candidates = useMemo(() => [...new Set((feed ?? []).map((r) => r.user_id))], [feed]);

  const pick = async (uid?: string) => {
    const user = uid ?? candidates[Math.floor(Math.random() * candidates.length)];
    if (!user) return;
    const h = await api<HistoryRow[]>(`/v1/users/${encodeURIComponent(user)}/history?limit=50`);
    const p = profileOf(user, h);
    setProfile(p);
    setForm((f) => ({ ...f, user_id: p.user_id, city: p.home, device_id: p.device, amount: Math.round(p.typical) }));
  };

  useEffect(() => {
    if (!profile && candidates.length) pick(candidates[0]);
  }, [candidates]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (txns: Txn[]) => {
    setBusy(true);
    setResults([]);
    for (const txn of txns) {
      try {
        const res = await scoreTransaction(txn as unknown as Record<string, unknown>);
        setResults((r) => [...r, { txn, res }]);
      } catch (e) {
        setResults((r) => [...r, { txn, err: (e as Error).message }]);
      }
    }
    setBusy(false);
  };

  const last = results[results.length - 1]?.res;
  const set = <K extends keyof Txn>(k: K, v: Txn[K]) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader title="Score a payment" sub="Send a real request to POST /v1/transactions. Scenarios replay the fraud patterns the model was trained on against a real customer's history." />

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-12">
        <div className="space-y-3 xl:col-span-5">
          <Panel eyebrow="Customer" title={profile ? <span className="font-mono">{profile.user_id}</span> : "Pick a customer"}
            action={<Button onClick={() => pick()} disabled={!candidates.length}><Dice5 size={13} /> Another</Button>}>
            {profile && (
              <div className="grid grid-cols-3 gap-2 text-[12.5px]">
                {[["Home", profile.home], ["Usual device", profile.device], ["Typical", inr(profile.typical)]].map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-panel-2/70 px-3 py-2"><div className="label text-[9.5px]">{k}</div><div className="num mt-0.5 truncate">{v}</div></div>
                ))}
              </div>
            )}
          </Panel>

          <Panel eyebrow="Scenarios" title="Replay a fraud pattern">
            <div className="grid grid-cols-2 gap-2">
              {SCENARIOS.map((s) => (
                <button key={s.id} disabled={!profile || busy} onClick={() => profile && run(s.steps(profile))}
                  className="group rounded-xl border border-line bg-panel-2/50 p-3 text-left transition hover:border-saffron/40 hover:bg-panel-2 disabled:opacity-50">
                  <div className="flex items-center justify-between text-[13px] font-semibold">{s.name}<Zap size={13} className="text-faint group-hover:text-saffron" /></div>
                  <div className="mt-1 text-[11.5px] leading-snug text-dim">{s.blurb}</div>
                </button>
              ))}
            </div>
          </Panel>

          <Panel eyebrow="Custom" title="Build your own">
            <div className="grid grid-cols-2 gap-2.5 text-[12.5px]">
              <Field label="Customer"><input value={form.user_id} onChange={(e) => set("user_id", e.target.value)} className={input} /></Field>
              <Field label="Amount (₹)"><input type="number" min={1} value={form.amount} onChange={(e) => set("amount", Number(e.target.value))} className={input} /></Field>
              <Field label="City"><select value={form.city} onChange={(e) => set("city", e.target.value)} className={input}>{CITIES.map((c) => <option key={c}>{c}</option>)}</select></Field>
              <Field label="Device"><input value={form.device_id} onChange={(e) => set("device_id", e.target.value)} className={input} /></Field>
              <Field label="Category"><select value={form.category} onChange={(e) => set("category", e.target.value)} className={input}>{CATEGORIES.map((c) => <option key={c} value={c}>{human(c)}</option>)}</select></Field>
              <Field label="Rail">
                <div className="flex gap-1">{CHANNELS.map((c) => (
                  <button key={c} onClick={() => set("channel", c)} className={cx("flex-1 rounded-md border py-1.5 text-[11px] uppercase", form.channel === c ? "border-saffron/50 bg-saffron/10 text-saffron" : "border-line text-dim")}>{c}</button>
                ))}</div>
              </Field>
            </div>
            <Button variant="primary" className="mt-4 w-full py-2" disabled={busy || !form.user_id || !form.device_id || !(form.amount > 0)} onClick={() => run([form])}>
              {busy ? <Loader2 size={14} className="animate-spin" /> : <FlaskConical size={14} />} Score it
            </Button>
          </Panel>
        </div>

        <div className="space-y-3 xl:col-span-7">
          <Panel eyebrow="Result" title={last ? <span className="flex items-center gap-2">Decision <DecisionBadge d={last.decision} /></span> : "Run a scenario or score a custom payment"}>
            {!last && !busy && (
              <div className="flex flex-col items-center justify-center py-16 text-center text-dim">
                <FlaskConical size={36} className="text-faint" />
                <p className="mt-3 max-w-sm text-[13px]">Results show the decision, fraud probability, plain-English reasons and the case the agent opened.</p>
              </div>
            )}
            {last && (
              <div className="animate-fade-up">
                <div className="flex flex-wrap items-center gap-6">
                  <RiskGauge score={last.score} thresholds={thresholds} size={210} />
                  <div className="space-y-1.5 text-[13px]">
                    <div><span className="text-dim">Latency</span> <span className="num">{last.latency_ms.toFixed(1)} ms</span></div>
                    <div><span className="text-dim">Model</span> <span className="num">{last.model_version}</span></div>
                    {last.model_decision !== last.decision && <div className="text-info">Model said {last.model_decision}; policy downgraded it.</div>}
                    {last.case_id && (
                      <Link to={`/cases/${last.case_id}`} className="inline-flex items-center gap-1.5 font-medium text-saffron hover:underline">
                        Open case #{last.case_id} <ArrowRight size={13} />
                      </Link>
                    )}
                  </div>
                </div>
                <div className="mt-4 space-y-2">
                  {last.reasons.risk.map((x) => (
                    <div key={x.code} className="rounded-lg border border-line bg-panel-2/60 px-3 py-2.5">
                      <div className="text-[13px] font-semibold">{x.title}</div>
                      <div className="num mt-0.5 text-[12px] text-dim">{x.observed} <span className="text-faint">vs</span> {x.normal}</div>
                    </div>
                  ))}
                  {last.reasons.reassuring.length > 0 && <div className="text-[12.5px] text-allow">Reassuring: {last.reasons.reassuring.join(" · ")}</div>}
                </div>
              </div>
            )}
          </Panel>

          {results.length > 1 && (
            <Panel eyebrow="Sequence" title="Each payment in order">
              <ol className="space-y-1.5">
                {results.map((r, i) => (
                  <li key={i} className="grid grid-cols-[24px_1fr_auto_auto] items-center gap-3 rounded-lg bg-panel-2/50 px-3 py-2 text-[12.5px]">
                    <span className="num text-faint">{i + 1}</span>
                    <span className="truncate"><span className="num font-semibold">{inr(r.txn.amount)}</span> <span className="text-dim">· {r.txn.city} · {human(r.txn.category)} · {r.txn.device_id}</span></span>
                    <span className="num text-dim">{r.res?.score.toFixed(3) ?? ""}</span>
                    {r.res ? <DecisionBadge d={r.res.decision} /> : <span className="text-block">{r.err}</span>}
                  </li>
                ))}
              </ol>
            </Panel>
          )}

          <Panel eyebrow="Request" title="The exact call">
            <pre className="overflow-x-auto rounded-lg border border-line bg-ink p-3 font-mono text-[11.5px] leading-relaxed text-dim">
{`curl -X POST $SENTINEL_URL/v1/transactions \\
  -H "X-API-Key: $SENTINEL_API_KEY" -H "Content-Type: application/json" \\
  -d '${JSON.stringify(results[results.length - 1]?.txn ?? form)}'`}
            </pre>
          </Panel>
        </div>
      </div>
    </div>
  );
}

const input = "h-9 w-full rounded-lg border border-line-2 bg-ink px-2.5 text-[12.5px] outline-none focus:border-saffron/60";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="label mb-1 block text-[9.5px]">{label}</span>{children}</label>;
}
