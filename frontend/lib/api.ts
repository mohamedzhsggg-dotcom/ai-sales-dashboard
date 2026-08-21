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
  subtotal?: number;
  total?: number;
  items_count?: number;
  courier_name?: string | null;
  tracking_number?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrderDetail extends Order {
  customer_id?: number | null;
  items?: OrderItem[];
  cancel_reason?: string | null;
  cancel_note?: string | null;
}

export interface OrderItem {
  id: number;
  product_id?: number | null;
  product_name?: string | null;
  variant_id?: number | null;
  variant_options?: Record<string, unknown>;
  sku?: string | null;
  quantity: number;
  unit_price: number;
  subtotal: number;
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
  total_spent?: number;
  last_order_at?: string | null;
}

export interface Product {
  id: number;
  name: string;
  type?: string;
  sku?: string | null;
  description?: string | null;
  status?: string;
  category_id?: number | null;
  price?: number | null;
  sizes: unknown[];
  colors: unknown[];
  image_url?: string | null;
  stock: number;
  low_stock_threshold?: number;
  is_dashboard_managed?: boolean;
  fb_post_id?: string | null;
  ig_post_id?: string | null;
  updated_at: string;
}

export interface Shipment {
  id: number;
  tenant_id: number;
  order_id: number;
  courier_name: string;
  tracking_number?: string | null;
  status: string;
  cod_amount: number;
  shipping_fee: number;
  delivery_method?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  shipped_at?: string | null;
  delivered_at?: string | null;
}

export interface ShipmentDetail extends Shipment {
  tracking_events?: TrackingEvent[];
}

export interface TrackingEvent {
  id: number;
  status: string;
  description?: string | null;
  location?: string | null;
  courier_raw_status?: string | null;
  recorded_at: string;
}

export interface Category {
  id: number;
  tenant_id: number;
  parent_id?: number | null;
  name: string;
  slug: string;
  sort_order: number;
  is_active: boolean;
  product_count?: number;
  created_at: string;
}

export interface Conversation {
  id: number;
  tenant_id: number;
  customer_id?: number | null;
  platform: string;
  external_conversation_id?: string | null;
  external_user_id?: string | null;
  subject?: string | null;
  status: string;
  last_message_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages?: Message[];
  customer_name?: string | null;
  customer_phone?: string | null;
}

export interface Message {
  id: number;
  tenant_id: number;
  conversation_id: number;
  direction: string;
  content: string;
  platform_message_id?: string | null;
  external_user_id?: string | null;
  extra_data?: Record<string, unknown> | null;
  created_at: string;
}

export interface SocialComment {
  id: number;
  tenant_id: number;
  platform: string;
  post_id: string;
  comment_id: string;
  external_user_id?: string | null;
  external_username?: string | null;
  comment_text?: string | null;
  product_id?: number | null;
  product_name?: string | null;
  resolved: boolean;
  replied: boolean;
  reply_text?: string | null;
  created_at: string;
  processed_at?: string | null;
}

export interface PostMapping {
  id: number;
  tenant_id: number;
  platform: string;
  post_id: string;
  product_id?: number | null;
  product_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Return {
  id: number;
  tenant_id: number;
  order_id: number;
  status: string;
  reason?: string | null;
  note?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DashboardStats {
  new_orders: number;
  confirmed_orders: number;
  shipped_orders: number;
  delivered_orders: number;
  cancelled_orders: number;
  returned_orders: number;
  total_revenue: number;
  total_products: number;
  low_stock_count: number;
  by_wilaya: { wilaya: string; count: number }[];
  recent_orders: Order[];
  recent_activity: { id: number; action: string; entity_type?: string; entity_id?: string; created_at?: string }[];
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
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/auth/me"),
  orders: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<Page<Order>>(`/orders?${qs.toString()}`);
  },
  order: (id: number) => request<OrderDetail>(`/orders/${id}`),
  confirmOrder: (id: number) =>
    request<{ order: Order; message: string }>(`/orders/${id}/confirm`, {
      method: "POST",
    }),
  updateStatus: (id: number, status: string, note?: string) =>
    request<Order>(`/orders/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, note }),
    }),
  cancelOrder: (id: number, note: string) =>
    request<Order>(`/orders/${id}/cancel`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
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
  inventorySummary: () =>
    request<{ total_products: number; total_stock: number; low_stock_count: number; out_of_stock_count: number }>(
      `/inventory/summary`
    ),
  stats: () => request<DashboardStats>("/dashboard/stats"),
  updateStock: (id: number, quantity: number, reason: string = "manual") =>
    request<Product>(`/inventory/${id}/stock`, {
      method: "PATCH",
      body: JSON.stringify({ quantity, reason }),
    }),

  // Shipments
  shipments: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<Page<Shipment>>(`/shipments?${qs.toString()}`);
  },
  shipment: (id: number) => request<ShipmentDetail>(`/shipments/${id}`),
  createShipment: (orderId: number, courierName: string = "yalidine") =>
    request<ShipmentDetail>(`/shipments`, {
      method: "POST",
      body: JSON.stringify({ order_id: orderId, courier_name: courierName }),
    }),
  refreshShipment: (id: number) =>
    request<ShipmentDetail>(`/shipments/${id}/refresh`, { method: "POST" }),
  cancelShipment: (id: number) =>
    request<void>(`/shipments/${id}`, { method: "DELETE" }),

  // Categories
  categories: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<Page<Category>>(`/categories?${qs.toString()}`);
  },
  categoryTree: () => request<Category[]>("/categories/tree"),

  // Conversations
  conversations: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<Page<Conversation>>(`/conversations?${qs.toString()}`);
  },
  conversation: (id: number) => request<ConversationDetail>(`/conversations/${id}`),
  createConversation: (data: { platform: string; subject?: string; customer_id?: number }) =>
    request<ConversationDetail>("/conversations", { method: "POST", body: JSON.stringify(data) }),
  addMessage: (conversationId: number, content: string, direction: string = "outbound") =>
    request<Message>(`/conversations/${conversationId}/messages`, {
      method: "POST", body: JSON.stringify({ content, direction }),
    }),

  // Social Comments
  comments: (params: Record<string, string | number | boolean | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<Page<SocialComment>>(`/comments?${qs.toString()}`);
  },
  replyToComment: (commentId: number, replyText: string) =>
    request<SocialComment>(`/comments/${commentId}/reply`, {
      method: "PATCH", body: JSON.stringify({ reply_text: replyText }),
    }),

  // Post Mappings
  postMappings: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<Page<PostMapping>>(`/post-mappings?${qs.toString()}`);
  },
  resolvePost: (platform: string, postId: string) =>
    request<{ resolved: boolean; product_id?: number; product_name?: string }>(
      `/resolve-post?platform=${platform}&post_id=${postId}`
    ),
};
