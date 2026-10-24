import { useEffect, useState } from "react";
import { Route, Routes } from "react-router";
import { Shell } from "./components/Shell";
import { getKey, queryClient } from "./lib/api";
import { Agent } from "./pages/Agent";
import { Audit } from "./pages/Audit";
import { CaseQueue } from "./pages/Cases";
import { Command } from "./pages/Command";
import { Connect } from "./pages/Connect";
import { Investigation } from "./pages/Investigation";
import { Login } from "./pages/Login";
import { Model } from "./pages/Model";
import { Playground } from "./pages/Playground";
import { Policy } from "./pages/Policy";

export function App() {
  const [key, setKeyState] = useState(getKey());
  // null until /health says whether visitors may browse without a key
  const [publicRead, setPublicRead] = useState<boolean | null>(null);
  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((h) => setPublicRead(Boolean(h.public_read)))
      .catch(() => setPublicRead(false));
  }, []);
  useEffect(() => {
    const sync = () => {
      setKeyState(getKey());
      queryClient.clear();
    };
    window.addEventListener("sentinel-auth", sync);
    return () => window.removeEventListener("sentinel-auth", sync);
  }, []);

  if (!key && publicRead === null) return null;
  if (!key && !publicRead) return <Login />;
  return (
    <Routes>
      <Route path="login" element={<Login canBrowse={!key} />} />
      <Route element={<Shell />}>
        <Route index element={<Command />} />
        <Route path="cases" element={<CaseQueue />} />
        <Route path="cases/:id" element={<Investigation />} />
        <Route path="agent" element={<Agent />} />
        <Route path="playground" element={<Playground />} />
        <Route path="model" element={<Model />} />
        <Route path="policy" element={<Policy />} />
        <Route path="audit" element={<Audit />} />
        <Route path="connect" element={<Connect />} />
        <Route path="*" element={<Command />} />
      </Route>
    </Routes>
  );
}
