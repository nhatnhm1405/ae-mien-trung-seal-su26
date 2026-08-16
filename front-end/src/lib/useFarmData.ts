// Nguồn dữ liệu sống cho dashboard: một WebSocket + vài lần gọi REST lúc mount.
//
// Nguyên tắc: KHÔNG bao giờ để màn hình trắng. Khi chưa kết nối được backend,
// hook trả `live: false` và App.tsx tự rơi về bộ dữ liệu mẫu — mất mạng giữa
// buổi demo thì dashboard vẫn có hình để nói, chỉ đổi nhãn trạng thái.

import { useCallback, useEffect, useRef, useState } from 'react'

import {
  api,
  WS_URL,
  type AgentInsight,
  type Envelope,
  type FarmSnapshot,
  type Plan,
  type Reading,
  type Task,
} from './api'
import { DEVICE_ORDER } from './adapt'

const HISTORY_LIMIT = 120 // số bản ghi giữ lại mỗi thiết bị (đủ cho chart 3 tiếng)
const RECONNECT_MAX_MS = 8000
const INSIGHT_LIMIT = 20 // số chẩn đoán giữ lại trên UI, khớp INSIGHT_LOG_MAXLEN mặc định của backend

export type FarmData = {
  live: boolean
  connected: boolean
  error: string | null
  snapshot: FarmSnapshot
  records: Record<string, Reading[]>
  tasks: Task[]
  plans: Plan[]
  /** Incident Log — mọi chẩn đoán gần đây, mới nhất trước. */
  insights: AgentInsight[]
  /** device_code -> thời điểm (ms) model bắn cảnh báo gần nhất */
  anomalyAt: Record<string, number>
  veto: { action: string; reason: string; at: number } | null
  lastUpdate: number | null
  scenario: string
}

const EMPTY: FarmData = {
  live: false,
  connected: false,
  error: null,
  snapshot: {},
  records: {},
  tasks: [],
  plans: [],
  insights: [],
  anomalyAt: {},
  veto: null,
  lastUpdate: null,
  scenario: 'NORMAL',
}

export function useFarmData() {
  const [data, setData] = useState<FarmData>(EMPTY)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef(0)
  const closedRef = useRef(false)

  // ---- Nạp dữ liệu ban đầu qua REST -------------------------------------
  const loadRest = useCallback(async () => {
    try {
      const [snapshot, tasksRes, plansRes, insightsRes, statusRes] = await Promise.all([
        api.devices(),
        api.tasks(),
        api.plans(),
        api.insights(INSIGHT_LIMIT),
        api.status(),
      ])

      // Lịch sử để vẽ sparkline + chart xu hướng ngay lần render đầu; các điểm
      // sau đó được nối thêm từ WebSocket chứ không poll lại REST.
      const histories = await Promise.all(
        DEVICE_ORDER.map((code) =>
          api
            .history(code, HISTORY_LIMIT)
            .then((r) => [code, r.records] as const)
            .catch(() => [code, [] as Reading[]] as const),
        ),
      )

      setData((prev) => ({
        ...prev,
        live: true,
        error: null,
        snapshot,
        records: Object.fromEntries(histories),
        tasks: tasksRes.tasks,
        plans: plansRes.plans,
        insights: insightsRes.insights,
        scenario: statusRes.scenario,
        lastUpdate: Date.now(),
      }))
    } catch (err) {
      setData((prev) => ({ ...prev, live: false, error: (err as Error).message }))
    }
  }, [])

  // ---- WebSocket --------------------------------------------------------
  useEffect(() => {
    closedRef.current = false
    let reconnectTimer: number | undefined

    function connect() {
      if (closedRef.current) return
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        retryRef.current = 0
        setData((prev) => ({ ...prev, connected: true, error: null }))
        void loadRest()
      }

      ws.onmessage = (event) => {
        let msg: Envelope
        try {
          msg = JSON.parse(event.data as string)
        } catch {
          return
        }
        setData((prev) => reduce(prev, msg))
      }

      ws.onerror = () => {
        // onclose chạy ngay sau, việc nối lại xử lý ở đó.
      }

      ws.onclose = () => {
        setData((prev) => ({ ...prev, connected: false }))
        if (closedRef.current) return
        retryRef.current += 1
        const delay = Math.min(500 * 2 ** retryRef.current, RECONNECT_MAX_MS)
        reconnectTimer = window.setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      closedRef.current = true
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      wsRef.current?.close()
    }
  }, [loadRest])

  // Nhịp 10s để nhãn "cập nhật N giây trước" tự trôi kể cả khi không có message.
  const [, setTick] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 10_000)
    return () => window.clearInterval(id)
  }, [])

  // ---- Hành động --------------------------------------------------------
  const actions = {
    approvePlan: async (planId: string) => {
      const res = await api.approvePlan(planId)
      setData((prev) => ({
        ...prev,
        plans: upsert(prev.plans, res.plan, 'plan_id'),
        tasks: upsert(prev.tasks, res.task, 'task_id'),
      }))
    },
    rejectPlan: async (planId: string, reason = 'Người quản lý từ chối') => {
      const plan = await api.rejectPlan(planId, reason)
      setData((prev) => ({ ...prev, plans: upsert(prev.plans, plan, 'plan_id') }))
    },
    verifyTask: async (taskId: string) => {
      const res = await api.verifyTask(taskId)
      setData((prev) => ({ ...prev, tasks: upsert(prev.tasks, res.task, 'task_id') }))
    },
    inject: (device: string, metrics: Record<string, number>) => api.inject(device, metrics),
    freeze: (code: string) => api.freeze(code),
    unfreeze: (code: string) => api.unfreeze(code),
    reload: loadRest,
  }

  return { data, actions }
}

