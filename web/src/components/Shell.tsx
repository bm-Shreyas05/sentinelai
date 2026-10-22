import {
  Activity, Bot, BookOpenText, Command, FlaskConical, Inbox, LogOut, Pause, Play, Plug, Radar, ScrollText, Search,
} from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { setKey, useCases, useOverview, useTraffic } from "../lib/api";
import { inr } from "../lib/format";
import { cx } from "./ui";

export const NAV = [
  { to: "/", label: "Command center", icon: Radar, end: true, key: "g c" },
  { to: "/cases", label: "Case queue", icon: Inbox, key: "g q" },
  { to: "/agent", label: "Agent activity", icon: Bot, key: "g a" },
  { to: "/playground", label: "Score a payment", icon: FlaskConical, key: "g s" },
  { to: "/model", label: "Model & drift", icon: Activity, key: "g m" },
  { to: "/policy", label: "Policy assistant", icon: BookOpenText, key: "g p" },
  { to: "/audit", label: "Audit log", icon: ScrollText, key: "g l" },
  { to: "/connect", label: "API & MCP", icon: Plug, key: "g i" },
];

export function Logo({ size = 28 }: { size?: number }) {
  const id = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ff9a3c" />
          <stop offset="1" stopColor="#ff3d71" />
        </linearGradient>
      </defs>
      <path d="M16 2 4 7v8c0 7.5 5.1 13.4 12 15 6.9-1.6 12-7.5 12-15V7z" fill={`url(#${id})`} />
      <path d="m10.5 16 3.8 3.8 7.4-7.6" fill="none" stroke="#05070b" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function TrafficControl() {
  const { data } = useOverview();
  const t = useTraffic();
  const running = data?.traffic.running ?? false;
  const rate = data?.traffic.rate ?? 5;
  return (
    <div className="flex items-center gap-2 rounded-xl border border-line bg-panel-2/80 py-1 pr-1 pl-3">
      <span className="relative flex size-2">
        {running && <span className="absolute inset-0 animate-pulse-ring rounded-full bg-allow" />}
        <span className={cx("relative size-2 rounded-full", running ? "bg-allow" : "bg-faint")} />
      </span>
      <span className="hidden text-[12px] text-dim sm:inline">{running ? "Live demo traffic" : "Traffic paused"}</span>
      <select
        aria-label="Transactions per second"
        value={rate}
        onChange={(e) => t.mutate({ rate: Number(e.target.value) })}
        className="num rounded-md border border-line bg-panel px-1.5 py-1 text-[12px] text-fg outline-none"
      >
        {[1, 2, 5, 10, 20, 30].map((r) => <option key={r} value={r}>{r} tx/s</option>)}
      </select>
      <button
        onClick={() => t.mutate({ running: !running })}
        className={cx(
          "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[12px] font-semibold transition",
          running ? "bg-panel-3 text-fg hover:bg-line-2" : "bg-gradient-to-r from-saffron to-rose text-ink hover:brightness-110",
        )}
      >
        {running ? <Pause size={12} /> : <Play size={12} />} {running ? "Pause" : "Start"}
      </button>
    </div>
  );
}

function Ticker() {
  const { data } = useOverview();
  if (!data) return null;
  const m = data.metrics;
  return (
    <div className="hidden items-center gap-5 text-[12px] text-dim lg:flex">
      <span>Scored <b className="num font-semibold text-fg">{m.transactions.toLocaleString("en-IN")}</b></span>
      <span>Held <b className="num font-semibold text-block">{inr(m.blocked_amount, true)}</b></span>
      <span>Model <b className="num font-semibold text-fg">{m.model_version}</b></span>
    </div>
  );
}

export function Shell() {
  const [palette, setPalette] = useState(false);
  const { data: open } = useCases("open", 500);
  const nav = useNavigate();
  const loc = useLocation();

  useEffect(() => {
    let g = false, timer = 0;
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement)?.closest("input, textarea, select");
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); return; }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "/") { e.preventDefault(); setPalette(true); return; }
      if (g) {
        const hit = NAV.find((n) => n.key === `g ${e.key}`);
        g = false;
        if (hit) { e.preventDefault(); nav(hit.to); }
        return;
      }
      if (e.key === "g") { g = true; clearTimeout(timer); timer = window.setTimeout(() => (g = false), 900); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nav]);

  const critical = open?.filter((c) => c.priority === "critical").length ?? 0;

  return (
    <div className="backdrop flex min-h-full">
      <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 flex-col border-r border-line bg-panel/60 backdrop-blur-xl md:flex">
        <div className="flex items-center gap-2.5 px-5 pt-5 pb-6">
          <Logo />
          <div>
            <div className="text-[15px] font-semibold tracking-tight">Sentinel<span className="brand-text">AI</span></div>
            <div className="text-[10.5px] tracking-wide text-faint">Fraud operations · India</div>
          </div>
        </div>
        <button
          onClick={() => setPalette(true)}
          className="mx-3 mb-4 flex items-center gap-2 rounded-lg border border-line bg-panel-2 px-2.5 py-1.5 text-[12.5px] text-faint transition hover:border-line-2 hover:text-dim"
        >
          <Search size={13} /> Jump to…
          <kbd className="ml-auto flex items-center gap-0.5 rounded border border-line-2 px-1 font-mono text-[10px]"><Command size={9} />K</kbd>
        </button>
        <nav className="flex flex-1 flex-col gap-0.5 px-3">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cx(
                  "group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition",
                  isActive || (to === "/cases" && loc.pathname.startsWith("/cases"))
                    ? "bg-panel-3 text-fg shadow-[inset_0_0_0_1px_var(--color-line-2)]"
                    : "text-dim hover:bg-panel-2 hover:text-fg",
                )
              }
            >
              {({ isActive }) => (
                <>
                  {(isActive || (to === "/cases" && loc.pathname.startsWith("/cases"))) && (
                    <span className="absolute top-2 bottom-2 -left-3 w-[3px] rounded-r bg-gradient-to-b from-saffron to-rose" />
                  )}
                  <Icon size={15} className="shrink-0" />
                  {label}
                  {to === "/cases" && open && open.length > 0 && (
                    <span className={cx("num ml-auto rounded-full px-1.5 py-px text-[10.5px] font-semibold", critical ? "bg-block/15 text-block" : "bg-panel-3 text-dim")}>
                      {open.length}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="m-3 rounded-xl border border-line bg-panel-2/60 p-3 text-[11.5px] leading-relaxed text-faint">
          Amounts in INR, times in IST. Scores are probabilities from the serving LightGBM model.
          <button onClick={() => setKey(null)} className="mt-2 flex items-center gap-1.5 text-dim hover:text-fg">
            <LogOut size={12} /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-4 border-b border-line bg-ink/75 px-4 backdrop-blur-xl md:px-6">
          <div className="flex items-center gap-3">
            <div className="md:hidden"><Logo size={24} /></div>
            <Ticker />
          </div>
          <TrafficControl />
        </header>
        <nav className="flex shrink-0 gap-1 overflow-x-auto border-b border-line px-3 py-2 md:hidden">
          {NAV.map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => cx("shrink-0 rounded-md px-2.5 py-1 text-[12px]", isActive ? "bg-panel-3 text-fg" : "text-dim")}>
              {label}
            </NavLink>
          ))}
        </nav>
        <main className="min-w-0 flex-1 px-4 py-5 md:px-6">
          <Outlet />
        </main>
      </div>
      {palette && <Palette onClose={() => setPalette(false)} />}
    </div>
  );
}

