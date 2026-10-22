import { BellRing, Bot, ChevronDown, Cpu, Siren, Timer } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { TraceStrip, TraceTimeline, toolMeta } from "../components/Trace";
import { DecisionBadge, Empty, Kpi, Panel, PriorityPill, Segmented, Skeleton, cx } from "../components/ui";
import { useInvestigations, useInvestigationsSince } from "../lib/api";
import { ago, clock, inr, num } from "../lib/format";
import type { Investigation } from "../lib/types";
import { PageHeader } from "./Command";

const PIPELINE = ["get_transaction", "get_user_history", "lookup_policy", "assess_priority", "notify_customer", "notify_analysts"];

export function Agent() {
  const [actor, setActor] = useState("all");
  const [since] = useState(() => Date.now() / 1000 - 3600);
  const hour = useInvestigationsSince(since).data?.items ?? [];
  const { data, isLoading } = useInvestigations(30, actor === "all" ? undefined : actor);

  const ms = useMemo(() => hour.map((r) => r.agent_ms).sort((a, b) => a - b), [hour]);
  const tools = useMemo(() => {
    const m = new Map<string, { n: number; ms: number }>();
    hour.forEach((r) => r.trace.forEach((s) => {
      const x = m.get(s.tool) ?? { n: 0, ms: 0 };
      x.n += 1; x.ms += s.ms ?? 0; m.set(s.tool, x);
    }));
    return [...m.entries()].sort((a, b) => b[1].n - a[1].n);
  }, [hour]);

  return (
    <div className="mx-auto max-w-[1600px]">
      <PageHeader
        title="Agent activity"
        sub="Every REVIEW or BLOCK opens a case and the investigation agent works it: transaction, customer history, policy, priority, notifications. Steps are shown exactly as recorded."
      />

      <Pipeline />

      <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Investigations, last hour" value={num(hour.length)} color="#a78bfa" icon={<Bot size={15} />} sub="one per flagged payment" />
        <Kpi label="Critical or high" value={num(hour.filter((r) => r.priority !== "normal").length)} color="#ff4d6a" icon={<Siren size={15} />} sub="paged to analysts" />
        <Kpi label="Notifications sent" value={num(hour.reduce((s, r) => s + r.notified.length, 0))} color="#ff9a3c" icon={<BellRing size={15} />} sub="customer SMS and analyst alerts" />
        <Kpi label="Agent time, median" value={ms.length ? `${ms[Math.floor(ms.length / 2)].toFixed(1)} ms` : "n/a"} color="#2dd4a3" icon={<Timer size={15} />}
          sub={ms.length ? <>p95 <span className="num">{ms[Math.floor(ms.length * 0.95)].toFixed(1)} ms</span></> : "no runs yet"} />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-12">
        <Panel className="xl:col-span-8" pad={false} eyebrow="Live" title="Investigations as they run"
          action={data && data.actors.length > 0 && (
            <Segmented value={actor} onChange={setActor} options={[{ value: "all", label: "All" }, ...data.actors.map((a) => ({ value: a, label: `via ${a}` }))]} />
          )}>
          <div className="space-y-2 px-3 pb-3">
            {isLoading && Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-16" />)}
            {data?.items.map((r, i) => <Run key={r.case_id} r={r} defaultOpen={i === 0} />)}
            {data && data.items.length === 0 && (
              <Empty icon={<Bot size={28} />} title="No investigations yet">
                Start demo traffic, score a payment through the API, or have an MCP client call score_transaction.
              </Empty>
            )}
          </div>
        </Panel>

        <Panel className="xl:col-span-4 self-start" eyebrow="Last hour" title="Tool usage">
          <div className="space-y-3">
            {tools.map(([tool, x]) => {
              const m = toolMeta(tool);
              const Icon = m.icon;
              return (
                <div key={tool}>
                  <div className="flex items-center justify-between text-[12.5px]">
                    <span className="flex items-center gap-2"><Icon size={13} style={{ color: m.color }} /><span className="font-mono">{tool}</span></span>
                    <span className="num text-dim">{num(x.n)} · {(x.ms / x.n).toFixed(2)} ms</span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-panel-3">
                    <div className="h-full rounded-full" style={{ width: `${(x.n / tools[0][1].n) * 100}%`, background: m.color }} />
                  </div>
                </div>
              );
            })}
            {tools.length === 0 && <p className="text-[13px] text-dim">No tool calls in the last hour.</p>}
          </div>
          <p className="mt-5 border-t border-line pt-3 text-[12px] leading-relaxed text-faint">
            The chain is deterministic, so every result is reproducible and auditable. With ANTHROPIC_API_KEY set, an LLM
            also writes a short narrative from the same evidence; it never changes the decision, priority or actions.
          </p>
        </Panel>
      </div>
    </div>
  );
}

function Pipeline() {
  return (
    <div className="panel overflow-x-auto px-5 py-4">
      <div className="flex min-w-[760px] items-center">
        <Node label="Payment scored" sub="REVIEW or BLOCK" color="var(--color-review)" icon={<Cpu size={14} />} />
        <Wire />
        <Node label="Case opened" sub="priority pending" color="var(--color-info)" icon={<Bot size={14} />} />
        {PIPELINE.map((t) => {
          const m = toolMeta(t);
          const Icon = m.icon;
          return (
            <div key={t} className="flex flex-1 items-center">
              <Wire />
              <Node label={t} sub={t.startsWith("notify") ? "when required" : m.verb.toLowerCase()} color={m.color} icon={<Icon size={14} />} mono />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Node({ label, sub, color, icon, mono }: { label: string; sub: string; color: string; icon: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex shrink-0 flex-col items-center gap-1.5 text-center">
      <span className="flex size-9 items-center justify-center rounded-xl" style={{ color, background: `color-mix(in oklab, ${color} 13%, transparent)`, boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${color} 35%, transparent), 0 0 24px -8px ${color}` }}>
        {icon}
      </span>
      <span className={cx("text-[11px] font-semibold", mono && "font-mono")}>{label}</span>
      <span className="-mt-1 text-[10px] text-faint">{sub}</span>
    </div>
  );
}

function Wire() {
  return (
    <div className="relative mx-1 -mt-8 h-px min-w-4 flex-1 overflow-hidden bg-line-2">
      <span className="absolute inset-y-0 w-8 animate-wire bg-gradient-to-r from-transparent via-saffron to-transparent" />
    </div>
  );
}

function Run({ r, defaultOpen }: { r: Investigation; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={cx("animate-fade-up overflow-hidden rounded-xl border transition", open ? "border-line-2 bg-panel-2/60" : "border-line bg-panel-2/30 hover:border-line-2")}>
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-4 px-3.5 py-3 text-left max-lg:flex-wrap">
        <span className="w-[76px] shrink-0"><PriorityPill p={r.priority} /></span>
        <span className="num w-10 shrink-0 text-[12px] text-faint">#{r.case_id}</span>
        <span className="w-[62px] shrink-0"><DecisionBadge d={r.decision} /></span>
        <span className="num w-[92px] shrink-0 text-[13px] font-semibold">{inr(r.amount)}</span>
        <span className="min-w-0 flex-1 truncate text-[12.5px] text-dim">{r.city} · {r.user_id}</span>
        <span className="flex shrink-0 items-center gap-4">
          <span className="flex w-[170px] justify-end"><TraceStrip trace={r.trace} /></span>
          <span className="num w-[92px] text-right text-[11.5px] text-dim">{r.trace.length} steps · {r.agent_ms.toFixed(1)} ms</span>
          <span className="w-[92px] text-center"><span className="rounded-md bg-panel-3 px-1.5 py-0.5 text-[11px] text-dim">via {r.actor ?? "unknown"}</span></span>
          <span className="num w-16 text-right text-[11.5px] text-faint" title={clock(r.created_at)}>{ago(r.created_at)}</span>
          <ChevronDown size={14} className={cx("text-faint transition", open && "rotate-180")} />
        </span>
      </button>
      {open && (
        <div className="border-t border-line px-4 pt-4 pb-2">
          <TraceTimeline trace={r.trace} />
          <div className="flex justify-end pb-2">
            <Link to={`/cases/${r.case_id}`} className="text-[12.5px] font-medium text-saffron hover:underline">Open case #{r.case_id} →</Link>
          </div>
        </div>
      )}
    </div>
  );
}
