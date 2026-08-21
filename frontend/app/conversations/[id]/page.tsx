"use client";

import { useEffect, useState } from "react";
import { api, ConversationDetail, Message } from "@/lib/api";
import { useParams } from "next/navigation";

export default function ConversationDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [conv, setConv] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.conversation(id).then(setConv).catch(console.error).finally(() => setLoading(false));
  }, [id]);

  const handleSend = async () => {
    if (!replyText.trim() || !id) return;
    setSending(true);
    try {
      await api.addMessage(id, replyText, "outbound");
      setReplyText("");
      const updated = await api.conversation(id);
      setConv(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setSending(false);
    }
  };

  if (loading) return <p className="text-slate-500">Loading...</p>;
  if (!conv) return <p className="text-red-500">Conversation not found.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Conversation #{conv.id}</h1>
          <p className="text-sm text-slate-500">
            {conv.platform} · {conv.customer_name || "Unknown"} · {conv.status}
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="space-y-4 max-h-96 overflow-y-auto">
          {(conv.messages || []).map((m: Message) => (
            <div key={m.id} className={`flex ${m.direction === "outbound" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[70%] rounded-lg px-4 py-2 ${
                m.direction === "outbound"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-100 text-slate-800"
              }`}>
                <p className="text-sm">{m.content}</p>
                <p className={`text-xs mt-1 ${m.direction === "outbound" ? "text-blue-200" : "text-slate-400"}`}>
                  {new Date(m.created_at).toLocaleString()}
                </p>
              </div>
            </div>
          ))}
          {(!conv.messages || conv.messages.length === 0) && (
            <p className="text-center text-slate-400 text-sm py-8">No messages yet.</p>
          )}
        </div>
      </div>

      <div className="flex gap-3">
        <input
          type="text"
          placeholder="Type a reply..."
          value={replyText}
          onChange={(e) => setReplyText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm"
          disabled={sending}
        />
        <button
          onClick={handleSend}
          disabled={sending || !replyText.trim()}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {sending ? "Sending..." : "Send"}
        </button>
      </div>
    </div>
  );
}
