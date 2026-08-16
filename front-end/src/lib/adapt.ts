// Chuyển dữ liệu backend sang đúng shape mà UI đang dùng.
//
// Backend trả số + đơn vị tách riêng (`metrics: {soil_moisture: 32.9}`,
// `units: {soil_moisture: '%'}`), còn card thiết bị nhận chuỗi đã format sẵn
// ('32.9%') kèm nhãn tiếng Việt. Toàn bộ việc dịch giữa hai bên nằm ở file này,
// để App.tsx không phải biết gì về schema backend và ngược lại.

import type { AnomalyPayload, DeviceSnapshot, FarmSnapshot, Plan, Reading, Task } from './api'
import type { SeriesPoint } from '../components/charts'

export type Status = 'ok' | 'warn' | 'danger' | 'offline'

export type MetricView = { label: string; value: string; history?: number[] }
export type DeviceView = {
  id: string
  name: string
  status: Status
  age: string
  metrics: MetricView[]
}

export type TaskView = {
  id: string
  name: string
  agent: string[]
  status: 'Chờ' | 'Đang xử lý' | 'Hoàn tất'
  time: string
}

export type VerificationView = { name: string; result: 'Thành công' | 'Thất bại' }

// Thứ tự hiển thị 6 thiết bị Track B. AC_01 (thiết bị demo của BTC) cố tình không
// hiện: nó không thuộc bài toán nông nghiệp và sẽ làm lệch lưới 6 cột.
export const DEVICE_ORDER = ['SOIL_01', 'WEATHER_01', 'PUMP_01', 'PH_01', 'TANK_01', 'SUN_01']

// Metric "chủ đạo" của mỗi thiết bị — số to nhất trên card và là đường sparkline.
const HERO_METRIC: Record<string, string> = {
  SOIL_01: 'soil_moisture',
  WEATHER_01: 'temperature',
  PUMP_01: 'flow_rate',
  PH_01: 'ph',
  TANK_01: 'level',
  SUN_01: 'lux',
}

const METRIC_LABEL: Record<string, string> = {
  soil_moisture: 'Độ ẩm đất',
  temperature: 'Nhiệt độ',
  humidity: 'Độ ẩm',
  flow_rate: 'Lưu lượng',
  power: 'Công suất',
  ph: 'Độ pH',
  level: 'Mực nước',
  lux: 'Cường độ sáng',
}

export function metricLabel(key: string): string {
  return METRIC_LABEL[key] ?? key
}

/** Cảnh báo còn được coi là "đang hoạt động" trong bao lâu (ms) sau khi model bắn. */
export const ANOMALY_TTL_MS = 120_000

// ---- Format số -----------------------------------------------------------

function formatNumber(key: string, value: number): string {
  // Lux lên tới ~90.000: rút gọn thành "53k". Dùng dấu phân cách nghìn kiểu Việt
  // ("52.951") sẽ đọc nhầm thành số thập phân khi đứng cạnh các metric 1 chữ số lẻ.
  if (key === 'lux') {
    return Math.abs(value) >= 10000
      ? `${Math.round(value / 1000)}k`
      : String(Math.round(value))
  }
  if (key === 'ph') return value.toFixed(1)
  if (Math.abs(value) >= 1000) return `${Math.round(value / 1000)}k`
  if (Math.abs(value) >= 100) return String(Math.round(value))
  return String(Math.round(value * 10) / 10)
}

function formatValue(key: string, value: number, unit: string | undefined): string {
  const num = formatNumber(key, value)
  if (!unit || unit === 'pH') return num
  // '%' và '°C' viết liền; 'L/min', 'W', 'lx' tách bằng khoảng trắng.
  return unit === '%' || unit === '°C' ? `${num}${unit}` : `${num} ${unit}`
}

