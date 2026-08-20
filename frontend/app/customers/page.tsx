"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Shell from "@/components/shell";
import { Pagination, SearchInput } from "@/components/ui";
import { useAuth } from "@/lib/useAuth";
import { api, Customer } from "@/lib/api";

export default function CustomersPage() {
  useAuth();
  const [items, setItems] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [wilaya, setWilaya] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .customers({ page, search, wilaya, limit: 20 })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((e) => setError(e.message));
  }, [page, search, wilaya]);

  return (
    <Shell>
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-slate-800">Customers</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <SearchInput value={search} onChange={setSearch} placeholder="Search name or phone..." />
          <input
            value={wilaya}
            onChange={(e) => setWilaya(e.target.value)}
            placeholder="Wilaya"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Phone</th>
                <th className="px-4 py-3">Wilaya</th>
                <th className="px-4 py-3">Commune</th>
                <th className="px-4 py-3">Platform</th>
                <th className="px-4 py-3">Orders</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{c.name || "—"}</td>
                  <td className="px-4 py-3" dir="ltr">{c.phone || "—"}</td>
                  <td className="px-4 py-3">{c.wilaya || "—"}</td>
                  <td className="px-4 py-3">{c.commune || "—"}</td>
                  <td className="px-4 py-3">{c.platform || "—"}</td>
                  <td className="px-4 py-3">{c.order_count ?? 0}</td>
                  <td className="px-4 py-3">
                    <Link href={`/customers/${c.id}`} className="font-medium text-brand-600 hover:text-brand-700">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && <div className="px-4 py-10 text-center text-sm text-slate-400">No customers found.</div>}
          <Pagination page={page} total={total} limit={20} onChange={setPage} />
        </div>
      </div>
    </Shell>
  );
}