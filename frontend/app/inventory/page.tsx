"use client";

import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Badge, formatPrice } from "@/components/ui";
import { useAuth } from "@/lib/useAuth";
import { api, Product } from "@/lib/api";

export default function InventoryPage() {
  useAuth();
  const [items, setItems] = useState<Product[]>([]);
  const [filter, setFilter] = useState<"all" | "low" | "out">("all");
  const [summary, setSummary] = useState({ total_products: 0, total_stock: 0, low_stock_count: 0, out_of_stock_count: 0 });
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const params = filter === "low" ? { low_stock: true } : filter === "out" ? { out_of_stock: true } : {};
      const [list, sum] = await Promise.all([api.inventory(params), api.inventorySummary()]);
      setItems(list);
      setSummary(sum);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load inventory");
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const cards = [
    { label: "Total products", value: summary.total_products, color: "bg-slate-50 text-slate-700" },
    { label: "Total stock units", value: summary.total_stock, color: "bg-blue-50 text-blue-700" },
    { label: "Low stock (≤5)", value: summary.low_stock_count, color: "bg-amber-50 text-amber-700" },
    { label: "Out of stock", value: summary.out_of_stock_count, color: "bg-red-50 text-red-700" },
  ];

  return (
    <Shell>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-800">Inventory</h2>
          <div className="flex gap-2">
            {(["all", "low", "out"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  filter === f ? "bg-brand-600 text-white" : "bg-white text-slate-600 border border-slate-300"
                }`}
              >
                {f === "all" ? "All" : f === "low" ? "Low stock" : "Out of stock"}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {cards.map((c) => (
            <div key={c.label} className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-sm text-slate-500">{c.label}</p>
              <p className={`mt-1 inline-block rounded-md px-2 py-1 text-2xl font-semibold ${c.color}`}>{c.value}</p>
            </div>
          ))}
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Price</th>
                <th className="px-4 py-3">Stock</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{p.name}</td>
                  <td className="px-4 py-3">{formatPrice(p.price)}</td>
                  <td className="px-4 py-3">{p.stock}</td>
                  <td className="px-4 py-3">
                    <Badge color={p.stock === 0 ? "red" : p.stock <= 5 ? "amber" : "green"}>
                      {p.stock === 0 ? "Out of stock" : p.stock <= 5 ? "Low stock" : "In stock"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && <div className="px-4 py-10 text-center text-sm text-slate-400">No products found.</div>}
        </div>
      </div>
    </Shell>
  );
}