export function formatAge(lastSeenTs: number | null): string {
  if (!lastSeenTs) return 'Chưa có dữ liệu'
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - lastSeenTs))
  if (seconds < 60) return `${seconds} giây`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} phút`
  return `${Math.round(minutes / 60)} giờ`
}

/**
 * Nhãn trục thời gian tương đối: '−40s', '−45p', '−2g15', 'Hiện tại'.
 *
 * Có nhánh giây vì lúc server vừa khởi động, cả buffer chỉ trải trong hơn một
 * phút — làm tròn thẳng sang phút thì mọi điểm đều thành '−1p' và trục nhìn như
 * bị hỏng.
 */
function relativeLabel(ts: number, now: number): string {
  const seconds = Math.max(0, Math.round(now - ts))
  if (seconds < 90) return `−${seconds}s`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `−${minutes}p`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest === 0 ? `−${hours} giờ` : `−${hours}g${String(rest).padStart(2, '0')}`
}

// ---- Thiết bị ------------------------------------------------------------

function deviceStatus(snap: DeviceSnapshot, anomalyAt: number | undefined): Status {
  if (snap.is_stale || !snap.latest) return 'offline'
  if (anomalyAt && Date.now() - anomalyAt < ANOMALY_TTL_MS) return 'danger'
  return 'ok'
}

export function toDeviceViews(
  snapshot: FarmSnapshot,
  history: Record<string, number[]>,
  anomalyAt: Record<string, number>,
): DeviceView[] {
  return DEVICE_ORDER.filter((code) => snapshot[code]).map((code) => {
    const snap = snapshot[code]
    const latest = snap.latest ?? {}
    const hero = HERO_METRIC[code]

    // Metric chủ đạo lên đầu, phần còn lại giữ nguyên thứ tự backend trả về.
    const keys = Object.keys(latest).filter((k) => k !== 'ts')
    keys.sort((a, b) => (a === hero ? -1 : b === hero ? 1 : 0))

    const metrics: MetricView[] = keys.map((key, index) => ({
      label: metricLabel(key),
      value: formatValue(key, latest[key] as number, snap.units[key]),
      history: index === 0 ? history[code] : undefined,
    }))

    return {
      id: code,
      name: snap.name,
      status: deviceStatus(snap, anomalyAt[code]),
      age: formatAge(snap.last_seen_ts),
      metrics,
    }
  })
}

/**
 * Lấy chuỗi giá trị của metric chủ đạo mỗi thiết bị, cho sparkline trên card.
 * Giữ tối đa `points` điểm cuối — sparkline chỉ để thấy hướng đi, không cần dày.
 */
export function heroHistories(
  records: Record<string, Reading[]>,
  points = 20,
): Record<string, number[]> {
  const out: Record<string, number[]> = {}
  for (const code of DEVICE_ORDER) {
    const key = HERO_METRIC[code]
    const values = (records[code] ?? [])
      .map((r) => r[key])
      .filter((v): v is number => typeof v === 'number')
      .slice(-points)
    if (values.length >= 2) out[code] = values
  }
  return out
}

/** Chuỗi lịch sử -> series cho TrendChart, hạ mẫu còn tối đa `maxPoints` điểm. */
export function toSeries(records: Reading[], metricKey: string, maxPoints = 13): SeriesPoint[] {
  const usable = records.filter((r) => typeof r[metricKey] === 'number' && r.ts)
  if (usable.length === 0) return []

  const step = Math.max(1, Math.ceil(usable.length / maxPoints))
  const sampled = usable.filter((_, i) => i % step === 0 || i === usable.length - 1)
  const now = Date.now() / 1000

  return sampled.map((r, i) => ({
    // Điểm cuối luôn là "Hiện tại" — dán nhãn theo mốc thời gian sẽ cho hai điểm
    // sát nhau cùng tên khi chúng cách nhau vài giây.
    label: i === sampled.length - 1 ? 'Hiện tại' : relativeLabel(r.ts as number, now),
    value: Math.round((r[metricKey] as number) * 10) / 10,
  }))
}

// ---- Nhiệm vụ & xác minh -------------------------------------------------

const TASK_STATUS: Record<Task['status'], TaskView['status']> = {
  open: 'Chờ',
  completed: 'Đang xử lý', // đã xử lý xong nhưng CHƯA qua verification
  verified: 'Hoàn tất',
}

function hhmm(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? '--:--'
    : `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function toTaskViews(tasks: Task[]): TaskView[] {
  return [...tasks]
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
    .map((t) => ({
      id: t.task_id,
      name: t.title,
      // Phiếu hiện trường do Farm Action Agent tạo (tools.create_inspection_task);
      // nếu phiếu dính thiết bị mất dữ liệu thì Field IoT Agent cũng có phần.
      agent: Object.values(t.stale_flags ?? {}).some(Boolean)
        ? ['Farm Action', 'Field IoT']
        : ['Farm Action'],
      status: TASK_STATUS[t.status] ?? 'Chờ',
      time: hhmm(t.created_at),
    }))
}

export function toVerificationViews(tasks: Task[], plans: Plan[]): VerificationView[] {
  const fromTasks: VerificationView[] = tasks
    .filter((t) => t.verification_proof)
    .map((t) => ({
      name: t.title,
      result: t.verification_proof!.verification_status === 'PASSED' ? 'Thành công' : 'Thất bại',
    }))

  const fromPlans: VerificationView[] = plans
    .filter((p) => p.status !== 'pending_approval')
    .map((p) => ({
      name: `Kế hoạch tưới ${p.zone} (${p.plan_id})`,
      result: p.status === 'confirmed' ? 'Thành công' : 'Thất bại',
    }))

  return [...fromPlans, ...fromTasks].slice(0, 8)
}

// ---- Cảnh báo ------------------------------------------------------------

/** Metric nào lệch nhiều nhất so với trung bình trượt — dùng để nói "vì cảm biến nào". */
export function topDeviation(anomaly: AnomalyPayload): { metric: string; z: number } | null {
  let best: { metric: string; z: number } | null = null
  for (const [key, stat] of Object.entries(anomaly.rolling ?? {})) {
    if (stat.mean === null || stat.std === null || stat.std === 0) continue
    const z = (stat.current - stat.mean) / stat.std
    if (!best || Math.abs(z) > Math.abs(best.z)) best = { metric: metricLabel(key), z }
  }
  return best
}
