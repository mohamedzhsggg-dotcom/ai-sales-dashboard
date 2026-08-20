const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_PREFIX = "/api/v1";

export interface User {
  id: number;
  email: string;
  full_name?: string | null;
  role: string;
  tenant_id: number;
}

export interface Order {
  id: number;
  order_id?: string | null;
  phone?: string | null;
  name?: string | null;
  wilaya?: string | null;
  commune?: string | null;
  product?: string | null;
  color?: string | null;
  size?: string | null;
  quantity?: number | null;
  price?: number | null;
  delivery_method?: string | null;
  status: string;
  source_channel?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrderDetail extends Order {
  customer_id?: number | null;
  sheet_row?: number | null;
  status_history?: { from?: string; to: string; at: string }[];
}

export interface Customer {
  id: number;
  phone?: string | null;
  name?: string | null;
  wilaya?: string | null;
  commune?: string | null;
  platform?: string | null;
  created_at: string;
  order_count?: number;
}

export interface Product {
  id: number;
  name: string;
  price?: number | null;
  sizes: unknown[];
  colors: unknown[];
  image_url?: string | null;
  stock: number;
  fb_post_id?: string | null;
  ig_post_id?: string | null;
  updated_at: string;
}

export interface DashboardStats {
  new_orders: number;
  confirmed_orders: number;
  total_revenue: number;
  low_stock_count: number;
  by_wilaya: { wilaya: string; count: number }[];
  recent_orders: Order[];
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

const TOKEN_KEY = "access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearTokens();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/auth/me"),
  orders: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<Page<Order>>(`/orders?${qs.toString()}`);
  },
  order: (id: number) => request<OrderDetail>(`/orders/${id}`),
  confirmOrder: (id: number) =>
    request<{ order: Order; stock_after: number; message: string }>(`/orders/${id}/confirm`, {
      method: "POST",
    }),
  updateStatus: (id: number, status: string) =>
    request<Order>(`/orders/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  customers: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<Page<Customer>>(`/customers?${qs.toString()}`);
  },
  customer: (id: number) =>
    request<Customer & { orders: Order[] }>(`/customers/${id}`),
  products: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<Page<Product>>(`/products?${qs.toString()}`);
  },
  inventory: (params: Record<string, string | number | boolean | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<Product[]>(`/inventory?${qs.toString()}`);
  },
  inventorySummary: () => request<{ total_products: number; total_stock: number; low_stock_count: number; out_of_stock_count: number }>(`/inventory/summary`),
  stats: () => request<DashboardStats>("/dashboard/stats"),
  updateStock: (id: number, stock: number) =>
    request<Product>(`/inventory/${id}/stock`, { method: "PATCH", body: JSON.stringify({ stock }) }),
};