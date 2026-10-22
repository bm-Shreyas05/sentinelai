import { Check, Copy, Plug, TerminalSquare } from "lucide-react";
import { useState } from "react";
import { Panel } from "../components/ui";
import { useConnect } from "../lib/api";
import { PageHeader } from "./Command";

function Code({ children }: { children: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="group relative">
      <pre className="overflow-x-auto rounded-xl border border-line bg-ink p-4 font-mono text-[12px] leading-relaxed text-dim">{children}</pre>
      <button
        onClick={() => { navigator.clipboard?.writeText(children).then(() => { setDone(true); setTimeout(() => setDone(false), 1200); }); }}
        className="absolute top-2.5 right-2.5 rounded-md border border-line-2 bg-panel-2 p-1.5 text-dim opacity-0 transition group-hover:opacity-100 hover:text-fg"
        aria-label="Copy"
      >
        {done ? <Check size={13} className="text-allow" /> : <Copy size={13} />}
      </button>
    </div>
  );
}

export function Connect() {
  const { data } = useConnect();
  const origin = window.location.origin;
  return (
    <div className="mx-auto max-w-[1100px]">
      <PageHeader title="API & MCP" sub="Everything on this console goes through the same REST API that payment switches and agents use." />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel eyebrow="REST" title={<span className="flex items-center gap-2"><TerminalSquare size={14} /> Score a payment</span>}>
          <Code>{`curl -X POST ${origin}/v1/transactions \\
  -H "X-API-Key: $SENTINEL_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"user_id":"U00042","amount":84000,
       "city":"Kolkata","device_id":"new-phone",
       "category":"electronics","channel":"upi"}'`}</Code>
          <p className="mt-3 text-[12.5px] text-dim">Interactive docs: <a className="text-saffron hover:underline" href="/docs" target="_blank" rel="noreferrer">{origin}/docs</a>. Bulk ingestion: <code className="font-mono">POST /v1/webhooks/transactions</code> with up to 1,000 payments.</p>
        </Panel>
        <Panel eyebrow="MCP" title={<span className="flex items-center gap-2"><Plug size={14} /> Claude Desktop, Claude Code or any MCP client</span>}>
          <Code>{JSON.stringify(data?.mcp ?? {}, null, 2)}</Code>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {data?.tools.map((t) => <span key={t} className="rounded-md bg-agent/10 px-2 py-0.5 font-mono text-[11px] text-agent">{t}</span>)}
          </div>
          <p className="mt-3 text-[12.5px] text-dim">The tools share this database, so an agent sees the same cases you do, and cases it opens show up under Agent activity.</p>
        </Panel>
      </div>
    </div>
  );
}
