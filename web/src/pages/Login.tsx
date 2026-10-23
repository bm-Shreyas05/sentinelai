import { ArrowRight, KeyRound } from "lucide-react";
import { useState } from "react";
import { Logo } from "../components/Shell";
import { Button } from "../components/ui";
import { api, ApiError, setKey } from "../lib/api";

export function Login() {
  const [key, setValue] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await api("/v1/metrics", { key: key.trim() });
      setKey(key.trim());
    } catch (x) {
      setErr(x instanceof ApiError && x.status === 401 ? "That key was not accepted." : "Could not reach the SentinelAI API.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="backdrop relative flex min-h-full items-center justify-center overflow-hidden px-4">
      <div className="pointer-events-none absolute top-1/2 left-1/2 size-[640px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-line/60" />
      <div className="pointer-events-none absolute top-1/2 left-1/2 size-[920px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-line/40" />
      <div className="pointer-events-none absolute top-1/2 left-1/2 size-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-rose/10 blur-[120px]" />
      <form onSubmit={submit} className="panel relative w-full max-w-sm animate-fade-up p-7 shadow-2xl shadow-black/50">
        <Logo size={40} />
        <h1 className="mt-5 text-xl font-semibold tracking-tight">Sentinel<span className="brand-text">AI</span> console</h1>
        <p className="mt-1.5 text-[13px] leading-relaxed text-dim">
          Real-time fraud scoring, explanations and case management for Indian payments.
        </p>
        <label className="label mt-6 mb-1.5 block" htmlFor="key">API key</label>
        <div className="flex items-center gap-2 rounded-lg border border-line-2 bg-ink px-3 focus-within:border-saffron/60">
          <KeyRound size={14} className="text-faint" />
          <input
            id="key"
            type="password"
            autoFocus
            value={key}
            onChange={(e) => setValue(e.target.value)}
            placeholder="X-API-Key"
            className="h-10 flex-1 bg-transparent font-mono text-[13px] outline-none placeholder:text-faint"
          />
        </div>
        {err && <p className="mt-2 text-[12.5px] text-block">{err}</p>}
        <Button type="submit" variant="primary" className="mt-5 w-full py-2" disabled={!key.trim() || busy}>
          {busy ? "Checking…" : <>Enter console <ArrowRight size={14} /></>}
        </Button>
        <p className="mt-5 text-[11.5px] leading-relaxed text-faint">
          Keys come from <code className="font-mono text-dim">SENTINEL_API_KEYS</code>. On a hosted deploy, ask
          whoever runs it for a key.
        </p>
      </form>
    </div>
  );
}
