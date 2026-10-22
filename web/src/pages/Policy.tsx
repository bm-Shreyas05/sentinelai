import { BookOpenText, CornerDownLeft, Loader2, ShieldQuestion } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Panel, cx } from "../components/ui";
import { askPolicy } from "../lib/api";
import type { PolicyAnswer } from "../lib/types";
import { PageHeader } from "./Command";

const QUICK = [
  "When do we file an STR?",
  "What if a card is used in two cities quickly?",
  "Is the customer refunded while we investigate?",
  "What PSI triggers retraining?",
  "Can we tell the customer about an STR?",
];

type Turn = { q: string; a?: PolicyAnswer; err?: string };

export function Policy() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [turns]);

  const ask = async (question: string) => {
    if (question.trim().length < 3 || busy) return;
    setQ("");
    setBusy(true);
    setTurns((t) => [...t, { q: question }]);
    try {
      const a = await askPolicy(question);
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, a } : x)));
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, err: (e as Error).message } : x)));
    }
    setBusy(false);
  };

  return (
    <div className="mx-auto max-w-[980px]">
      <PageHeader title="Policy assistant" sub="Answers come only from the Markdown files in policies/ and always cite a clause. When nothing matches, it says so." />
      <Panel pad={false} className="min-h-[60vh]">
        <div className="flex min-h-[60vh] flex-col">
          <div className="flex-1 space-y-5 p-5">
            {turns.length === 0 && (
              <div className="flex flex-col items-center py-10 text-center">
                <span className="flex size-12 items-center justify-center rounded-2xl bg-agent/10 text-agent ring-1 ring-agent/30"><BookOpenText size={22} /></span>
                <p className="mt-4 text-[14px] font-medium">Ask anything the fraud, AML or customer-protection policies cover</p>
                <div className="mt-5 flex max-w-2xl flex-wrap justify-center gap-2">
                  {QUICK.map((x) => (
                    <button key={x} onClick={() => ask(x)} className="rounded-full border border-line-2 bg-panel-2 px-3 py-1.5 text-[12.5px] text-dim transition hover:border-agent/50 hover:text-fg">{x}</button>
                  ))}
                </div>
              </div>
            )}
            {turns.map((t, i) => (
              <div key={i} className="animate-fade-up space-y-3">
                <div className="flex justify-end"><div className="max-w-[80%] rounded-2xl rounded-br-md bg-panel-3 px-4 py-2.5 text-[13.5px]">{t.q}</div></div>
                <div className="flex gap-3">
                  <span className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-lg bg-agent/15 text-agent"><ShieldQuestion size={14} /></span>
                  <div className="min-w-0 flex-1">
                    {!t.a && !t.err && <Loader2 size={16} className="mt-1.5 animate-spin text-faint" />}
                    {t.err && <p className="text-[13px] text-block">{t.err}</p>}
                    {t.a && (t.a.abstained ? (
                      <div className="rounded-xl border border-review/30 bg-review/5 px-4 py-3 text-[13.5px]">{t.a.message}</div>
                    ) : (
                      <>
                        <div className={cx("rounded-xl border px-4 py-3 text-[13.5px] leading-relaxed", t.a.confidence === "high" ? "border-line-2 bg-panel-2/60" : "border-review/30 bg-review/5")}>
                          {t.a.answer}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {t.a.citations.map((c) => (
                            <span key={c.id} title={c.text} className="inline-flex items-center gap-2 rounded-lg border border-line bg-panel-2 px-2 py-1 text-[11.5px]">
                              <b className="num text-agent">{c.id}</b><span className="text-dim">{c.document}</span><span className="num text-faint">{c.score.toFixed(2)}</span>
                            </span>
                          ))}
                          <span className={cx("rounded-lg px-2 py-1 text-[11px]", t.a.confidence === "high" ? "text-allow" : "text-review")}>{t.a.confidence} confidence</span>
                        </div>
                      </>
                    ))}
                  </div>
                </div>
              </div>
            ))}
            <div ref={end} />
          </div>
          <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="sticky bottom-0 border-t border-line bg-panel/90 p-3 backdrop-blur">
            <div className="flex items-center gap-2 rounded-xl border border-line-2 bg-ink px-3 focus-within:border-agent/60">
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. What do we do with a mule account?" className="h-11 flex-1 bg-transparent text-[13.5px] outline-none placeholder:text-faint" />
              <button disabled={busy || q.trim().length < 3} className="flex items-center gap-1.5 rounded-lg bg-agent/15 px-2.5 py-1.5 text-[12px] font-medium text-agent disabled:opacity-40">
                Ask <CornerDownLeft size={12} />
              </button>
            </div>
          </form>
        </div>
      </Panel>
    </div>
  );
}
