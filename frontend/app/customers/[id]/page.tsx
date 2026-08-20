"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Shell from "@/components/shell";
import { Badge, formatDate, formatPrice, statusColor } from "@/components/ui";
import { useAuth } from "@/lib/useAuth";
import { api, Customer, Order } from "@/lib/api";

export default function CustomerDetailPage() {
  useAuth();
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [customer, setCustomer] = useState<(Customer & { orders: Order[] }) | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .customer(id)
      .then(setCustomer)
      .catch((e) => setError(e.message));
  }, [id]);

  if (error) return <Shell><p className="text-sm text-red-600">{error}</p></Shell>;
  if (!customer) return <Shell><div className="text-sm text-slate-500">Loading...</div></Shell>;

  return (
    <Shell>
      <div className="mx-auto max-w-3xl space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">{customer.name || "Customer"}</h2>
          <p className="text-sm text-slate-500" dir="ltr">{customer.phone || "—"}</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-slate-700">Details</h3>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <div className="text-slate-500">Wilaya</div><div>{customer.wilaya || "—"}</div>
            <div className="text-slate-500">Commune</div><div>{customer.commune || "—"}</div>
            <div className="text-slate-500">Platform</div><div>{customer.platform || "—"}</div>
            <div className="text-slate-500">Orders</div><div>{customer.orders.length}</div>
            <div className="text-slate-500">Customer since</div><div>{formatDate(customer.created_at)}</div>
          </dl>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-slate-700">Order history</h3>
          <ul className="mt-3 divide-y divide-slate-100">
            {customer.orders.map((o) => (
              <li key={o.id} className="flex items-center justify-between py-2 text-sm">
                <div>
                  <span className="font-medium text-brand-700">{o.order_id || `#${o.id}`}</span>
                  <span className="ml-2 text-slate-500">{o.product}</span>
                  <span className="ml-2 text-xs text-slate-400">×{o.quantity ?? 1}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">{formatDate(o.created_at)}</span>
                  <Badge color={statusColor(o.status)}>{o.status}</Badge>
                </div>
              </li>
            ))}
            {customer.orders.length === 0 && <li className="py-4 text-sm text-slate-400">No orders yet.</li>}
          </ul>
        </div>
      </div>
    </Shell>
  );
}