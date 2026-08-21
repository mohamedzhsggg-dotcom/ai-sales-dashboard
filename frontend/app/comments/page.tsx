"use client";

import { useEffect, useState } from "react";
import { api, SocialComment, Page } from "@/lib/api";

export default function CommentsPage() {
  const [data, setData] = useState<Page<SocialComment> | null>(null);
  const [platform, setPlatform] = useState<string>("");
  const [resolved, setResolved] = useState<string>("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.comments({
      platform: platform || undefined,
      resolved: resolved !== "" ? resolved === "true" : undefined,
      page,
      limit: 20,
    })
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [platform, resolved, page]);

  const platformBadge = (p: string) =>
    p === "facebook" ? "bg-blue-100 text-blue-700" : "bg-pink-100 text-pink-700";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Social Comments</h1>

      <div className="flex gap-3">
        <select
          value={platform}
          onChange={(e) => { setPlatform(e.target.value); setPage(1); }}
          className="rounded border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All Platforms</option>
          <option value="facebook">Facebook</option>
          <option value="instagram">Instagram</option>
        </select>
        <select
          value={resolved}
          onChange={(e) => { setResolved(e.target.value); setPage(1); }}
          className="rounded border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All</option>
          <option value="false">Unresolved</option>
          <option value="true">Resolved</option>
        </select>
      </div>

      {loading ? (
        <p className="text-slate-500">Loading...</p>
      ) : !data || data.items.length === 0 ? (
        <p className="text-slate-500">No comments found.</p>
      ) : (
        <div className="space-y-3">
          {data.items.map((c) => (
            <div key={c.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${platformBadge(c.platform)}`}>
                      {c.platform}
                    </span>
                    <span className="text-xs text-slate-400">Post: {c.post_id}</span>
                    {c.product_name && (
                      <span className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
                        {c.product_name}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-slate-700">{c.comment_text}</p>
                  <p className="text-xs text-slate-400">
                    by @{c.external_username || c.external_user_id || "unknown"} · {new Date(c.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {c.resolved ? (
                    <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700">Resolved</span>
                  ) : (
                    <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs text-yellow-700">Pending</span>
                  )}
                  {c.replied && (
                    <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">Replied</span>
                  )}
                </div>
              </div>
              {c.reply_text && (
                <div className="mt-3 rounded bg-blue-50 p-3">
                  <p className="text-xs font-medium text-blue-600 mb-1">Reply:</p>
                  <p className="text-sm text-blue-800">{c.reply_text}</p>
                </div>
              )}
            </div>
          ))}
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
  );
}
