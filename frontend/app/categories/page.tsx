"use client";

import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { Badge } from "@/components/ui";
import { api, type Category } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

interface CategoryNode extends Category {
  children?: CategoryNode[];
}

function buildTree(categories: Category[]): CategoryNode[] {
  const map = new Map<number, CategoryNode>();
  const roots: CategoryNode[] = [];
  for (const c of categories) {
    map.set(c.id, { ...c, children: [] });
  }
  for (const c of categories) {
    const node = map.get(c.id)!;
    if (c.parent_id && map.has(c.parent_id)) {
      map.get(c.parent_id)!.children!.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

function CategoryRow({ node, depth }: { node: CategoryNode; depth: number }) {
  return (
    <>
      <tr className="hover:bg-slate-50">
        <td className="px-4 py-3" style={{ paddingLeft: String(16 + depth * 24) + "px" }}>
          {"  ".repeat(depth)}
          {node.name}
        </td>
        <td className="px-4 py-3 font-mono text-xs">{node.slug}</td>
        <td className="px-4 py-3">
          <Badge color={node.is_active ? "green" : "slate"}>
            {node.is_active ? "Active" : "Inactive"}
          </Badge>
        </td>
        <td className="px-4 py-3 text-center">{node.product_count ?? 0}</td>
      </tr>
      {node.children?.map((child) => (
        <CategoryRow key={child.id} node={child} depth={depth + 1} />
      ))}
    </>
  );
}

export default function CategoriesPage() {
  useAuth();
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.categories({ limit: 200 })
      .then((data) => setCategories(data.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const tree = buildTree(categories);

  return (
    <Shell>
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Categories</h2>
        {loading ? (
          <p className="text-sm text-slate-500">Loading...</p>
        ) : categories.length === 0 ? (
          <p className="text-sm text-slate-500">No categories found.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Slug</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Products</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tree.map((node) => (
                  <CategoryRow key={node.id} node={node} depth={0} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Shell>
  );
}
