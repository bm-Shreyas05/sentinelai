import { Link } from "react-router";
import { Panel, Skeleton } from "../components/ui";
import { useAudit } from "../lib/api";
import { brief, clock, dateTime, human } from "../lib/format";
import { PageHeader } from "./Command";

const ACTION_COLOR: Record<string, string> = {
  case_opened: "var(--color-info)",
  case_resolved: "var(--color-allow)",
  retrain_run: "var(--color-agent)",
};

export function Audit() {
  const { data } = useAudit(150);
  return (
    <div className="mx-auto max-w-[1200px]">
      <PageHeader title="Audit log" sub="Append-only record of who did what: cases opened by the agent, analyst resolutions, retraining runs. Retained with transaction records (AML-3.2)." />
      <Panel pad={false}>
        <ol className="divide-y divide-line/60">
          {!data && Array.from({ length: 10 }, (_, i) => <li key={i} className="p-3"><Skeleton className="h-6" /></li>)}
          {data?.map((a) => {
            const c = ACTION_COLOR[a.action] ?? "var(--color-dim)";
            const caseId = a.detail?.case_id as number | undefined;
            return (
              <li key={a.id} className="grid grid-cols-[150px_120px_1fr] items-center gap-4 px-4 py-2.5 text-[12.5px] hover:bg-panel-2/50 max-md:grid-cols-1 max-md:gap-1">
                <span className="num text-faint" title={dateTime(a.ts)}>{dateTime(a.ts).replace(/,.*/, "")} · {clock(a.ts)}</span>
                <span className="flex items-center gap-2"><span className="size-1.5 rounded-full" style={{ background: c }} /><span className="truncate font-mono text-dim">{a.actor}</span></span>
                <span className="min-w-0 truncate">
                  <span className="font-medium" style={{ color: c }}>{human(a.action)}</span>
                  {caseId != null && <> · <Link to={`/cases/${caseId}`} className="num text-fg hover:text-saffron">case #{caseId}</Link></>}
                  <span className="ml-2 font-mono text-[11.5px] text-faint">{brief(Object.fromEntries(Object.entries(a.detail ?? {}).filter(([k]) => k !== "case_id")), 140)}</span>
                </span>
              </li>
            );
          })}
        </ol>
      </Panel>
    </div>
  );
}
