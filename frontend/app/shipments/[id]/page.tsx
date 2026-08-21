"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Shell from "@/components/shell";
import { Badge, formatDate, formatPrice, statusColor } from "@/components/ui";
import { api, type ShipmentDetail } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

export default function ShipmentDetailPage() {
  useAuth();
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const [shipment, setShipment] = useState<ShipmentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = () => {
    setLoading(true);
    api.shipment(id).then(setShipment).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { if (id) load(); }, [id]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const updated = await api.refreshShipment(id);
      setShipment(updated);
    } catch {}
    setRefreshing(false);
  };

  const handleCancel = async () => {
    if (!confirm("Cancel this shipment?")) return;
    try {
      await api.cancelShipment(id);
      load();
    } catch {}
  };

  if (loading) return <Shell><p className="text-sm text-slate-500">Loading...</p></Shell>;
  if (!shipment) return <Shell><p className="text-sm text-red-500">Shipment not found.</p></Shell>;

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Shipment #{shipment.id}</h2>
            <p className="text-sm text-slate-500">
              Order #{shipment.order_id} · {shipment.courier_name}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {refreshing ? "Refreshing..." : "Refresh Tracking"}
            </button>
            {shipment.status !== "delivered" && shipment.status !== "cancelled" && (
              <button
                onClick={handleCancel}
                className="rounded-md border border-red-300 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
              >
                Cancel
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase text-slate-500">Status</p>
            <Badge color={statusColor(shipment.status)}>{shipment.status}</Badge>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase text-slate-500">Tracking Number</p>
            <p className="font-mono text-sm">{shipment.tracking_number || "—"}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase text-slate-500">COD Amount</p>
            <p className="text-sm font-medium">{formatPrice(shipment.cod_amount)}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase text-slate-500">Delivery Method</p>
            <p className="text-sm capitalize">{shipment.delivery_method || "—"}</p>
          </div>
        </div>

        {shipment.tracking_events && shipment.tracking_events.length > 0 && (
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold">Tracking History</h3>
            <div className="space-y-3">
              {shipment.tracking_events.map((ev) => (
                <div key={ev.id} className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-blue-500" />
                  <div>
                    <p className="text-sm font-medium">{ev.status}</p>
                    {ev.description && <p className="text-xs text-slate-500">{ev.description}</p>}
                    <p className="text-xs text-slate-400">{formatDate(ev.recorded_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-500">
          <p>Created: {formatDate(shipment.created_at)}</p>
          {shipment.shipped_at && <p>Shipped: {formatDate(shipment.shipped_at)}</p>}
          {shipment.delivered_at && <p>Delivered: {formatDate(shipment.delivered_at)}</p>}
        </div>
      </div>
    </Shell>
  );
}
