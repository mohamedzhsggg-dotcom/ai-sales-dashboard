"use client";

import { useEffect, useState } from "react";
import Shell from "@/components/shell";
import { api, User } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

export default function SettingsPage() {
  useAuth();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.me().then(setUser).catch(console.error).finally(() => setLoading(false));
  }, []);

  return (
    <Shell>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-slate-800">Settings</h1>

        {loading ? (
          <p className="text-slate-500">Loading...</p>
        ) : !user ? (
          <p className="text-red-500">Could not load user info.</p>
        ) : (
          <>
            <div className="rounded-lg border border-slate-200 bg-white p-6 space-y-4">
              <h2 className="text-lg font-semibold text-slate-700">Account</h2>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-slate-500">Email</span>
                  <p className="font-medium text-slate-800">{user.email}</p>
                </div>
                <div>
                  <span className="text-slate-500">Full Name</span>
                  <p className="font-medium text-slate-800">{user.full_name || "-"}</p>
                </div>
                <div>
                  <span className="text-slate-500">Role</span>
                  <p className="font-medium text-slate-800 capitalize">{user.role}</p>
                </div>
                <div>
                  <span className="text-slate-500">Tenant ID</span>
                  <p className="font-medium text-slate-800">{user.tenant_id}</p>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-6 space-y-4">
              <h2 className="text-lg font-semibold text-slate-700">System</h2>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-slate-500">Database</span>
                  <p className="font-medium text-slate-800">PostgreSQL (Authoritative)</p>
                </div>
                <div>
                  <span className="text-slate-500">Compatibility Mode</span>
                  <p className="font-medium text-slate-800">Google Sheets (Legacy)</p>
                </div>
                <div>
                  <span className="text-slate-500">Platform</span>
                  <p className="font-medium text-slate-800">RAQI KE SaaS</p>
                </div>
                <div>
                  <span className="text-slate-500">Version</span>
                  <p className="font-medium text-slate-800">Phase 2.0</p>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}