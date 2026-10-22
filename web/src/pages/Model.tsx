import { CheckCircle2, Crown, Loader2, RefreshCcw, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button, Empty, Panel, Skeleton, cx } from "../components/ui";
import { runRetrain, useDrift, useModel } from "../lib/api";
import { dateTime, featureLabel, num, pct } from "../lib/format";
import type { OperatingPoint } from "../lib/types";
import { PageHeader } from "./Command";

const PSI_COLOR = { stable: "var(--color-allow)", warning: "var(--color-review)", critical: "var(--color-block)" };

export function Model() {
  const { data: m } = useModel();
  const { data: d } = useDrift();
  const qc = useQueryClient();
  const [retrain, setRetrain] = useState<{ busy: boolean; out?: { decision: string; reason: string }; err?: string }>({ busy: false });

  const current = m?.versions.find((v) => v.version === m.current);

  const go = async () => {
    setRetrain({ busy: true });
    try {
      const out = await runRetrain();
      setRetrain({ busy: false, out });
      qc.invalidateQueries({ queryKey: ["model"] });
      qc.invalidateQueries({ queryKey: ["drift"] });
    } catch (e) {
      setRetrain({ busy: false, err: (e as Error).message });
    }
  };

  return (
    <div className="mx-auto max-w-[1600px]">
      <PageHeader title="Model & drift" sub="The serving model, how it was chosen, and whether live traffic still looks like its training data." />

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-12">
        <section className="relative overflow-hidden rounded-2xl border border-line bg-panel p-5 xl:col-span-12">
          <div className="pointer-events-none absolute -top-32 left-1/3 size-80 rounded-full bg-agent/10 blur-3xl" />
          {!current ? <Skeleton className="h-28" /> : (
            <div className="relative flex flex-wrap items-center gap-8">
              <div>
                <div className="label flex items-center gap-1.5"><Crown size={12} className="text-saffron" /> Champion, serving now</div>
                <div className="num mt-1 text-2xl font-semibold">{current.version}</div>
                <div className="mt-1 text-[12.5px] text-dim">LightGBM · {current.features.length} features · trained {dateTime(current.trained_at)} IST</div>
                {current.notes && <div className="mt-0.5 text-[12px] text-faint">{current.notes}</div>}
              </div>
              <div className="flex flex-1 flex-wrap justify-end gap-3">
                <Stat label="PR-AUC" value={current.metrics.pr_auc.toFixed(3)} />
                <Stat label="ROC-AUC" value={current.metrics.roc_auc.toFixed(3)} />
                <OpPoint name="Block" p={current.metrics.block} color="var(--color-block)" />
                <OpPoint name="Review" p={current.metrics.review} color="var(--color-review)" />
              </div>
            </div>
          )}
        </section>

        <Panel className="xl:col-span-7" eyebrow="Feature drift" title="PSI against the training reference"
          action={d?.ready && <span className={cx("rounded-full px-2 py-0.5 text-[11px] font-medium", d.retrain_recommended ? "bg-block/15 text-block" : "bg-allow/10 text-allow")}>
            {d.retrain_recommended ? "retraining recommended" : "no retraining needed"}</span>}>
          {!d ? <Skeleton className="h-80" /> : !d.ready ? (
            <Empty title="Not enough traffic yet">Need {d.needed} scored transactions on this model; have {d.rows}.</Empty>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-3 gap-2">
                <Stat label="Score PSI" value={String(d.score_psi)} sub={d.score_status} small />
                <Stat label="Critical features" value={String(d.critical_features)} small />
                <Stat label="Window" value={num(d.rows)} sub="recent transactions" small />
              </div>
              <div className="space-y-1.5">
                {d.features?.map((f) => {
                  const max = Math.max(0.3, ...(d.features ?? []).map((x) => x.psi));
                  return (
                    <div key={f.feature} className="grid grid-cols-[160px_1fr_64px] items-center gap-3 text-[12px]">
                      <span className="truncate text-dim" title={f.feature}>{featureLabel(f.feature)}</span>
                      <div className="relative h-3.5 rounded-sm bg-panel-2">
                        <div className="absolute inset-y-0 border-l border-dashed border-review/50" style={{ left: `${(0.1 / max) * 100}%` }} />
                        <div className="absolute inset-y-0 border-l border-dashed border-block/50" style={{ left: `${(0.25 / max) * 100}%` }} />
                        <div className="h-full rounded-sm" style={{ width: `${Math.max(1, (f.psi / max) * 100)}%`, background: PSI_COLOR[f.status] }} />
                      </div>
                      <span className="num text-right" style={{ color: PSI_COLOR[f.status] }}>{f.psi.toFixed(3)}</span>
                    </div>
                  );
                })}
              </div>
              <p className="mt-3 text-[11.5px] text-faint">PSI &lt; 0.10 stable · 0.10–0.25 warning · &gt; 0.25 critical (policy FRF-3.1).</p>
            </>
          )}
        </Panel>

        <div className="space-y-3 xl:col-span-5">
          <Panel eyebrow="Champion / challenger" title="Retrain with analyst labels">
            <p className="text-[13px] leading-relaxed text-dim">
              Trains a challenger on fresh data plus <b className="num text-fg">{num(m?.labels ?? 0)}</b> analyst label(s), compares it with the
              champion on the newest held-out slice, and promotes it only if PR-AUC improves without losing review recall.
            </p>
            <Button variant="primary" className="mt-3" onClick={go} disabled={retrain.busy}>
              {retrain.busy ? <Loader2 size={14} className="animate-spin" /> : <RefreshCcw size={14} />}
              {retrain.busy ? "Training challenger…" : "Run retraining"}
            </Button>
            {retrain.out && (
              <div className={cx("mt-3 flex gap-2 rounded-lg border px-3 py-2.5 text-[12.5px]", retrain.out.decision === "PROMOTED" ? "border-allow/30 bg-allow/5" : "border-review/30 bg-review/5")}>
                {retrain.out.decision === "PROMOTED" ? <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-allow" /> : <TriangleAlert size={15} className="mt-0.5 shrink-0 text-review" />}
                <div><b>{retrain.out.decision}</b> <span className="num text-dim">{retrain.out.reason}</span></div>
              </div>
            )}
            {retrain.err && <p className="mt-2 text-[12.5px] text-block">{retrain.err}</p>}
          </Panel>

          {m?.benchmark && (
            <Panel eyebrow="Public benchmark" title="ULB credit-card fraud, time-ordered split">
              <div className="space-y-3">
                {Object.entries(m.benchmark.models).map(([name, b]) => (
                  <div key={name}>
                    <div className="flex justify-between text-[12.5px]">
                      <span className={name.includes("sentinel") ? "font-semibold" : "text-dim"}>{name.replace(/_/g, " ")}</span>
                      <span className="num">PR-AUC {b.pr_auc.toFixed(3)}</span>
                    </div>
                    <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-panel-3">
                      <div className={cx("h-full rounded-full", name.includes("sentinel") ? "bg-gradient-to-r from-saffron to-rose" : "bg-faint")} style={{ width: `${b.pr_auc * 100}%` }} />
                    </div>
                    <div className="num mt-1 text-[11px] text-faint">block {pct(b.block.precision, 0)} precision / {pct(b.block.recall, 0)} recall · review recall {pct(b.review.recall, 0)}</div>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[11.5px] text-faint">{num(m.benchmark.rows)} real transactions, {m.benchmark.test_frauds} frauds in the test period.</p>
            </Panel>
          )}
        </div>

        <Panel className="xl:col-span-12" pad={false} eyebrow="Registry" title="Model versions">
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead><tr className="text-left">{["", "Version", "PR-AUC", "Block precision", "Block recall", "Review recall", "Thresholds", "Decision", "Notes"].map((h) => <th key={h} className="label border-b border-line px-3 py-2 first:pl-4">{h}</th>)}</tr></thead>
              <tbody>
                {m?.versions.slice().reverse().map((v) => (
                  <tr key={v.version} className={cx("border-b border-line/60", v.version === m.current && "bg-saffron/5")}>
                    <td className="py-2 pl-4">{v.version === m.current && <Crown size={13} className="text-saffron" />}</td>
                    <td className="num px-3 py-2">{v.version}</td>
                    <td className="num px-3 py-2">{v.metrics.pr_auc.toFixed(4)}</td>
                    <td className="num px-3 py-2">{pct(v.metrics.block.precision)}</td>
                    <td className="num px-3 py-2">{pct(v.metrics.block.recall)}</td>
                    <td className="num px-3 py-2">{pct(v.metrics.review.recall)}</td>
                    <td className="num px-3 py-2 text-dim">{v.thresholds.review.toFixed(3)} / {v.thresholds.block.toFixed(3)}</td>
                    <td className="px-3 py-2">{v.metrics.comparison?.decision ?? <span className="text-faint">initial</span>}</td>
                    <td className="max-w-[360px] truncate px-3 py-2 text-dim" title={v.metrics.comparison?.reason ?? v.notes}>{v.metrics.comparison?.reason ?? v.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Stat({ label, value, sub, small }: { label: string; value: string; sub?: string; small?: boolean }) {
  return (
    <div className={cx("rounded-xl border border-line bg-panel-2/60", small ? "px-3 py-2" : "min-w-[110px] px-4 py-3")}>
      <div className="label text-[9.5px]">{label}</div>
      <div className={cx("num mt-0.5 font-semibold", small ? "text-[16px]" : "text-[22px]")}>{value}</div>
      {sub && <div className="text-[11px] text-faint">{sub}</div>}
    </div>
  );
}

function OpPoint({ name, p, color }: { name: string; p: OperatingPoint; color: string }) {
  return (
    <div className="min-w-[180px] rounded-xl border border-line bg-panel-2/60 px-4 py-3">
      <div className="label text-[9.5px]" style={{ color }}>{name} at ≥ {p.threshold.toFixed(3)}</div>
      <div className="mt-1 flex gap-5">
        <div><div className="num text-[22px] font-semibold">{pct(p.precision, 0)}</div><div className="text-[11px] text-faint">precision</div></div>
        <div><div className="num text-[22px] font-semibold">{pct(p.recall, 0)}</div><div className="text-[11px] text-faint">recall</div></div>
      </div>
    </div>
  );
}
