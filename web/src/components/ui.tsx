import type { ReactNode } from "react";
import { DECISION_COLOR, PRIORITY_COLOR, human } from "../lib/format";
import type { CaseStatus, Decision, Priority } from "../lib/types";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Panel({ title, action, children, className, pad = true, eyebrow }: {
  title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; pad?: boolean; eyebrow?: ReactNode;
}) {
  return (
    <section className={cx("panel flex min-w-0 flex-col", className)}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 px-4 pt-3.5 pb-2">
          <div className="min-w-0">
            {eyebrow && <div className="label mb-0.5">{eyebrow}</div>}
            <h2 className="truncate text-[13px] font-semibold tracking-tight text-fg">{title}</h2>
          </div>
          {action}
        </header>
      )}
      <div className={cx("min-h-0 flex-1", pad && "px-4 pb-4")}>{children}</div>
    </section>
  );
}

export function DecisionBadge({ d, size = "sm" }: { d: Decision; size?: "sm" | "lg" }) {
  const c = DECISION_COLOR[d];
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-md font-mono font-semibold tracking-wide",
        size === "sm" ? "px-1.5 py-0.5 text-[10.5px]" : "px-2.5 py-1 text-sm",
      )}
      style={{ color: c, background: `color-mix(in oklab, ${c} 14%, transparent)`, boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${c} 30%, transparent)` }}
    >
      <span className="size-1.5 rounded-full" style={{ background: c }} />
      {d}
    </span>
  );
}

export function PriorityPill({ p }: { p: Priority }) {
  const c = PRIORITY_COLOR[p];
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider" style={{ color: c }}>
      <span className="relative flex size-2">
        {p === "critical" && <span className="absolute inset-0 animate-pulse-ring rounded-full" style={{ background: c }} />}
        <span className="relative size-2 rounded-full" style={{ background: c }} />
      </span>
      {p}
    </span>
  );
}

const STATUS_STYLE: Record<CaseStatus, string> = {
  open: "text-info bg-info/10 ring-info/25",
  confirmed_fraud: "text-block bg-block/10 ring-block/25",
  false_positive: "text-allow bg-allow/10 ring-allow/25",
};

export function StatusPill({ s }: { s: CaseStatus }) {
  return <span className={cx("rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset", STATUS_STYLE[s])}>{human(s)}</span>;
}

export function Button({ children, variant = "ghost", className, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "ghost" | "primary" | "danger" | "success" | "subtle";
}) {
  const v = {
    ghost: "border border-line-2 bg-panel-2 text-fg hover:bg-panel-3 hover:border-faint/50",
    subtle: "text-dim hover:text-fg hover:bg-panel-2",
    primary: "bg-gradient-to-r from-saffron to-rose text-ink font-semibold shadow-[0_6px_24px_-8px_var(--color-rose)] hover:brightness-110",
    danger: "bg-block/90 text-white font-semibold hover:bg-block shadow-[0_6px_24px_-10px_var(--color-block)]",
    success: "border border-allow/40 bg-allow/10 text-allow font-semibold hover:bg-allow/20",
  }[variant];
  return (
    <button
      className={cx("inline-flex items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-[13px] transition disabled:cursor-not-allowed disabled:opacity-50", v, className)}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Sparkline({ values, color, height = 36, fill = true }: { values: number[]; color: string; height?: number; fill?: boolean }) {
  const w = 120;
  if (values.length < 2) return <svg viewBox={`0 0 ${w} ${height}`} className="h-9 w-full" />;
  const max = Math.max(...values, 1);
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, height - 3 - (v / max) * (height - 6)] as const);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
  const id = `sp-${color.replace(/[^a-z]/gi, "")}`;
  return (
    <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className="w-full" style={{ height }}>
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.35" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={`${line}L${w},${height}L0,${height}Z`} fill={`url(#${id})`} />}
      <path d={line} fill="none" stroke={color} strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="2.4" fill={color} />
    </svg>
  );
}

export function Kpi({ label, value, sub, color, spark, icon }: {
  label: string; value: ReactNode; sub?: ReactNode; color: string; spark?: number[]; icon?: ReactNode;
}) {
  return (
    <div className="panel relative overflow-hidden px-4 pt-3.5 pb-2">
      <div className="pointer-events-none absolute -top-10 -right-10 size-28 rounded-full opacity-25 blur-2xl" style={{ background: color }} />
      <div className="flex items-center justify-between">
        <span className="label truncate">{label}</span>
        <span style={{ color }}>{icon}</span>
      </div>
      <div className="num mt-1.5 text-[26px] leading-none font-semibold text-fg">{value}</div>
      <div className="mt-1 h-4 truncate text-[11.5px] text-dim">{sub}</div>
      {spark && <div className="-mx-1 mt-1"><Sparkline values={spark} color={color} height={30} /></div>}
    </div>
  );
}

export function ScoreBar({ score, thresholds }: { score: number; thresholds?: { review: number; block: number } }) {
  const c = thresholds
    ? score >= thresholds.block ? "var(--color-block)" : score >= thresholds.review ? "var(--color-review)" : "var(--color-allow)"
    : score > 0.5 ? "var(--color-block)" : score > 0.1 ? "var(--color-review)" : "var(--color-allow)";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-panel-3">
        <div className="h-full rounded-full" style={{ width: `${Math.max(3, score * 100)}%`, background: c }} />
      </div>
      <span className="num w-10 text-[11.5px] text-dim">{score.toFixed(3)}</span>
    </div>
  );
}

export function Empty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      {icon && <div className="text-faint">{icon}</div>}
      <div className="text-sm font-medium text-fg">{title}</div>
      {children && <div className="max-w-sm text-[13px] text-dim">{children}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-md bg-panel-3/70", className)} />;
}

export function Segmented<T extends string>({ value, options, onChange }: {
  value: T; options: { value: T; label: ReactNode }[]; onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-panel-2 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cx(
            "rounded-md px-2.5 py-1 text-[12px] font-medium transition",
            value === o.value ? "bg-panel-3 text-fg shadow-[inset_0_0_0_1px_var(--color-line-2)]" : "text-dim hover:text-fg",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
