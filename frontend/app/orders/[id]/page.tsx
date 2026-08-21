"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Shell from "@/components/shell";
import { Badge, formatPrice, statusColor } from "@/components/ui";
import { useAuth } from "@/lib/useAuth";
import { api, OrderDetail } from "@/lib/api";

export default function OrderDetailPage() {
  useAuth();
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmMsg, setConfirmMsg] = useState<string | null>(null);

  const load = async () => {
    try {
      setOrder(await api.order(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load order");
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const confirm = async () => {
    setConfirming(true);
    setError(null);
    setConfirmMsg(null);
    try {
      const res = await api.confirmOrder(id);
      setConfirmMsg(res.message || "Order confirmed successfully");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Confirmation failed");
    } finally {
      setConfirming(false);
    }
  };

  if (!order && !error) return <Shell><div className="text-sm text-slate-500">Loading...</div></Shell>;
  if (error) return <Shell><p className="text-sm text-red-600">{error}</p></Shell>;
  if (!order) return null;

  const canConfirm = order.status === "new";

  return (
    <Shell>
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-800">
              Order {order.order_id || `#${order.id}`}
            </h2>
            <p className="text-sm text-slate-500">
              Created {new Date(order.created_at).toLocaleString("fr-DZ")}
            </p>
          </div>
          <Badge color={statusColor(order.status)}>{order.status}</Badge>
        </div>

        {confirmMsg && (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {confirmMsg}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold text-slate-700">Customer</h3>
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">Name</dt><dd>{order.name || "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Phone</dt><dd dir="ltr">{order.phone || "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Wilaya</dt><dd>{order.wilaya || "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Commune</dt><dd>{order.commune || "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Channel</dt><dd>{order.source_channel || "—"}</dd></div>
            </dl>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold text-slate-700">Product</h3>
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">Product</dt><dd>{order.product || "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Color</dt><dd>{order.color || "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Size</dt><dd>{order.size || "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Quantity</dt><dd>{order.quantity ?? 1}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Unit price</dt><dd>{formatPrice(order.price)}</dd></div>
              <div className="flex justify-between border-t border-slate-100 pt-2 font-medium">
                <dt>Total</dt><dd>{formatPrice((order.price ?? 0) * (order.quantity ?? 1))}</dd>
              </div>
              <div className="flex justify-between"><dt className="text-slate-500">Delivery</dt><dd>{order.delivery_method || "—"}</dd></div>
            </dl>
          </div>
        </div>

        {canConfirm && (
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold text-slate-700">Confirm order</h3>
            <p className="mt-1 text-sm text-slate-500">
              Confirming will set the status to <b>confirmed</b> and automatically deduct{" "}
              {order.quantity ?? 1} unit(s) from inventory in Google Sheets.
            </p>
            <button
              onClick={confirm}
              disabled={confirming}
              className="mt-3 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {confirming ? "Confirming..." : "Confirm Order"}
            </button>
          </div>
        )}
      </div>
    </Shell>
  );
}