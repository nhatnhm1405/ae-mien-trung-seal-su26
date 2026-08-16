// Client REST + kiểu dữ liệu backend trả về.
//
// Backend là app FastAPI ở back-end/ (xem back-end/README.md). Nó bật CORS `*`
// nên gọi thẳng được, không cần proxy trong vite.config.ts (file đó do Figma Make
// quản lý, sửa vào dễ bị ghi đè).
//
// Đổi địa chỉ backend khi demo máy khác: tạo front-end/.env.local với
//   VITE_API_BASE=http://192.168.1.20:8000

export const API_BASE: string = import.meta.env?.VITE_API_BASE ?? 'http://localhost:8000'
export const WS_URL: string = `${API_BASE.replace(/^http/, 'ws')}/ws/telemetry`

// ---- Kiểu dữ liệu backend ------------------------------------------------

export type Reading = Record<string, number> & { ts?: number }

export type RollingStat = {
  current: number
  mean: number | null
  std: number | null
  slope_per_hour: number | null
}

export type DeviceSnapshot = {
  device_code: string
  name: string
  units: Record<string, string>
  latest: Reading | null
  is_stale: boolean
  last_seen_ts: number | null
  last_seen_iso: string | null
  rolling: Record<string, RollingStat>
}

export type FarmSnapshot = Record<string, DeviceSnapshot>

export type AnomalyPayload = {
  device_code: string
  name: string
  reading: Reading
  rolling: Record<string, RollingStat>
  is_anomaly: boolean
  anomaly_score: number | null
  confidence: string
  metrics_used?: string[]
}

export type TelemetryPayload = {
  device_code: string
  name: string
  units: Record<string, string>
  metrics: Reading
  latest: Reading | null
  is_stale: boolean
  source?: string
  scenario?: string | null
}

export type TraceCall = { tool: string; args?: unknown; result?: Record<string, unknown> }

export type AgentInsight = {
  trigger: string
  device_code: string
  device_name?: string
  anomaly?: AnomalyPayload
  answer: string | null
  trace: TraceCall[]
  latency_ms?: number
  error?: string
}

export type Plan = {
  plan_id: string
  zone: string
  scheduled_time: string
  priority: string
  duration_minutes: number
  rationale: string
  used_devices: string[]
  data_snapshot: Record<string, Reading | null>
  status: 'pending_approval' | 'confirmed' | 'rejected'
  created_at: string
  guardrail_check: { allowed: boolean; reason: string }
  approved_by?: string
  rejected_by?: string
  rejection_reason?: string
}

export type Task = {
  task_id: string
  title: string
  zone: string
  reason: string
  severity: string
  assigned_to: string
  used_devices: string[]
  stale_flags: Record<string, boolean>
  status: 'open' | 'completed' | 'verified'
  created_at: string
  resolution_note?: string
  verification_proof?: { verification_status: string; confidence_score: number }
}

export type FarmStatus = {
  readable_devices: string[]
  stale_devices: string[]
  total_devices: number
  track_b_readable: string
  meets_minimum: boolean
  scenario: string
}

export type HistoryResponse = { device_code: string; count: number; records: Reading[] }

// Envelope thống nhất của WebSocket — mọi message đều đúng dạng này.
export type Envelope =
  | { type: 'snapshot'; ts: number; payload: FarmSnapshot }
  | { type: 'telemetry'; ts: number; payload: TelemetryPayload }
  | { type: 'anomaly'; ts: number; payload: AnomalyPayload }
  | { type: 'agent_insight'; ts: number; payload: AgentInsight }
  | { type: 'plan'; ts: number; payload: Plan }
  | { type: 'task'; ts: number; payload: Task }
  | { type: 'notification'; ts: number; payload: Record<string, unknown> }
  | { type: 'guardrail_veto'; ts: number; payload: { action: string; reason: string } }

// ---- Gọi REST ------------------------------------------------------------

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`${res.status} ${path}: ${detail.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  status: () => request<FarmStatus>('/api/status'),
  devices: () => request<FarmSnapshot>('/api/devices'),
  history: (code: string, limit = 60) =>
    request<HistoryResponse>(`/api/devices/${code}/history?limit=${limit}`),

  plans: () => request<{ total: number; plans: Plan[] }>('/api/irrigation/plans'),
  approvePlan: (id: string, by = 'Người quản lý nông trại') =>
    request<{ plan: Plan; task: Task }>(
      `/api/irrigation/plans/${id}/approve?approved_by=${encodeURIComponent(by)}`,
      { method: 'POST' },
    ),
  rejectPlan: (id: string, reason: string, by = 'Người quản lý nông trại') =>
    request<Plan>(
      `/api/irrigation/plans/${id}/reject?rejected_by=${encodeURIComponent(by)}&reason=${encodeURIComponent(reason)}`,
      { method: 'POST' },
    ),

  tasks: () => request<{ total: number; tasks: Task[] }>('/api/tasks'),
  verifyTask: (id: string) =>
    request<{ task: Task }>(`/api/tasks/${id}/verify`, { method: 'POST' }),

  lastInsight: () =>
    request<{ available: boolean; insight: AgentInsight | null }>('/api/agent/last-insight'),

  // Nút demo cho lúc pitch — giá trị bơm vào đi qua đúng đường ống như dữ liệu thật.
  inject: (device_code: string, metrics: Record<string, number>) =>
    request<{ injected: boolean; record: Reading }>('/api/simulate/inject', {
      method: 'POST',
      body: JSON.stringify({ device_code, metrics }),
    }),
  freeze: (code: string) => request<unknown>(`/api/simulate/freeze/${code}`, { method: 'POST' }),
  unfreeze: (code: string) => request<unknown>(`/api/simulate/unfreeze/${code}`, { method: 'POST' }),
}