function Palette({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const nav = useNavigate();
  const t = useTraffic();
  const { data: ov } = useOverview();
  const { data: open } = useCases("open", 500);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => input.current?.focus(), []);

  const items = useMemo(() => {
    const out: { label: ReactNode; hint?: string; text: string; run: () => void }[] = [];
    const id = q.match(/^#?(\d+)$/)?.[1];
    if (id) out.push({ label: <>Open case <b className="num">#{id}</b></>, text: q, run: () => nav(`/cases/${id}`) });
    NAV.forEach((n) => out.push({ label: n.label, hint: n.key, text: n.label, run: () => nav(n.to) }));
    out.push({
      label: ov?.traffic.running ? "Pause demo traffic" : "Start demo traffic",
      text: "traffic demo start pause stop",
      run: () => t.mutate({ running: !ov?.traffic.running }),
    });
    (open ?? []).slice(0, 30).forEach((c) =>
      out.push({
        label: <><span className="num">#{c.case_id}</span> · {inr(c.amount)} · {c.city} <span className="text-faint">· {c.priority} · {c.user_id}</span></>,
        text: `${c.case_id} ${c.user_id} ${c.city} ${c.priority} ${c.decision} ${c.txn_id}`,
        run: () => nav(`/cases/${c.case_id}`),
      }),
    );
    const needle = q.toLowerCase().replace(/^#/, "");
    return needle ? out.filter((i) => i.text.toLowerCase().includes(needle)) : out;
  }, [q, open, ov, nav, t]);

  const go = (i: number) => { items[i]?.run(); onClose(); };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-ink/70 px-4 pt-[14vh] backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-xl animate-fade-up overflow-hidden rounded-2xl border border-line-2 bg-panel shadow-2xl shadow-black/60" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Search size={16} className="text-faint" />
          <input
            ref={input}
            value={q}
            onChange={(e) => { setQ(e.target.value); setSel(0); }}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(items.length - 1, s + 1)); }
              if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
              if (e.key === "Enter") go(sel);
            }}
            placeholder="Search pages, open cases, or type a case number…"
            className="h-12 flex-1 bg-transparent text-[14px] outline-none placeholder:text-faint"
          />
          <kbd className="rounded border border-line-2 px-1.5 font-mono text-[10px] text-faint">esc</kbd>
        </div>
        <ul className="max-h-[50vh] overflow-y-auto p-1.5">
          {items.length === 0 && <li className="px-3 py-6 text-center text-[13px] text-faint">Nothing matches.</li>}
          {items.map((it, i) => (
            <li key={i}>
              <button
                onMouseEnter={() => setSel(i)}
                onClick={() => go(i)}
                className={cx("flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-[13px]", i === sel ? "bg-panel-3 text-fg" : "text-dim")}
              >
                <span className="truncate">{it.label}</span>
                {it.hint && <kbd className="font-mono text-[10.5px] text-faint">{it.hint}</kbd>}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
