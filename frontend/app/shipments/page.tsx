"use client";

import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Badge, Pagination, SearchInput, formatDate, formatPrice, statusColor } from "@/components/ui";
import { api, type Shipment, type Page } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";

export default function ShipmentsPage() {
  useAuth();
  const [data, setData] = useState<Page<Shipment> | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.shipments({ page, limit: 20, search: search || undefined })
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, search]);

  return (
    <Shell>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Shipments</h2>
        </div>
        <div className="w-full max-w-sm">
          <SearchInput value={search} onChange={setSearch} placeholder="Search by tracking number..." />
        </div>
        {loading ? (
          <p className="text-sm text-slate-500">Loading...</p>
        ) : !data || data.items.length === 0 ? (
          <p className="text-sm text-slate-500">No shipments found.</p>
        ) : (
          <>
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Order</th>
                    <th className="px-4 py-3">Courier</th>
                    <th className="px-4 py-3">Tracking</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Amount</th>
                    <th className="px-4 py-3">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((s) => (
                    <tr key={s.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3">
                        <Link href={`/orders/${s.order_id}`} className="text-brand-600 hover:underline">
                          #{s.order_id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 capitalize">{s.courier_name}</td>
                      <td className="px-4 py-3 font-mono text-xs">{s.tracking_number || "—"}</td>
                      <td className="px-4 py-3">
                        <Badge color={statusColor(s.status)}>{s.status}</Badge>
                      </td>
                      <td className="px-4 py-3">{formatPrice(s.cod_amount)}</td>
                      <td className="px-4 py-3 text-xs text-slate-500">{formatDate(s.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} total={data.total} limit={data.limit} onChange={setPage} />
          </>
        )}
      </div>
    </Shell>
  );
}
