import { useState } from "react";
import { featureLabel, hm, inr, num } from "../lib/format";
import type { Overview, Thresholds } from "../lib/types";

/* ── alerts per minute: stacked REVIEW/BLOCK bars over a faint volume area ─────────── */
export function AlertTimeline({ series, minutes, now }: { series: Overview["series"]; minutes: number; now: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const end = Math.floor(now / 60) * 60;
  const byMin = new Map(series.map((s) => [s.minute, s]));
  const rows = Array.from({ length: minutes }, (_, i) => {
    const m = end - (minutes - 1 - i) * 60;
    return byMin.get(m) ?? { minute: m, n: 0, review: 0, block: 0, held: 0 };
  });
  const W = 600, H = 170, P = 22;
  const maxA = Math.max(4, ...rows.map((r) => r.review + r.block));
  const maxN = Math.max(10, ...rows.map((r) => r.n));
  const bw = W / rows.length;
  const y = (v: number) => H - P - (v / maxA) * (H - P - 8);
  const vy = (v: number) => H - P - (v / maxN) * (H - P - 8);
  const area = rows.map((r, i) => `${i ? "L" : "M"}${(i + 0.5) * bw},${vy(r.n)}`).join("") + `L${W - bw / 2},${H - P}L${bw / 2},${H - P}Z`;
  const h = hover != null ? rows[hover] : null;
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-[190px] w-full" preserveAspectRatio="none" onMouseLeave={() => setHover(null)}>
        <defs>
          <linearGradient id="vol" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#5aa9ff" stopOpacity="0.18" />
            <stop offset="1" stopColor="#5aa9ff" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line key={f} x1="0" x2={W} y1={y(maxA * f)} y2={y(maxA * f)} stroke="var(--color-line)" strokeDasharray="2 4" />
        ))}
        <path d={area} fill="url(#vol)" />
        {rows.map((r, i) => {
          const x = i * bw + bw * 0.18, w = bw * 0.64;
          return (
            <g key={r.minute} onMouseEnter={() => setHover(i)}>
              <rect x={i * bw} y={0} width={bw} height={H - P} fill={hover === i ? "rgb(255 255 255 / 0.03)" : "transparent"} />
              <rect x={x} y={y(r.review)} width={w} height={H - P - y(r.review)} rx="1.5" fill="var(--color-review)" opacity="0.85" />
              <rect x={x} y={y(r.review + r.block)} width={w} height={y(r.review) - y(r.review + r.block)} rx="1.5" fill="var(--color-block)" />
            </g>
          );
        })}
        {rows.map((r, i) => (i % Math.ceil(rows.length / 6) === 0 || i === rows.length - 1) && (
          <text key={r.minute} x={(i + 0.5) * bw} y={H - 6} textAnchor="middle" className="fill-faint font-mono" fontSize="10">{hm(r.minute)}</text>
        ))}
      </svg>
      {h && (
        <div className="pointer-events-none absolute top-1 rounded-lg border border-line-2 bg-panel-2/95 px-3 py-2 text-[12px] shadow-xl backdrop-blur"
          style={{ left: `clamp(0px, calc(${((hover! + 0.5) / rows.length) * 100}% - 70px), calc(100% - 150px))` }}>
          <div className="num text-dim">{hm(h.minute)} IST</div>
          <div className="mt-1 grid grid-cols-[auto_auto] gap-x-4 gap-y-0.5">
            <span className="text-dim">scored</span><span className="num text-right">{num(h.n)}</span>
            <span className="text-review">review</span><span className="num text-right">{h.review}</span>
            <span className="text-block">block</span><span className="num text-right">{h.block}</span>
            <span className="text-dim">held</span><span className="num text-right">{inr(h.held, true)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── score distribution on a log scale, with the live decision thresholds ──────────── */
export function ScoreHistogram({ bins, thresholds }: { bins: number[]; thresholds: Thresholds }) {
  const W = 400, H = 120;
  const max = Math.log1p(Math.max(...bins, 1));
  const bw = W / bins.length;
  const col = (i: number) => {
    const mid = (i + 0.5) / bins.length;
    return mid >= thresholds.block ? "var(--color-block)" : mid >= thresholds.review ? "var(--color-review)" : "var(--color-allow)";
  };
  return (
    <svg viewBox={`0 0 ${W} ${H + 16}`} className="h-[140px] w-full" preserveAspectRatio="none">
      {bins.map((b, i) => {
        const h = (Math.log1p(b) / max) * (H - 6);
        return <rect key={i} x={i * bw + 1.5} y={H - h} width={bw - 3} height={h} rx="2" fill={col(i)} opacity={0.25 + 0.75 * (h / H)} />;
      })}
      {(["review", "block"] as const).map((k) => (
        <g key={k}>
          <line x1={thresholds[k] * W} x2={thresholds[k] * W} y1="0" y2={H} stroke={`var(--color-${k})`} strokeDasharray="3 3" />
          <text x={thresholds[k] * W + 4} y="10" fontSize="10" className="font-mono" fill={`var(--color-${k})`}>{k} {thresholds[k].toFixed(2)}</text>
        </g>
      ))}
      <text x="0" y={H + 13} fontSize="10" className="fill-faint font-mono">0.0</text>
      <text x={W} y={H + 13} fontSize="10" textAnchor="end" className="fill-faint font-mono">1.0</text>
    </svg>
  );
}

/* ── India as a constellation of the cities we score in ───────────────────────────── */
const LON = [67.5, 92], LAT = [7.5, 33];
// label placement for cities that sit close together
const LABEL: Record<string, "left" | "below" | "above"> = { Pune: "below", Mumbai: "left", Bengaluru: "left", Surat: "left", Ahmedabad: "left", Jaipur: "left" };
const riskColor = (rate: number) => (rate >= 0.025 ? "var(--color-block)" : rate >= 0.01 ? "var(--color-review)" : "var(--color-allow)");
export function CityConstellation({ cities }: { cities: Overview["cities"] }) {
  const [hover, setHover] = useState<string | null>(null);
  const W = 360, H = 380;
  const pts = cities.filter((c) => c.lat != null && c.lon != null).map((c) => ({
    ...c,
    x: ((c.lon! - LON[0]) / (LON[1] - LON[0])) * W,
    y: H - ((c.lat! - LAT[0]) / (LAT[1] - LAT[0])) * H,
  }));
  const maxN = Math.max(1, ...pts.map((p) => p.n));
  const hottest = new Set([...pts].sort((a, b) => b.held - a.held).filter((p) => p.held > 0).slice(0, 3).map((p) => p.city));
  const edges: [typeof pts[0], typeof pts[0]][] = [];
  pts.forEach((a) => {
    pts.map((b) => ({ b, d: Math.hypot(a.x - b.x, a.y - b.y) })).filter((o) => o.b !== a).sort((p, q) => p.d - q.d).slice(0, 2)
      .forEach(({ b }) => { if (!edges.some(([p, q]) => (p === b && q === a))) edges.push([a, b]); });
  });
  const hv = pts.find((p) => p.city === hover);
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="mx-auto h-[330px] w-full">
        <defs>
          <linearGradient id="beam" x1="0" x2="1">
            <stop offset="0" stopColor="#ff9a3c" stopOpacity="0" />
            <stop offset="1" stopColor="#ff9a3c" stopOpacity="0.22" />
          </linearGradient>
        </defs>
        {[60, 120, 180].map((r) => (
          <circle key={r} cx={W / 2} cy={H / 2} r={r} fill="none" stroke="var(--color-line)" strokeDasharray="1 5" />
        ))}
        <g className="origin-center animate-scan" style={{ transformOrigin: `${W / 2}px ${H / 2}px`, transformBox: "view-box" }}>
          <path d={`M${W / 2},${H / 2} L${W / 2 + 190},${H / 2} A190,190 0 0,0 ${W / 2 + 190 * Math.cos(-0.35)},${H / 2 + 190 * Math.sin(-0.35)} Z`} fill="url(#beam)" opacity="0.6" />
        </g>
        {edges.map(([a, b], i) => (
          <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--color-line-2)" strokeWidth="0.8" opacity="0.7" />
        ))}
        {pts.map((p) => {
          const r = 2.5 + Math.sqrt(p.n / maxN) * 7;
          const c = riskColor(p.n ? p.alerts / p.n : 0);
          const side = LABEL[p.city];
          const lx = side === "left" ? p.x - r - 4 : side === "below" || side === "above" ? p.x : p.x + r + 4;
          const ly = side === "below" ? p.y + r + 11 : side === "above" ? p.y - r - 5 : p.y + 3.5;
          return (
            <g key={p.city} onMouseEnter={() => setHover(p.city)} onMouseLeave={() => setHover(null)} className="cursor-default">
              {hottest.has(p.city) && (
                <circle cx={p.x} cy={p.y} r={r} fill="none" stroke={c} strokeWidth="1.5" className="animate-pulse-ring" style={{ transformOrigin: `${p.x}px ${p.y}px`, transformBox: "view-box" }} />
              )}
              <circle cx={p.x} cy={p.y} r={r + 5} fill={c} opacity="0.07" />
              <circle cx={p.x} cy={p.y} r={r} fill={c} opacity="0.25" stroke={c} strokeWidth="1" />
              <circle cx={p.x} cy={p.y} r="1.8" fill={c} />
              <text x={lx} y={ly} fontSize="10.5" textAnchor={side === "left" ? "end" : side ? "middle" : "start"}
                className={hover === p.city ? "fill-fg" : "fill-dim"} style={{ fontWeight: hover === p.city ? 700 : 500 }}>{p.city}</text>
            </g>
          );
        })}
      </svg>
      {hv && (
        <div className="pointer-events-none absolute right-2 bottom-2 rounded-lg border border-line-2 bg-panel-2/95 px-3 py-2 text-[12px] shadow-xl">
          <div className="font-semibold">{hv.city}</div>
          <div className="mt-1 grid grid-cols-[auto_auto] gap-x-4 gap-y-0.5">
            <span className="text-dim">scored</span><span className="num text-right">{num(hv.n)}</span>
            <span className="text-review">alerts</span><span className="num text-right">{hv.alerts}</span>
            <span className="text-block">blocked</span><span className="num text-right">{hv.block}</span>
            <span className="text-dim">held</span><span className="num text-right">{inr(hv.held, true)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── risk gauge: 0→1 arc with REVIEW and BLOCK bands ─────────────────────────────── */
export function RiskGauge({ score, thresholds, size = 200 }: { score: number; thresholds: Thresholds; size?: number }) {
  const r = 80, cx = 100, cy = 96, sw = 12;
  const pt = (f: number) => {
    const a = Math.PI * (1 - f);
    return [cx + r * Math.cos(a), cy - r * Math.sin(a)] as const;
  };
  const arc = (f0: number, f1: number) => {
    const [x0, y0] = pt(f0), [x1, y1] = pt(f1);
    return `M${x0},${y0} A${r},${r} 0 ${f1 - f0 > 0.5 ? 1 : 0} 1 ${x1},${y1}`;
  };
  const c = score >= thresholds.block ? "var(--color-block)" : score >= thresholds.review ? "var(--color-review)" : "var(--color-allow)";
  const [nx, ny] = pt(score);
  return (
    <svg viewBox="0 0 200 116" style={{ width: size }}>
      <path d={arc(0, 1)} stroke="var(--color-panel-3)" strokeWidth={sw} fill="none" strokeLinecap="round" />
      <path d={arc(0, thresholds.review)} stroke="var(--color-allow)" strokeOpacity="0.3" strokeWidth={sw} fill="none" />
      <path d={arc(thresholds.review, thresholds.block)} stroke="var(--color-review)" strokeOpacity="0.3" strokeWidth={sw} fill="none" />
      <path d={arc(thresholds.block, 1)} stroke="var(--color-block)" strokeOpacity="0.3" strokeWidth={sw} fill="none" />
      <path d={arc(0, Math.max(0.005, score))} stroke={c} strokeWidth={sw - 5} fill="none" strokeLinecap="round" style={{ filter: `drop-shadow(0 0 6px ${c})` }} />
      <circle cx={nx} cy={ny} r="7" fill="var(--color-ink)" stroke={c} strokeWidth="3" />
      <text x={cx} y={cy - 12} textAnchor="middle" className="font-mono" fontSize="30" fontWeight="700" fill="var(--color-fg)">{score.toFixed(3)}</text>
      <text x={cx} y={cy + 8} textAnchor="middle" fontSize="9.5" letterSpacing="1.5" fill="var(--color-faint)">FRAUD PROBABILITY</text>
    </svg>
  );
}

/* ── TreeSHAP contributions as a diverging bar chart ──────────────────────────────── */
export function Contributions({ contributions, features }: { contributions: Record<string, number>; features: Record<string, number> }) {
  const rows = Object.entries(contributions).filter(([, v]) => Math.abs(v) > 0.05).sort((a, b) => b[1] - a[1]);
  const max = Math.max(0.5, ...rows.map(([, v]) => Math.abs(v)));
  return (
    <div className="space-y-1">
      {rows.map(([f, v]) => (
        <div key={f} className="group grid grid-cols-[150px_1fr_56px] items-center gap-3 text-[12px]">
          <div className="truncate text-dim group-hover:text-fg" title={f}>
            {featureLabel(f)} <span className="num text-faint">{fmtFeature(f, features[f])}</span>
          </div>
          <div className="relative h-4">
            <div className="absolute inset-y-0 left-1/2 w-px bg-line-2" />
            <div
              className="absolute inset-y-0.5 rounded-sm transition-all"
              style={{
                left: v >= 0 ? "50%" : `${50 - (Math.abs(v) / max) * 50}%`,
                width: `${(Math.abs(v) / max) * 50}%`,
                background: v >= 0 ? "linear-gradient(90deg, color-mix(in oklab, var(--color-block) 40%, transparent), var(--color-block))" : "linear-gradient(270deg, color-mix(in oklab, var(--color-allow) 40%, transparent), var(--color-allow))",
              }}
            />
          </div>
          <div className={`num text-right ${v >= 0 ? "text-block" : "text-allow"}`}>{v >= 0 ? "+" : ""}{v.toFixed(2)}</div>
        </div>
      ))}
      <div className="grid grid-cols-[150px_1fr_56px] gap-3 pt-1 text-[10.5px] text-faint">
        <span />
        <div className="flex justify-between"><span>← towards legitimate</span><span>towards fraud →</span></div>
        <span />
      </div>
    </div>
  );
}

function fmtFeature(f: string, v: number | undefined) {
  if (v == null) return "";
  if (f.endsWith("_log")) return `${Math.round(Math.expm1(v))}`;
  if (f.startsWith("is_")) return v ? "yes" : "no";
  if (f === "amount_ratio" || f === "spend_1h_ratio") return `${v.toFixed(1)}×`;
  if (f === "dist_from_home_km") return `${Math.round(v)} km`;
  if (f === "travel_speed_kmh") return `${Math.round(v)} km/h`;
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}
