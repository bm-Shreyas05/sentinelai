import { AlertTriangle, ArrowUpRight, Banknote, FolderOpen, ShieldBan, Waves } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { AlertTimeline, CityConstellation, ScoreHistogram } from "../components/charts";
import { DecisionBadge, Empty, Kpi, Panel, PriorityPill, ScoreBar, Segmented, Skeleton, cx } from "../components/ui";
import { useCases, useFeed, useOverview } from "../lib/api";
import { ago, clock, human, inr, num, pct } from "../lib/format";

export function PageHeader({ title, sub, right }: { title: string; sub?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">{title}</h1>
        {sub && <p className="mt-0.5 text-[13px] text-dim">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function Command() {
  const [minutes, setMinutes] = useState<"30" | "60" | "120">("30");
  const { data: ov } = useOverview(Number(minutes));
  const series = ov?.series ?? [];
  const m = ov?.metrics;

  return (
    <div className="mx-auto max-w-[1600px]">
      <PageHeader
        title="Command center"
        sub={<>Every payment scored in real time, last hour{ov && <> · updated {clock(ov.server_time)} IST</>}</>}
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {m ? (
          <>
            <Kpi label="Scored, last hour" value={num(m.transactions)} color="#5aa9ff" icon={<Waves size={15} />}
              sub={<>avg score <span className="num">{m.avg_score.toFixed(3)}</span></>} spark={series.map((s) => s.n)} />
            <Kpi label="Alert rate" value={pct(m.alert_rate, 2)} color="#ffb547" icon={<AlertTriangle size={15} />}
              sub={<><span className="num">{num(m.review)}</span> review · <span className="num">{num(m.block)}</span> block</>}
              spark={series.map((s) => (s.n ? (s.review + s.block) / s.n : 0))} />
            <Kpi label="Blocked" value={num(m.block)} color="#ff4d6a" icon={<ShieldBan size={15} />}
              sub="held before money moved" spark={series.map((s) => s.block)} />
            <Kpi label="Amount held" value={inr(m.blocked_amount, true)} color="#ff3d71" icon={<Banknote size={15} />}
              sub={inr(m.blocked_amount)} spark={series.map((s) => s.held)} />
            <Kpi label="Open cases" value={num(m.cases.open ?? 0)} color="#a78bfa" icon={<FolderOpen size={15} />}
              sub={m.analyst_precision != null ? <>analyst-confirmed precision <span className="num">{pct(m.analyst_precision, 0)}</span></> : "awaiting analyst labels"} />
          </>
        ) : (
          Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-[134px] rounded-[14px]" />)
        )}
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-12">
        <Panel
          className="xl:col-span-8"
          eyebrow="Alerts per minute"
          title={<span className="flex items-center gap-3">Review <i className="inline-block size-2 rounded-sm bg-review" /> Block <i className="inline-block size-2 rounded-sm bg-block" /> <span className="text-faint">volume</span> <i className="inline-block h-0.5 w-3 bg-info/60" /></span>}
          action={<Segmented value={minutes} onChange={setMinutes} options={[{ value: "30", label: "30m" }, { value: "60", label: "1h" }, { value: "120", label: "2h" }]} />}
        >
          {ov ? <AlertTimeline series={series} minutes={Number(minutes)} now={ov.server_time} /> : <Skeleton className="h-[190px]" />}
        </Panel>

        <Panel className="xl:col-span-4 xl:row-span-2" eyebrow="Geography" title="Where alerts are coming from"
          action={<span className="text-[11px] text-faint">bubble = volume</span>}>
          {ov ? <CityConstellation cities={ov.cities} /> : <Skeleton className="h-[330px]" />}
          {ov && <CityTable cities={ov.cities} />}
        </Panel>

        <LiveStream className="xl:col-span-8" />

        <UrgentCases className="xl:col-span-4" />

        <Panel className="xl:col-span-4" eyebrow="Score distribution" title="Where the thresholds cut" action={<span className="text-[11px] text-faint">log scale</span>}>
          {ov ? <ScoreHistogram bins={ov.score_histogram} thresholds={ov.thresholds} /> : <Skeleton className="h-[140px]" />}
        </Panel>

        <Panel className="xl:col-span-4" eyebrow="Channels" title="Alert rate by payment rail">
          <div className="space-y-3 pt-1">
            {ov?.channels.map((c) => {
              const r = c.n ? c.alerts / c.n : 0;
              const max = Math.max(...ov.channels.map((x) => x.n), 1);
              return (
                <div key={c.channel}>
                  <div className="flex justify-between text-[12.5px]">
                    <span className="font-medium uppercase tracking-wide">{c.channel}</span>
                    <span className="num text-dim">{num(c.n)} · <span className={r > 0.02 ? "text-review" : "text-dim"}>{pct(r, 2)}</span></span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-panel-3">
                    <div className="h-full rounded-full bg-gradient-to-r from-info/70 to-info" style={{ width: `${(c.n / max) * 100}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function CityTable({ cities }: { cities: { city: string; n: number; alerts: number; block: number; held: number }[] }) {
  const top = [...cities].sort((a, b) => b.held - a.held || b.alerts - a.alerts).slice(0, 8);
  const max = Math.max(1, ...top.map((c) => c.held));
  return (
    <div className="mt-2 border-t border-line pt-3">
      <div className="label mb-2 flex justify-between"><span>City</span><span>alerts · held</span></div>
      <ol className="space-y-1.5">
        {top.map((c, i) => (
          <li key={c.city} className="relative grid grid-cols-[18px_1fr_auto] items-center gap-2 overflow-hidden rounded-md px-2 py-1.5 text-[12.5px]">
            <span className="absolute inset-y-0 left-0 bg-block/10" style={{ width: `${(c.held / max) * 100}%` }} />
            <span className="num relative text-faint">{i + 1}</span>
            <span className="relative">{c.city} <span className="num text-[11px] text-faint">{num(c.n)}</span></span>
            <span className="num relative text-dim"><span className="text-review">{c.alerts}</span> · <span className="text-fg">{inr(c.held, true)}</span></span>
          </li>
        ))}
      </ol>
      <div className="mt-3 flex gap-3 text-[11px] text-faint">
        <span className="flex items-center gap-1"><i className="size-2 rounded-full bg-allow" /> &lt;1% alerts</span>
        <span className="flex items-center gap-1"><i className="size-2 rounded-full bg-review" /> 1–2.5%</span>
        <span className="flex items-center gap-1"><i className="size-2 rounded-full bg-block" /> &gt;2.5%</span>
        <span>ring = most held</span>
      </div>
    </div>
  );
}

function LiveStream({ className }: { className?: string }) {
  const [flagged, setFlagged] = useState<"all" | "flagged">("all");
  const { data } = useFeed(28, flagged === "flagged");
  const nav = useNavigate();
  return (
    <Panel
      className={className}
      pad={false}
      eyebrow="Live stream"
      title="Transactions as they are scored"
      action={<Segmented value={flagged} onChange={setFlagged} options={[{ value: "all", label: "All" }, { value: "flagged", label: "Flagged" }]} />}
    >
      <div className="max-h-[560px] overflow-auto">
        <table className="w-full text-[12.5px] whitespace-nowrap">
          <thead className="sticky top-0 z-10 bg-panel/95 backdrop-blur">
            <tr className="text-left">
              {["Time", "Customer", "Amount", "Where", "Rail", "Risk", "Decision", "Why"].map((h) => (
                <th key={h} className="label border-b border-line px-3 py-2 font-semibold first:pl-4">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data?.map((r) => (
              <tr
                key={r.txn_id}
                onClick={() => r.case_id && nav(`/cases/${r.case_id}`)}
                className={cx("animate-row-in border-b border-line/60", r.case_id ? "cursor-pointer hover:bg-panel-2" : "")}
                style={{ ["--flash" as string]: r.decision === "BLOCK" ? "#ff4d6a" : r.decision === "REVIEW" ? "#ffb547" : "#5aa9ff" }}
              >
                <td className="num px-3 py-2 pl-4 text-faint">{clock(r.created_at)}</td>
                <td className="px-3 py-2 font-mono text-[12px] text-dim">{r.user_id}</td>
                <td className="num px-3 py-2 font-medium">{inr(r.amount)}</td>
                <td className="px-3 py-2"><span className="text-fg">{r.city}</span> <span className="text-faint">· {human(r.category)}</span></td>
                <td className="px-3 py-2 text-[11px] uppercase tracking-wide text-dim">{r.channel}</td>
                <td className="px-3 py-2"><ScoreBar score={r.score} /></td>
                <td className="px-3 py-2"><DecisionBadge d={r.decision} /></td>
                <td className="max-w-[220px] truncate px-3 py-2 text-dim">{r.reason ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.length === 0 && (
          <Empty title="No transactions yet">Press Start in the top bar to stream simulated payments, or POST to /v1/transactions.</Empty>
        )}
      </div>
    </Panel>
  );
}

function UrgentCases({ className }: { className?: string }) {
  const { data } = useCases("open", 8);
  return (
    <Panel className={className} pad={false} eyebrow="Needs a human" title="Most urgent open cases"
      action={<Link to="/cases" className="flex items-center gap-1 text-[12px] text-dim hover:text-fg">Queue <ArrowUpRight size={12} /></Link>}>
      <ul className="max-h-[560px] overflow-auto px-2 pb-2">
        {data?.map((c) => (
          <li key={c.case_id}>
            <Link to={`/cases/${c.case_id}`} className="group flex items-center gap-3 rounded-lg px-2 py-2.5 transition hover:bg-panel-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <PriorityPill p={c.priority} />
                  <span className="num text-[11px] text-faint">#{c.case_id}</span>
                </div>
                <div className="mt-1 truncate text-[13px]">
                  <span className="num font-semibold">{inr(c.amount)}</span> <span className="text-dim">· {c.city} · {c.user_id}</span>
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <DecisionBadge d={c.decision} />
                <span className="text-[11px] text-faint">{ago(c.created_at)}</span>
              </div>
            </Link>
          </li>
        ))}
        {data && data.length === 0 && <Empty title="Queue is clear">No open cases right now.</Empty>}
      </ul>
    </Panel>
  );
}
