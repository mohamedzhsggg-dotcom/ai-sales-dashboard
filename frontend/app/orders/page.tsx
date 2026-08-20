"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Shell from "@/components/shell";
import { Badge, Pagination, SearchInput, formatPrice, statusColor } from "@/components/ui";
import { useAuth } from "@/lib/useAuth";
import { api, Order } from "@/lib/api";

export default function OrdersPage() {
  useAuth();
  const [items, setItems] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [wilaya, setWilaya] = useState("");
  const [channel, setChannel] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOrders = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.orders({ page, search, status, wilaya, channel, limit: 20 });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load orders");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(fetchOrders, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, search, status, wilaya, channel]);

  return (
    <Shell>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-800">Orders</h2>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <SearchInput value={search} onChange={setSearch} placeholder="Search name, phone, order ID..." />
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">All statuses</option>
            <option value="new">New</option>
            <option value="confirmed">Confirmed</option>
            <option value="shipped">Shipped</option>
            <option value="delivered">Delivered</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <input
            value={wilaya}
            onChange={(e) => {
              setWilaya(e.target.value);
              setPage(1);
            }}
            placeholder="Wilaya"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
          />
          <select
            value={channel}
            onChange={(e) => {
              setChannel(e.target.value);
              setPage(1);
            }}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">All channels</option>
            <option value="facebook">Facebook</option>
            <option value="instagram">Instagram</option>
            <option value="comment">Comment</option>
          </select>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Order</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Qty</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Wilaya</th>
                <th className="px-4 py-3">Channel</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((o) => (
                <tr key={o.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-brand-700">{o.order_id || `#${o.id}`}</td>
                  <td className="px-4 py-3">
                    <div>{o.name || "—"}</div>
                    <div className="text-xs text-slate-400">{o.phone || ""}</div>
                  </td>
                  <td className="px-4 py-3">
                    {o.product}
                    {o.color || o.size ? (
                      <div className="text-xs text-slate-400">
                        {o.color} {o.size}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">{o.quantity ?? 1}</td>
                  <td className="px-4 py-3">{formatPrice((o.price ?? 0) * (o.quantity ?? 1))}</td>
                  <td className="px-4 py-3">{o.wilaya || "—"}</td>
                  <td className="px-4 py-3">
                    <Badge color={o.source_channel === "instagram" ? "amber" : "blue"}>
                      {o.source_channel || "—"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge color={statusColor(o.status)}>{o.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {new Date(o.created_at).toLocaleDateString("fr-DZ")}
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/orders/${o.id}`} className="font-medium text-brand-600 hover:text-brand-700">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && items.length === 0 && (
            <div className="px-4 py-10 text-center text-sm text-slate-400">No orders found.</div>
          )}
          <Pagination page={page} total={total} limit={20} onChange={setPage} />
        </div>
      </div>
    </Shell>
  );
}