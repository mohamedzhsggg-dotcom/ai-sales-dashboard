"use client";

import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Badge, SearchInput, formatPrice } from "@/components/ui";
import { useAuth } from "@/lib/useAuth";
import { api, Product } from "@/lib/api";

export default function ProductsPage() {
  useAuth();
  const [items, setItems] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .products({ page, search, limit: 24 })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((e) => setError(e.message));
  }, [page, search]);

  return (
    <Shell>
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-slate-800">Products</h2>
        <div className="max-w-sm">
          <SearchInput value={search} onChange={setSearch} placeholder="Search products..." />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((p) => (
            <div key={p.id} className="rounded-xl border border-slate-200 bg-white p-4">
              {p.image_url && (
                <img
                  src={p.image_url}
                  alt={p.name}
                  className="mb-3 h-40 w-full rounded-lg object-cover"
                />
              )}
              <h3 className="font-semibold text-slate-800">{p.name}</h3>
              <p className="mt-1 text-sm text-slate-500">{formatPrice(p.price)}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {p.sizes.slice(0, 5).map((s) => (
                  <span key={String(s)} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                    {String(s)}
                  </span>
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between">
                <Badge color={p.stock === 0 ? "red" : p.stock <= 5 ? "amber" : "green"}>
                  {p.stock} in stock
                </Badge>
                {p.fb_post_id && <span className="text-xs text-slate-400">FB: {p.fb_post_id}</span>}
                {p.ig_post_id && <span className="text-xs text-slate-400">IG: {p.ig_post_id}</span>}
              </div>
            </div>
          ))}
        </div>
        {items.length === 0 && <div className="py-10 text-center text-sm text-slate-400">No products found.</div>}
      </div>
    </Shell>
  );
}