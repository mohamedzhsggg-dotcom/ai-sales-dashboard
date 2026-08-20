import { clsx } from "clsx";
import type { ReactNode } from "react";

export function Badge({ children, color = "slate" }: { children: ReactNode; color?: string }) {
  const colors: Record<string, string> = {
    slate: "bg-slate-100 text-slate-700",
    blue: "bg-blue-100 text-blue-700",
    green: "bg-emerald-100 text-emerald-700",
    amber: "bg-amber-100 text-amber-700",
    red: "bg-red-100 text-red-700",
  };
  return (
    <span className={clsx("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", colors[color])}>
      {children}
    </span>
  );
}

export function statusColor(status: string): string {
  switch (status) {
    case "new":
      return "blue";
    case "confirmed":
      return "green";
    case "shipped":
      return "amber";
    case "delivered":
      return "green";
    case "cancelled":
      return "red";
    default:
      return "slate";
  }
}

export function formatPrice(v?: number | null): string {
  if (v == null) return "—";
  return `${v.toLocaleString("fr-DZ")} DZD`;
}

export function formatDate(iso?: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-DZ", { dateStyle: "short", timeStyle: "short" });
}

export function Pagination({
  page,
  total,
  limit,
  onChange,
}: {
  page: number;
  total: number;
  limit: number;
  onChange: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3">
      <p className="text-sm text-slate-600">
        Page {page} of {pages} · {total} results
      </p>
      <div className="flex gap-2">
        <button
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          className="rounded-md border border-slate-300 px-3 py-1 text-sm disabled:opacity-40"
        >
          Previous
        </button>
        <button
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
          className="rounded-md border border-slate-300 px-3 py-1 text-sm disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <input
      type="search"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
    />
  );
}