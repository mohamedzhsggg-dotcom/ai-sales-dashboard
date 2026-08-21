"use client";

import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { api, Conversation, Page } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

export default function ConversationsPage() {
  useAuth();
  const [data, setData] = useState<Page<Conversation> | null>(null);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.conversations({ status: status || undefined, search: search || undefined, page, limit: 20 })
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [status, search, page]);

  const platformBadge = (p: string) =>
    p === "facebook" ? "bg-blue-100 text-blue-700" : "bg-pink-100 text-pink-700";

  const statusBadge = (s: string) =>
    s === "open" ? "bg-green-100 text-green-700"
    : s === "closed" ? "bg-slate-100 text-slate-600"
    : "bg-yellow-100 text-yellow-700";

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-slate-800">Conversations</h1>
        </div>

        <div className="flex gap-3">
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            className="rounded border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">All Status</option>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
            <option value="archived">Archived</option>
          </select>
          <input
            type="text"
            placeholder="Search subject..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        {loading ? (
          <p className="text-slate-500">Loading...</p>
        ) : !data || data.items.length === 0 ? (
          <p className="text-slate-500">No conversations found.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-4 py-3 font-medium text-slate-600">ID</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Platform</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Subject</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Status</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Last Message</th>
                  <th className="px-4 py-3 font-medium text-slate-600">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <a href={`/conversations/${c.id}`} className="text-blue-600 hover:underline">
                        #{c.id}
                      </a>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${platformBadge(c.platform)}`}>
                        {c.platform}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{c.subject || "-"}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge(c.status)}`}>
                        {c.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {c.last_message_at ? new Date(c.last_message_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{new Date(c.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && data.total > data.limit && (
          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>Showing {data.items.length} of {data.total}</span>
            <div className="flex gap-2">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded border px-3 py-1 disabled:opacity-50">Prev</button>
              <button disabled={page * data.limit >= data.total} onClick={() => setPage(page + 1)} className="rounded border px-3 py-1 disabled:opacity-50">Next</button>
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}
