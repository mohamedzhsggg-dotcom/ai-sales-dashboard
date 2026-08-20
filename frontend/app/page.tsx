"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Shell from "@/components/shell";
import { Badge, formatDate, formatPrice, statusColor } from "@/components/ui";
import { useAuth } from "@/lib/useAuth";
import { api, DashboardStats } from "@/lib/api";

export default function DashboardPage() {
  useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch((e) => setError(e.message));
  }, []);

  const cards = stats
    ? [
        { label: "New orders", value: stats.new_orders, color: "bg-blue-50 text-blue-700" },
        { label: "Confirmed", value: stats.confirmed_orders, color: "bg-emerald-50 text-emerald-700" },
        { label: "Total revenue", value: formatPrice(stats.total_revenue), color: "bg-slate-50 text-slate-700" },
        { label: "Low stock", value: stats.low_stock_count, color: "bg-amber-50 text-amber-700" },
      ]
    : [];

  return (
    <Shell>
      <div className="space-y-6">
        <h2 className="text-xl font-semibold text-slate-800">Overview</h2>
        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((c) => (
            <div key={c.label} className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-sm text-slate-500">{c.label}</p>
              <p className={`mt-2 inline-block rounded-md px-2 py-1 text-2xl font-semibold ${c.color}`}>{c.value}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold text-slate-700">Orders by Wilaya</h3>
            <ul className="mt-3 space-y-2">
              {stats?.by_wilaya.slice(0, 8).map((w) => (
                <li key={w.wilaya} className="flex items-center justify-between text-sm">
                  <span className="text-slate-600">{w.wilaya || "Unknown"}</span>
                  <span className="font-medium">{w.count}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold text-slate-700">Recent orders</h3>
            <ul className="mt-3 divide-y divide-slate-100">
              {stats?.recent_orders.map((o) => (
                <li key={o.id} className="flex items-center justify-between py-2 text-sm">
                  <div>
                    <span className="font-medium">{o.name || o.phone || "—"}</span>
                    <span className="ml-2 text-xs text-slate-400">{o.product}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">{formatDate(o.created_at)}</span>
                    <Badge color={statusColor(o.status)}>{o.status}</Badge>
                  </div>
                </li>
              ))}
            </ul>
            <Link href="/orders" className="mt-3 inline-block text-sm font-medium text-brand-600 hover:text-brand-700">
              View all orders →
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  );
}