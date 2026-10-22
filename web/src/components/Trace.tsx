import { BellRing, BookOpenCheck, Gauge, History, MessageSquareText, Play, Receipt, Sparkles, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { brief, human } from "../lib/format";
import type { TraceStep } from "../lib/types";
import { cx } from "./ui";

const TOOL: Record<string, { icon: typeof Receipt; color: string; verb: string }> = {
  get_transaction: { icon: Receipt, color: "var(--color-info)", verb: "Loaded the transaction" },
  get_user_history: { icon: History, color: "var(--color-info)", verb: "Pulled customer history" },
  lookup_policy: { icon: BookOpenCheck, color: "var(--color-agent)", verb: "Retrieved policy clauses" },
  assess_priority: { icon: Gauge, color: "var(--color-saffron)", verb: "Assessed priority" },
  notify_customer: { icon: MessageSquareText, color: "var(--color-block)", verb: "Notified the customer" },
  notify_analysts: { icon: BellRing, color: "var(--color-block)", verb: "Paged the analyst team" },
  llm_narrative: { icon: Sparkles, color: "var(--color-agent)", verb: "Wrote the case narrative" },
};

export const toolMeta = (t: string) => TOOL[t] ?? { icon: Wrench, color: "var(--color-dim)", verb: human(t) };

/** The investigation agent's tool calls as a vertical timeline. `replay` animates the steps in order. */
export function TraceTimeline({ trace, compact = false, replayable = false }: { trace: TraceStep[]; compact?: boolean; replayable?: boolean }) {
  const [shown, setShown] = useState<number | null>(null);   // null: not replaying, show everything
  const [run, setRun] = useState(0);
  useEffect(() => {
    if (!run) return;
    setShown(0);
    const ids = trace.map((_, i) => window.setTimeout(() => setShown(i + 1), 280 * (i + 1)));
    ids.push(window.setTimeout(() => setShown(null), 280 * (trace.length + 1)));
    return () => ids.forEach(clearTimeout);
  }, [run]); // eslint-disable-line react-hooks/exhaustive-deps
  const total = trace.reduce((s, x) => s + (x.ms ?? 0), 0);

  return (
    <div>
      {replayable && (
        <div className="mb-3 flex items-center justify-between text-[12px] text-dim">
          <span><span className="num text-fg">{trace.length}</span> tool calls · <span className="num text-fg">{total.toFixed(1)} ms</span> total</span>
          <button onClick={() => setRun((r) => r + 1)} className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-agent hover:bg-agent/10">
            <Play size={12} /> Replay
          </button>
        </div>
      )}
      <ol className="relative">
        {trace.map((s, i) => {
          const m = toolMeta(s.tool);
          const Icon = m.icon;
          const last = i === trace.length - 1;
          return (
            <li key={s.step} className={cx("relative grid grid-cols-[28px_1fr] gap-x-3 transition-all duration-300", shown == null || i < shown ? "opacity-100" : "translate-y-1 opacity-0")}>
              {!last && <span className="absolute top-7 bottom-0 left-[13.5px] w-px bg-gradient-to-b from-line-2 to-line" />}
              <span
                className="relative z-10 mt-0.5 flex size-7 items-center justify-center rounded-full ring-1"
                style={{ color: m.color, background: `color-mix(in oklab, ${m.color} 12%, var(--color-panel))`, boxShadow: `0 0 0 1px color-mix(in oklab, ${m.color} 35%, transparent)` }}
              >
                <Icon size={13} />
              </span>
              <div className={cx("min-w-0", compact ? "pb-2.5" : "pb-4")}>
                <div className="flex items-baseline justify-between gap-3">
                  <div className="min-w-0 truncate">
                    <span className="font-mono text-[12.5px] font-semibold text-fg">{s.tool}</span>
                    {!compact && <span className="ml-2 text-[12px] text-faint">{m.verb}</span>}
                  </div>
                  <span className="num shrink-0 text-[11px] text-faint">{s.ms == null ? "async" : `${s.ms.toFixed(2)} ms`}</span>
                </div>
                <div className={cx("mt-1 rounded-md border border-line bg-ink/60 px-2.5 py-1.5 font-mono text-[11.5px] leading-relaxed text-dim", compact && "py-1")}>
                  <div className="break-words"><span className="text-faint">in&nbsp;&nbsp;</span>{brief(s.input, compact ? 90 : 220)}</div>
                  <div className="break-words"><span className="text-faint">out&nbsp;</span><span style={{ color: s.tool === "assess_priority" ? m.color : undefined }}>{brief(s.output, compact ? 90 : 220)}</span></div>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** One-line strip of tool icons, for list rows. */
export function TraceStrip({ trace }: { trace: TraceStep[] }) {
  return (
    <div className="flex items-center">
      {trace.map((s, i) => {
        const m = toolMeta(s.tool);
        const Icon = m.icon;
        return (
          <span key={i} className="flex items-center">
            {i > 0 && <span className="h-px w-2.5 bg-line-2" />}
            <span title={s.tool} className="flex size-5 items-center justify-center rounded-full" style={{ color: m.color, background: `color-mix(in oklab, ${m.color} 14%, transparent)` }}>
              <Icon size={10} />
            </span>
          </span>
        );
      })}
    </div>
  );
}
