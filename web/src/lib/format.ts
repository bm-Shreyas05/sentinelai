import type { Decision, Priority } from "./types";

/** Indian digit grouping: ₹12,34,567 */
export function inr(x: number, compact = false): string {
  if (compact) {
    const a = Math.abs(x);
    if (a >= 1e7) return `₹${(x / 1e7).toFixed(a >= 1e8 ? 0 : 1)} Cr`;
    if (a >= 1e5) return `₹${(x / 1e5).toFixed(a >= 1e6 ? 0 : 1)} L`;
    if (a >= 1e3) return `₹${(x / 1e3).toFixed(a >= 1e4 ? 0 : 1)}K`;
  }
  return `${x < 0 ? "-" : ""}₹${Math.round(Math.abs(x)).toLocaleString("en-IN")}`;
}

export const num = (x: number) => x.toLocaleString("en-IN");
export const pct = (x: number, d = 1) => `${(x * 100).toFixed(d)}%`;

const IST: Intl.DateTimeFormatOptions = { timeZone: "Asia/Kolkata", hour12: false };

export const clock = (epoch: number) =>
  new Date(epoch * 1000).toLocaleTimeString("en-IN", { ...IST, hour: "2-digit", minute: "2-digit", second: "2-digit" });

export const hm = (epoch: number) =>
  new Date(epoch * 1000).toLocaleTimeString("en-IN", { ...IST, hour: "2-digit", minute: "2-digit" });

export const dateTime = (epoch: number) =>
  new Date(epoch * 1000).toLocaleString("en-IN", { ...IST, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

export function ago(epoch: number, now = Date.now() / 1000): string {
  const s = Math.max(0, Math.round(now - epoch));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export const DECISION_COLOR: Record<Decision, string> = {
  BLOCK: "var(--color-block)",
  REVIEW: "var(--color-review)",
  ALLOW: "var(--color-allow)",
};

export const PRIORITY_COLOR: Record<Priority, string> = {
  critical: "var(--color-block)",
  high: "var(--color-saffron)",
  normal: "var(--color-review)",
};

export const titleCase = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
export const human = (s: string) => s.replace(/_/g, " ");

/** Short, readable rendering of a trace step's input or output. */
export function brief(v: unknown, limit = 160): string {
  let s: string;
  if (v == null) s = "none";
  else if (Array.isArray(v)) s = v.map((x) => brief(x, 40)).join(", ") || "none";
  else if (typeof v === "object")
    s = Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k}=${brief(x, 40)}`).join(", ");
  else s = String(v);
  return s.length <= limit ? s : s.slice(0, limit - 1) + "…";
}

export const FEATURE_LABEL: Record<string, string> = {
  amount_log: "Amount",
  amount_ratio: "Amount vs usual",
  history_log: "Customer history",
  tx_count_5min: "Payments in 5 min",
  tx_count_1h: "Payments in 1 h",
  spend_1h_ratio: "Spend in last hour",
  secs_since_last_log: "Time since last",
  is_new_device: "New device",
  device_user_count: "Accounts on device",
  is_new_city: "New city",
  dist_from_home_km: "Distance from home",
  travel_speed_kmh: "Travel speed",
  hour: "Hour of day",
  is_night: "Night-time",
  merchant_risk: "Merchant risk",
  is_new_category: "New category",
  channel_code: "Channel",
  is_new_payee: "New payee",
  payee_fan_in_log: "Payee fan-in",
};

export const featureLabel = (f: string) => FEATURE_LABEL[f] ?? human(f);
