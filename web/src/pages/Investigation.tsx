import {
  ArrowLeft, BadgeCheck, Bot, CheckCircle2, ChevronRight, CircleAlert, Gavel, Info, MapPin, Smartphone, User, XOctagon,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { Contributions, RiskGauge } from "../components/charts";
import { TraceTimeline } from "../components/Trace";
import { Button, DecisionBadge, Empty, Panel, PriorityPill, Skeleton, StatusPill, cx } from "../components/ui";
import { ApiError, useCase, useResolve } from "../lib/api";
import { DECISION_COLOR, clock, dateTime, human, inr, num } from "../lib/format";
import type { CaseDetail, HistoryRow } from "../lib/types";

const HEADLINE = {
  BLOCK: "Payment held. Contact the customer before release.",
  REVIEW: "Payment processed. Review within 2 hours.",
  ALLOW: "Allowed.",
};

export function Investigation() {
  const id = Number(useParams().id);
  const { data: c, error, isLoading } = useCase(Number.isFinite(id) ? id : null);

  if (error) {
    return (
      <Empty icon={<CircleAlert size={28} />} title={error instanceof ApiError && error.status === 404 ? `Case #${id} does not exist` : "Could not load this case"}>
        <Link to="/cases" className="text-saffron">Back to the queue</Link>
      </Empty>
    );
  }
  if (isLoading || !c) {
    return (
      <div className="mx-auto max-w-[1500px] space-y-3">
        <Skeleton className="h-48 rounded-2xl" />
        <div className="grid grid-cols-12 gap-3"><Skeleton className="col-span-7 h-96" /><Skeleton className="col-span-5 h-96" /></div>
      </div>
    );
  }
  const t = c.transaction;
  const r = t.reasons;

  return (
    <div className="mx-auto max-w-[1500px] animate-fade-up">
      <div className="mb-3 flex items-center gap-2 text-[12.5px] text-dim">
        <Link to="/cases" className="flex items-center gap-1 hover:text-fg"><ArrowLeft size={13} /> Case queue</Link>
        <ChevronRight size={12} className="text-faint" />
        <span className="num text-fg">Case #{c.case_id}</span>
      </div>

      <Verdict c={c} />

      {r.policy_override && (
        <Banner icon={<Gavel size={15} />} color="var(--color-info)">{r.policy_override}</Banner>
      )}
      {r.strength === "single" && t.decision === "REVIEW" && (
        <Banner icon={<Info size={15} />} color="var(--color-review)">
          Only one weak signal. This is likely a false positive: verify before any customer impact.
        </Banner>
      )}

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-12">
        <div className="space-y-3 xl:col-span-7">
          <Panel eyebrow="Evidence" title="What happened, against what is normal for this customer">
            <div className="space-y-2.5">
              {r.risk.map((x) => (
                <div key={x.code} className="relative overflow-hidden rounded-xl border border-line bg-panel-2/60 p-3.5 pl-4">
                  <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: `linear-gradient(var(--color-block), var(--color-saffron))` }} />
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-[14px] font-semibold">{x.title}</h3>
                    <span className="num rounded-md bg-block/10 px-1.5 py-0.5 text-[11px] text-block">+{x.weight.toFixed(2)} log-odds</span>
                  </div>
                  <div className="mt-2.5 grid grid-cols-2 gap-2">
                    <div className="rounded-lg bg-ink/70 px-3 py-2">
                      <div className="label text-[9.5px]">This payment</div>
                      <div className="num mt-0.5 text-[13px] text-fg">{x.observed}</div>
                    </div>
                    <div className="rounded-lg bg-ink/70 px-3 py-2">
                      <div className="label text-[9.5px]">Normal for this customer</div>
                      <div className="num mt-0.5 text-[13px] text-dim">{x.normal}</div>
                    </div>
                  </div>
                  <p className="mt-2 text-[12.5px] leading-relaxed text-dim">{x.detail}</p>
                </div>
              ))}
              {r.risk.length === 0 && <p className="text-[13px] text-dim">No single strong reason: a combination of weak signals.</p>}
              {r.reassuring.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <span className="label">Reassuring</span>
                  {r.reassuring.map((x) => (
                    <span key={x} className="inline-flex items-center gap-1 rounded-full bg-allow/10 px-2.5 py-1 text-[12px] text-allow ring-1 ring-allow/25 ring-inset">
                      <CheckCircle2 size={12} /> {x}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </Panel>

          <Panel eyebrow="Explainability" title="Why the model scored it this way" action={<span className="text-[11px] text-faint">exact TreeSHAP · LightGBM</span>}>
            <Contributions contributions={t.contributions} features={t.features} />
          </Panel>

          <CustomerPanel c={c} />

          <Panel eyebrow="Policy" title="Clauses the agent cited">
            <div className="space-y-2">
              {c.policy_refs?.map((p) => (
                <div key={p.id} className="rounded-lg border border-line bg-panel-2/60 px-3 py-2.5">
                  <div className="flex items-center justify-between">
                    <span className="num rounded bg-agent/15 px-1.5 py-0.5 text-[11px] font-semibold text-agent">{p.id}</span>
                    <span className="text-[11px] text-faint">{p.document}</span>
                  </div>
                  <p className="mt-1.5 text-[12.5px] leading-relaxed text-dim">{p.text}</p>
                </div>
              ))}
              {!c.policy_refs?.length && <p className="text-[13px] text-dim">No clause matched.</p>}
            </div>
          </Panel>
        </div>

        <div className="space-y-3 xl:col-span-5">
          <Resolve c={c} />

          <Panel eyebrow="Investigation agent" title="Case summary" action={<Bot size={15} className="text-agent" />}>
            <p className="text-[13px] leading-relaxed text-dim">{c.summary?.text}</p>
            <div className="label mt-4 mb-2">Recommended actions</div>
            <ol className="space-y-1.5">
              {c.summary?.actions.map((a, i) => (
                <li key={i} className="flex gap-2.5 text-[13px]">
                  <span className="num mt-px flex size-5 shrink-0 items-center justify-center rounded-full bg-agent/15 text-[10.5px] text-agent">{i + 1}</span>
                  <span className="leading-relaxed">{a}</span>
                </li>
              ))}
            </ol>
          </Panel>

          <Panel eyebrow="Agent trace" title="Every tool call, as recorded">
            {c.trace && <TraceTimeline trace={c.trace} replayable />}
          </Panel>

          <Panel eyebrow="Customer notification" title={t.decision === "BLOCK" ? "SMS sent to the customer" : "Message if the customer is contacted"}>
            <Phone text={c.customer_message} sent={c.alerts.some((a) => a.audience === "customer")} />
          </Panel>

          {c.audit.length > 0 && (
            <Panel eyebrow="Audit trail" title="What happened to this case">
              <ol className="space-y-2">
                {c.audit.map((a, i) => (
                  <li key={i} className="flex items-baseline gap-3 text-[12.5px]">
                    <span className="num shrink-0 text-faint">{dateTime(a.ts)}</span>
                    <span><b className="font-medium">{a.actor}</b> <span className="text-dim">{human(a.action)}</span>
                      {"status" in a.detail && <span className="text-dim"> as {human(String(a.detail.status))}</span>}</span>
                  </li>
                ))}
              </ol>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

function Verdict({ c }: { c: CaseDetail }) {
  const t = c.transaction;
  const col = DECISION_COLOR[t.decision];
  const to = t.category === "p2p_transfer" && t.payee ? t.payee : t.merchant;
  return (
    <section className="relative overflow-hidden rounded-2xl border p-5 md:p-6"
      style={{ borderColor: `color-mix(in oklab, ${col} 35%, var(--color-line))`, background: `radial-gradient(800px 300px at 0% 0%, color-mix(in oklab, ${col} 14%, transparent), transparent 70%), var(--color-panel)` }}>
      <div className="pointer-events-none absolute -top-24 -right-24 size-72 rounded-full opacity-20 blur-3xl" style={{ background: col }} />
      <div className="relative flex flex-wrap items-center justify-between gap-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <DecisionBadge d={t.decision} size="lg" />
            <PriorityPill p={c.priority} />
            <StatusPill s={c.status} />
          </div>
          <h1 className="mt-3 text-[22px] font-semibold tracking-tight md:text-[26px]">{HEADLINE[t.decision]}</h1>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-dim">
            <span className="flex items-center gap-1.5"><User size={13} /> <span className="font-mono">{t.user_id}</span></span>
            <span className="flex items-center gap-1.5"><MapPin size={13} /> {t.city}</span>
            <span className="flex items-center gap-1.5"><Smartphone size={13} /> <span className="font-mono">{t.device_id}</span></span>
            <span className="num">{t.txn_id}</span>
            <span>model <span className="num">{t.model_version}</span></span>
            <span>{dateTime(t.created_at)} IST</span>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-right">
            <div className="num text-[34px] leading-none font-semibold md:text-[40px]">{inr(t.amount)}</div>
            <div className="mt-2 text-[13px] text-dim">{to} · {human(t.category)} · <span className="uppercase">{t.channel}</span></div>
          </div>
          <RiskGauge score={t.score} thresholds={c.thresholds} size={190} />
        </div>
      </div>
    </section>
  );
}

function Banner({ icon, color, children }: { icon: React.ReactNode; color: string; children: React.ReactNode }) {
  return (
    <div className="mt-3 flex items-center gap-2.5 rounded-xl border px-4 py-2.5 text-[13px]"
      style={{ color, borderColor: `color-mix(in oklab, ${color} 30%, transparent)`, background: `color-mix(in oklab, ${color} 7%, transparent)` }}>
      {icon}<span className="text-fg">{children}</span>
    </div>
  );
}

function Resolve({ c }: { c: CaseDetail }) {
  const [analyst, setAnalyst] = useState(() => { try { return localStorage.getItem("sentinel.analyst") ?? ""; } catch { return ""; } });
  const [notes, setNotes] = useState("");
  const m = useResolve(c.case_id);
  const submit = (is_fraud: boolean) => {
    if (!analyst.trim()) return;
    try { localStorage.setItem("sentinel.analyst", analyst.trim()); } catch { /* ignore */ }
    m.mutate({ is_fraud, analyst: analyst.trim(), notes });
  };

  if (c.status !== "open") {
    const fraud = c.status === "confirmed_fraud";
    return (
      <div className={cx("rounded-2xl border p-4", fraud ? "border-block/30 bg-block/5" : "border-allow/30 bg-allow/5")}>
        <div className="flex items-center gap-2.5">
          {fraud ? <XOctagon className="text-block" size={20} /> : <BadgeCheck className="text-allow" size={20} />}
          <div>
            <div className="font-semibold">Resolved as {human(c.status)}</div>
            <div className="text-[12.5px] text-dim">by {c.assignee} · {dateTime(c.updated_at)} IST</div>
          </div>
        </div>
        {c.resolution_notes && <p className="mt-3 rounded-lg bg-ink/50 px-3 py-2 text-[13px] text-dim">“{c.resolution_notes}”</p>}
        <p className="mt-3 text-[12px] text-faint">The label feeds the next champion/challenger retraining run.</p>
      </div>
    );
  }
  return (
    <div className="relative overflow-hidden rounded-2xl border border-saffron/30 bg-panel p-4 shadow-[0_0_60px_-30px_var(--color-saffron)]">
      <div className="label text-saffron">Your call</div>
      <div className="mt-1 text-[15px] font-semibold">Resolve this case</div>
      <div className="mt-3 grid gap-2">
        <input value={analyst} onChange={(e) => setAnalyst(e.target.value)} placeholder="Analyst name (for the audit trail)"
          className="h-9 rounded-lg border border-line-2 bg-ink px-3 text-[13px] outline-none placeholder:text-faint focus:border-saffron/60" />
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="Notes, e.g. customer confirmed on call"
          className="resize-none rounded-lg border border-line-2 bg-ink px-3 py-2 text-[13px] outline-none placeholder:text-faint focus:border-saffron/60" />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Button variant="danger" disabled={!analyst.trim() || m.isPending} onClick={() => submit(true)}><XOctagon size={14} /> Confirm fraud</Button>
        <Button variant="success" disabled={!analyst.trim() || m.isPending} onClick={() => submit(false)}><BadgeCheck size={14} /> False positive</Button>
      </div>
      {m.error && <p className="mt-2 text-[12.5px] text-block">{m.error.message}</p>}
      {c.transaction.decision === "BLOCK" && (
        <p className="mt-2.5 text-[11.5px] text-faint">Marking a blocked payment as a false positive releases it and tells the customer (CP-3.1).</p>
      )}
    </div>
  );
}

function Phone({ text, sent }: { text: string; sent: boolean }) {
  return (
    <div className="mx-auto w-full max-w-[300px] rounded-[28px] border border-line-2 bg-ink p-2.5 shadow-inner">
      <div className="rounded-[20px] bg-panel-2 px-3 pt-2 pb-4">
        <div className="mx-auto mb-3 h-1 w-14 rounded-full bg-line-2" />
        <div className="mb-2 text-center text-[10.5px] text-faint">SENTINL · SMS</div>
        <div className="max-w-[92%] rounded-2xl rounded-tl-md bg-panel-3 px-3 py-2 text-[12.5px] leading-relaxed">{text}</div>
        <div className="mt-1.5 text-[10.5px] text-faint">{sent ? "Delivered by the agent" : "Not sent: REVIEW cases contact the customer only if needed"}</div>
      </div>
    </div>
  );
}

function CustomerPanel({ c }: { c: CaseDetail }) {
  const p = c.profile;
  const t = c.transaction;
  return (
    <Panel eyebrow="Customer" title={<span className="font-mono">{t.user_id}</span>}>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          ["Home city", p.home_city ?? "unknown"],
          ["Typical payment", inr(p.typical_amount)],
          ["Payments seen", num(p.transactions)],
          ["Devices · cities", `${p.devices} · ${p.cities}`],
        ].map(([k, v]) => (
          <div key={k} className="rounded-lg bg-panel-2/70 px-3 py-2">
            <div className="label text-[9.5px]">{k}</div>
            <div className="num mt-0.5 text-[13.5px]">{v}</div>
          </div>
        ))}
      </div>
      <HistoryChart rows={c.history} current={t.txn_id} typical={p.typical_amount} />
      <div className="mt-2 max-h-72 overflow-auto">
        <table className="w-full text-[12px]">
          <thead className="sticky top-0 bg-panel">
            <tr className="text-left">{["When", "Amount", "Category", "City", "Device", "Decision", "Label"].map((h) => <th key={h} className="label border-b border-line px-2 py-1.5">{h}</th>)}</tr>
          </thead>
          <tbody>
            {c.history.map((h) => (
              <tr key={h.txn_id} className={cx("border-b border-line/50", h.txn_id === t.txn_id && "bg-saffron/5")}>
                <td className="num px-2 py-1.5 text-faint">{dateTime(h.ts)}</td>
                <td className="num px-2 py-1.5">{inr(h.amount)}</td>
                <td className="px-2 py-1.5 text-dim">{human(h.category)}</td>
                <td className="px-2 py-1.5">{h.city}</td>
                <td className="max-w-[120px] truncate px-2 py-1.5 font-mono text-[11px] text-dim">{h.device_id}</td>
                <td className="px-2 py-1.5"><DecisionBadge d={h.decision} /></td>
                <td className="px-2 py-1.5 text-[11.5px]">{h.label == null ? <span className="text-faint">—</span> : h.label ? <span className="text-block">fraud</span> : <span className="text-allow">legit</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

/** Amounts over time on a log scale, with the customer's typical spend as a baseline. */
function HistoryChart({ rows, current, typical }: { rows: HistoryRow[]; current: string; typical: number }) {
  if (rows.length < 2) return null;
  const pts = [...rows].sort((a, b) => a.ts - b.ts);
  const W = 640, H = 120, P = 12;
  const maxA = Math.log10(Math.max(...pts.map((p) => p.amount), typical) * 1.4);
  const minA = Math.log10(Math.max(1, Math.min(...pts.map((p) => p.amount), typical) / 1.6));
  const idx = new Map(pts.map((p, i) => [p.txn_id, i]));   // evenly spaced: bursts and gaps both stay readable
  const x = (id: string) => P + (idx.get(id)! / (pts.length - 1)) * (W - 2 * P);
  const y = (a: number) => H - P - ((Math.log10(Math.max(a, 1)) - minA) / (maxA - minA)) * (H - 2 * P);
  return (
    <div className="mt-3 rounded-lg border border-line bg-ink/40 px-2 pt-2">
      <div className="flex justify-between px-1 text-[10.5px] text-faint"><span>Recent payments, log scale</span><span>— typical {inr(typical)}</span></div>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-[120px] w-full" preserveAspectRatio="none">
        <line x1={P} x2={W - P} y1={y(typical)} y2={y(typical)} stroke="var(--color-faint)" strokeDasharray="4 4" />
        <path d={pts.map((p, i) => `${i ? "L" : "M"}${x(p.txn_id)},${y(p.amount)}`).join("")} fill="none" stroke="var(--color-line-2)" strokeWidth="1" />
        {pts.map((p) => {
          const cur = p.txn_id === current;
          return (
            <g key={p.txn_id}>
              {cur && <circle cx={x(p.txn_id)} cy={y(p.amount)} r="9" fill="none" stroke={DECISION_COLOR[p.decision]} strokeWidth="1.5" opacity="0.7" />}
              <circle cx={x(p.txn_id)} cy={y(p.amount)} r={cur ? 4.5 : 3} fill={DECISION_COLOR[p.decision]}>
                <title>{`${inr(p.amount)} · ${p.city} · ${clock(p.ts)}`}</title>
              </circle>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

