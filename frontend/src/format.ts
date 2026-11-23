export const tagTitle = (tag: string) => tag.charAt(0).toUpperCase() + tag.slice(1);

export const signed = (n: number) => `${n >= 0 ? "+" : "−"}${Math.abs(Math.round(n))}`;

export const pct = (n: number | null | undefined, digits = 0) =>
  n == null ? "—" : `${(n * 100).toFixed(digits)}%`;

export const int = (n: number | null | undefined) =>
  n == null ? "—" : Math.round(n).toLocaleString("en-US");

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const secs = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.round(secs / 60)} min ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)} h ago`;
  return `${Math.round(secs / 86400)} days ago`;
}

export const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-US", { month: "short", year: "2-digit" });

export const dayMonth = (iso: string) =>
  new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });

export const LABEL_TEXT: Record<string, string> = {
  weak: "Weak",
  average: "Average",
  strong: "Strong",
  insufficient: "Not enough data",
};

export const labelColor = (label: string) =>
  label === "weak" ? "var(--neg)" : label === "strong" ? "var(--pos)" : "var(--mid)";