// ---- Reducer cho từng loại message ---------------------------------------

function reduce(prev: FarmData, msg: Envelope): FarmData {
  switch (msg.type) {
    case 'snapshot':
      return { ...prev, live: true, snapshot: msg.payload, lastUpdate: Date.now() }

    case 'telemetry': {
      const p = msg.payload
      const existing = prev.snapshot[p.device_code]
      const record: Reading = { ...(p.latest ?? p.metrics), ts: msg.ts }
      const nextRecords = [...(prev.records[p.device_code] ?? []), record].slice(-HISTORY_LIMIT)

      return {
        ...prev,
        live: true,
        lastUpdate: Date.now(),
        scenario: p.scenario ?? prev.scenario,
        records: { ...prev.records, [p.device_code]: nextRecords },
        snapshot: {
          ...prev.snapshot,
          [p.device_code]: {
            ...existing,
            device_code: p.device_code,
            name: p.name,
            units: p.units,
            latest: p.latest ?? p.metrics,
            is_stale: p.is_stale,
            last_seen_ts: Date.now() / 1000,
            last_seen_iso: existing?.last_seen_iso ?? null,
            rolling: existing?.rolling ?? {},
          },
        },
      }
    }

    case 'anomaly':
      return {
        ...prev,
        anomalyAt: { ...prev.anomalyAt, [msg.payload.device_code]: Date.now() },
      }

    case 'agent_insight': {
      // Chèn vào ĐẦU Incident Log, mới nhất trước — không đè lên chẩn đoán cũ.
      // Trùng id (VD: reload trang giữa lúc WS đang gửi cùng lúc REST vừa nạp)
      // thì bỏ qua thay vì tạo bản sao.
      if (prev.insights.some((i) => i.id === msg.payload.id)) return prev
      return { ...prev, insights: [msg.payload, ...prev.insights].slice(0, INSIGHT_LIMIT) }
    }

    case 'plan':
      return { ...prev, plans: upsert(prev.plans, msg.payload, 'plan_id') }

    case 'task':
      return { ...prev, tasks: upsert(prev.tasks, msg.payload, 'task_id') }

    case 'guardrail_veto':
      return { ...prev, veto: { ...msg.payload, at: Date.now() } }

    default:
      return prev
  }
}

function upsert<T extends Record<string, unknown>>(list: T[], item: T, key: keyof T): T[] {
  const index = list.findIndex((x) => x[key] === item[key])
  if (index === -1) return [item, ...list]
  const next = [...list]
  next[index] = item
  return next
}
