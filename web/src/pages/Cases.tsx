import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { TraceStrip } from "../components/Trace";
import { DecisionBadge, Empty, Panel, PriorityPill, ScoreBar, Segmented, Skeleton, StatusPill, cx } from "../components/ui";
import { useCases } from "../lib/api";
import { ago, inr, num } from "../lib/format";
import type { Priority } from "../lib/types";
import { PageHeader } from "./Command";

type Status = "open" | "confirmed_fraud" | "false_positive" | "all";

export function CaseQueue() {
  const [status, setStatus] = useState<Status>("open");
  const [prio, setPrio] = useState<"all" | Priority>("all");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const { data, isLoading } = useCases(status);
  const nav = useNavigate();

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data ?? []).filter((c) =>
      (prio === "all" || c.priority === prio) &&
      (!needle || `${c.case_id} ${c.user_id} ${c.city} ${c.merchant} ${c.txn_id}`.toLowerCase().includes(needle)));
  }, [data, prio, q]);

  const counts = useMemo(() => {
    const out: Record<string, number> = { critical: 0, high: 0, normal: 0 };
    (data ?? []).forEach((c) => (out[c.priority] += 1));
    return out;
  }, [data]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input, textarea, select")) return;
      if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(rows.length - 1, s + 1)); }
      if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
      if (e.key === "Enter" && rows[sel]) nav(`/cases/${rows[sel].case_id}`);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rows, sel, nav]);

  const exposure = rows.reduce((s, c) => s + c.amount, 0);

  return (
    <div className="mx-auto max-w-[1600px]">
      <PageHeader
        title="Case queue"
        sub="Every REVIEW or BLOCK opens a case. The investigation agent has already worked each one; most urgent first."
        right={<div className="text-[12px] text-faint"><kbd className="font-mono">j</kbd>/<kbd className="font-mono">k</kbd> to move · <kbd className="font-mono">enter</kbd> to open</div>}
      />

      <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
        {(["critical", "high", "normal"] as const).map((p) => (
          <button key={p} onClick={() => setPrio(prio === p ? "all" : p)}
            className={cx("panel px-4 py-3 text-left transition hover:border-line-2", prio === p && "ring-1 ring-saffron/50")}>
            <PriorityPill p={p} />
            <div className="num mt-1.5 text-2xl font-semibold">{num(counts[p])}</div>
          </button>
        ))}
        <div className="panel px-4 py-3">
          <span className="label">Exposure in view</span>
          <div className="num mt-1.5 text-2xl font-semibold">{inr(exposure, true)}</div>
        </div>
      </div>

      <Panel pad={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <Segmented<Status> value={status} onChange={(v) => { setStatus(v); setSel(0); }} options={[
            { value: "open", label: "Open" }, { value: "confirmed_fraud", label: "Confirmed fraud" },
            { value: "false_positive", label: "False positive" }, { value: "all", label: "All" },
          ]} />
          <div className="ml-auto flex items-center gap-2 rounded-lg border border-line bg-panel-2 px-2.5">
            <Search size={13} className="text-faint" />
            <input value={q} onChange={(e) => { setQ(e.target.value); setSel(0); }} placeholder="Case, customer, city…"
              className="h-8 w-56 bg-transparent text-[12.5px] outline-none placeholder:text-faint" />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px] whitespace-nowrap">
            <thead>
              <tr className="text-left">
                {["Priority", "Case", "Amount", "Customer", "Where", "Risk", "Decision", "Agent", "Next step", "Status", "Opened"].map((h) => (
                  <th key={h} className="label border-b border-line px-3 py-2.5 first:pl-4">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((c, i) => (
                <tr key={c.case_id} onClick={() => nav(`/cases/${c.case_id}`)} onMouseEnter={() => setSel(i)}
                  className={cx("cursor-pointer border-b border-line/60 transition", i === sel ? "bg-panel-2" : "hover:bg-panel-2/60")}>
                  <td className="relative px-3 py-2.5 pl-4">
                    {i === sel && <span className="absolute inset-y-1 left-0 w-[3px] rounded-r bg-gradient-to-b from-saffron to-rose" />}
                    <PriorityPill p={c.priority} />
                  </td>
                  <td className="num px-3 py-2.5 text-dim">#{c.case_id}</td>
                  <td className="num px-3 py-2.5 font-semibold">{inr(c.amount)}</td>
                  <td className="px-3 py-2.5 font-mono text-[12px] text-dim">{c.user_id}</td>
                  <td className="px-3 py-2.5">{c.city} <span className="text-faint">· {c.merchant}</span></td>
                  <td className="px-3 py-2.5"><ScoreBar score={c.score} /></td>
                  <td className="px-3 py-2.5"><DecisionBadge d={c.decision} /></td>
                  <td className="px-3 py-2.5">{c.trace && <TraceStrip trace={c.trace} />}</td>
                  <td className="max-w-[280px] truncate px-3 py-2.5 text-dim">{c.summary?.actions?.[0] ?? ""}</td>
                  <td className="px-3 py-2.5"><StatusPill s={c.status} /></td>
                  <td className="px-3 py-2.5 text-faint">{ago(c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {isLoading && <div className="space-y-2 p-4">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-9" />)}</div>}
          {data && rows.length === 0 && <Empty title="No cases match">Try another status or clear the filters.</Empty>}
        </div>
      </Panel>
    </div>
  );
}
