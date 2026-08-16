import { Fragment, useMemo, useState } from 'react'
import { METRIC_COLOR, Sparkline, TrendChart, type SeriesPoint } from './components/charts'
import { AiPanel } from './components/AiPanel'
import { useFarmData } from './lib/useFarmData'
import {
  heroHistories,
  toDeviceViews,
  toSeries,
  toTaskViews,
  toVerificationViews,
  type DeviceView,
} from './lib/adapt'

type Status = 'ok' | 'warn' | 'danger' | 'offline'

const STATUS_COLOR: Record<Status, string> = {
  ok: 'var(--color-ok)',
  warn: 'var(--color-warn)',
  danger: 'var(--color-danger)',
  offline: 'var(--color-offline)',
}

function Dot({ status, size = 8 }: { status: Status; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 8 8"
      aria-hidden="true"
      className="shrink-0"
    >
      <circle cx="4" cy="4" r="4" fill={STATUS_COLOR[status]} />
    </svg>
  )
}

// ---- Icons (inline SVG, single-stroke, currentColor) ---------------------

type IconProps = { className?: string }
const iconBase = 'shrink-0'

function IconDroplet({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="#0EA5E9" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={`${iconBase} ${className}`} aria-hidden="true">
      <path d="M10 2.5S5 8.7 5 12.5a5 5 0 0 0 10 0C15 8.7 10 2.5 10 2.5Z" fill="#BAE6FD" fillOpacity="0.6" />
    </svg>
  )
}

function IconThermometer({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="#F97316" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={`${iconBase} ${className}`} aria-hidden="true">
      <path d="M8.7 11.6V4.3a1.3 1.3 0 1 1 2.6 0v7.3a3.3 3.3 0 1 1-2.6 0Z" fill="#FED7AA" fillOpacity="0.6" />
    </svg>
  )
}

function IconCloud({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="#38BDF8" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={`${iconBase} ${className}`} aria-hidden="true">
      <path d="M6.3 15h7a3 3 0 0 0 .3-6 4.5 4.5 0 0 0-8.6-1.2A3.2 3.2 0 0 0 6.3 15Z" fill="#E0F2FE" fillOpacity="0.6" />
    </svg>
  )
}

function IconWaves({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="#06B6D4" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={`${iconBase} ${className}`} aria-hidden="true">
      <path d="M2.5 8.2c1.3-1.6 2.9-1.6 4.2 0s2.9 1.6 4.2 0 2.9-1.6 4.2 0 2.9-1.6 4.2 0" />
      <path d="M2.5 13c1.3-1.6 2.9-1.6 4.2 0s2.9 1.6 4.2 0 2.9-1.6 4.2 0 2.9-1.6 4.2 0" />
    </svg>
  )
}

function IconBolt({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="#F59E0B" className={`${iconBase} ${className}`} aria-hidden="true">
      <path d="M11 2 4.5 11.5H9l-.6 6.5 6.6-9.5H10.6L11 2Z" />
    </svg>
  )
}

function IconFlask({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="#8B5CF6" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={`${iconBase} ${className}`} aria-hidden="true">
      <path d="M8 2.5h4M8.7 2.5v4.9l-3.9 6.9a2 2 0 0 0 1.7 3h6.9a2 2 0 0 0 1.7-3l-3.9-6.9V2.5" fill="#EDE9FE" fillOpacity="0.6" />
    </svg>
  )
}

function IconTank({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="#3B82F6" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={`${iconBase} ${className}`} aria-hidden="true">
      <ellipse cx="10" cy="5" rx="6" ry="2" fill="#DBEAFE" fillOpacity="0.6" />
      <path d="M4 5v9a6 2 0 0 0 12 0V5" fill="#DBEAFE" fillOpacity="0.4" />
    </svg>
  )
}

function IconSun({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="#F59E0B" strokeWidth="1.6" strokeLinecap="round" className={`${iconBase} ${className}`} aria-hidden="true">
      <circle cx="10" cy="10" r="3.3" fill="#FBBF24" stroke="none" />
      <path d="M10 2.7v2M10 15.3v2M2.7 10h2M15.3 10h2M4.8 4.8l1.4 1.4M13.8 13.8l1.4 1.4M15.2 4.8l-1.4 1.4M6.2 13.8l-1.4 1.4" />
    </svg>
  )
}

function IconCheckCircle({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={`${iconBase} ${className}`} aria-hidden="true">
      <circle cx="10" cy="10" r="7.3" />
      <path d="M6.8 10.2l2.1 2.1 4.2-4.6" />
    </svg>
  )
}

function IconXCircle({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={`${iconBase} ${className}`} aria-hidden="true">
      <circle cx="10" cy="10" r="7.3" />
      <path d="M7.5 7.5l5 5M12.5 7.5l-5 5" />
    </svg>
  )
}

function IconClock({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={`${iconBase} ${className}`} aria-hidden="true">
      <circle cx="10" cy="10" r="7.3" />
      <path d="M10 5.8V10l2.8 1.8" />
    </svg>
  )
}

function IconLoader({ className = 'h-3.5 w-3.5' }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" className={`${iconBase} ${className}`} aria-hidden="true">
      <path d="M16 10a6 6 0 1 1-1.8-4.3" />
      <path d="M16 4.5v3.7h-3.7" />
    </svg>
  )
}

// Metric label → icon, keyed by the exact label text used in device data.
const METRIC_ICON: Record<string, (props: IconProps) => React.JSX.Element> = {
  'Độ ẩm đất': IconDroplet,
  'Độ ẩm': IconCloud,
  'Nhiệt độ': IconThermometer,
  'Lưu lượng': IconWaves,
  'Công suất': IconBolt,
  'Độ pH': IconFlask,
  'Mực nước': IconTank,
  'Cường độ sáng': IconSun,
}

const STATUS_ICON: Record<'Chờ' | 'Đang xử lý' | 'Hoàn tất', (props: IconProps) => React.JSX.Element> = {
  'Chờ': IconClock,
  'Đang xử lý': IconLoader,
  'Hoàn tất': IconCheckCircle,
}

function Badge({
  children,
  tone = 'neutral',
}: {
  children: React.ReactNode
  tone?: 'neutral' | 'ok' | 'warn' | 'danger' | 'offline' | 'leaf' | 'soil'
}) {
  const tones: Record<string, string> = {
    neutral: 'bg-[var(--color-soil-soft)] text-[var(--color-soil)]',
    ok: 'bg-[var(--color-leaf-soft)] text-[var(--color-leaf-deep)]',
    warn: 'bg-[#fbf1d6] text-[#946a06]',
    danger: 'bg-[#fbe0e0] text-[#a72f2f]',
    offline: 'bg-[#ececea] text-[#6d7268]',
    leaf: 'bg-[var(--color-leaf)] text-white',
    soil: 'bg-[var(--color-soil)] text-white',
  }
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm font-bold tracking-tight ${tones[tone]}`}
    >
      {children}
    </span>
  )
}

// Mỗi agent một màu riêng để dễ phân biệt trong bảng nhiệm vụ / kế hoạch.
const AGENT_COLOR: Record<string, string> = {
  'Field IoT': 'bg-[#dbeafe] text-[#1d4ed8]',
  'Irrigation Planning': 'bg-[#cffafe] text-[#0e7490]',
  'Resource': 'bg-[#ede9fe] text-[#6d28d9]',
  'Farm Action': 'bg-[#fef3c7] text-[#b45309]',
  'Farm Coordinator': 'bg-[#e0e7ff] text-[#4338ca]',
}

function AgentBadge({ agent, label }: { agent: string; label?: string }) {
  const cls = AGENT_COLOR[agent] ?? 'bg-[var(--color-soil-soft)] text-[var(--color-soil)]'
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-tight ${cls}`}
    >
      {label ?? agent}
    </span>
  )
}

// ---- Dữ liệu dự phòng ----------------------------------------------------
//
// Chỉ dùng khi CHƯA kết nối được backend. Giữ lại có chủ đích: mất mạng giữa
// buổi demo thì dashboard vẫn có hình để trình bày thay vì trắng trơn — nhưng
// thanh trạng thái trên đầu sẽ ghi rõ "Dữ liệu mẫu" để không ai nhầm là số thật.

const mockDevices: DeviceView[] = [
  {
    id: 'SOIL_01',
    name: 'Cảm biến đất',
    status: 'ok',
    age: '12 giây',
    metrics: [
      { label: 'Độ ẩm đất', value: '68%', history: [72, 71, 70, 70, 69, 69, 68, 68] },
      { label: 'Nhiệt độ', value: '27°C' },
    ],
  },
  {
    id: 'WEATHER_01',
    name: 'Trạm thời tiết',
    status: 'ok',
    age: '30 giây',
    metrics: [
      { label: 'Nhiệt độ', value: '24°C', history: [22, 23, 23, 24, 25, 24, 23, 24] },
      { label: 'Độ ẩm', value: '82%' },
    ],
  },
  {
    id: 'PUMP_01',
    name: 'Bơm tưới Khu A',
    status: 'ok',
    age: '45 giây',
    metrics: [
      { label: 'Lưu lượng', value: '18 L/min', history: [15, 16, 17, 19, 20, 18, 17, 18] },
      { label: 'Công suất', value: '340 W' },
    ],
  },
  {
    id: 'PH_01',
    name: 'Cảm biến pH bồn',
    status: 'warn',
    age: '1 phút',
    metrics: [{ label: 'Độ pH', value: '6.4', history: [6.1, 6.2, 6.3, 6.5, 6.6, 6.5, 6.4, 6.4] }],
  },
  {
    id: 'TANK_01',
    name: 'Bồn nước chính',
    status: 'ok',
    age: '18 giây',
    metrics: [{ label: 'Mực nước', value: '72%', history: [76, 75, 74, 73, 73, 72, 72, 72] }],
  },
  {
    id: 'SUN_01',
    name: 'Cảm biến nắng',
    status: 'offline',
    age: '8 phút',
    metrics: [{ label: 'Cường độ sáng', value: '—' }],
  },
]

// 3 tiếng gần nhất, mỗi điểm cách nhau 15 phút — dùng cho 2 chart xu hướng chính.
// Độ ẩm đất & mực nước bồn đều đang giảm dần dù số hiện tại chưa ở mức báo động,
// đúng tinh thần "sliding window bắt xu hướng" của đề bài.
const mockSoilMoistureTrend: SeriesPoint[] = [
  { label: '−3 giờ', value: 76 },
  { label: '−2g45', value: 75 },
  { label: '−2g30', value: 75 },
  { label: '−2g15', value: 74 },
  { label: '−2 giờ', value: 74 },
  { label: '−1g45', value: 73 },
  { label: '−1g30', value: 72 },
  { label: '−1g15', value: 71 },
  { label: '−1 giờ', value: 71 },
  { label: '−45p', value: 70 },
  { label: '−30p', value: 69 },
  { label: '−15p', value: 69 },
  { label: 'Hiện tại', value: 68 },
]

const mockTankLevelTrend: SeriesPoint[] = [
  { label: '−3 giờ', value: 81 },
  { label: '−2g45', value: 80 },
  { label: '−2g30', value: 80 },
  { label: '−2g15', value: 79 },
  { label: '−2 giờ', value: 78 },
  { label: '−1g45', value: 77 },
  { label: '−1g30', value: 76 },
  { label: '−1g15', value: 76 },
  { label: '−1 giờ', value: 75 },
  { label: '−45p', value: 74 },
  { label: '−30p', value: 73 },
  { label: '−15p', value: 73 },
  { label: 'Hiện tại', value: 72 },
]

type Task = {
  id?: string
  name: string
  agent: string[]
  status: 'Chờ' | 'Đang xử lý' | 'Hoàn tất'
  time: string
}

const mockTasks: Task[] = [
  { name: 'Tưới Khu A', agent: ['Irrigation Planning', 'Farm Action'], status: 'Đang xử lý', time: '06:12' },
  { name: 'Đọc dữ liệu SOIL_01', agent: ['Field IoT'], status: 'Hoàn tất', time: '05:40' },
  { name: 'Xác nhận nguồn nước TANK_01', agent: ['Resource'], status: 'Hoàn tất', time: '05:30' },
  { name: 'Kiểm tra phiên tưới Khu A', agent: ['Field IoT'], status: 'Đang xử lý', time: '05:58' },
  { name: 'Kiểm tra kết nối SUN_01', agent: ['Farm Action'], status: 'Chờ', time: '06:14' },
  { name: 'Tạo báo cáo canh tác', agent: ['Farm Coordinator'], status: 'Chờ', time: '06:05' },
]

type Verification = {
  name: string
  result: 'Thành công' | 'Thất bại'
}

const mockVerifications: Verification[] = [
  { name: 'Van tưới Khu A', result: 'Thành công' },
  { name: 'Cảm biến SOIL_01', result: 'Thành công' },
  { name: 'Kết nối SUN_01', result: 'Thất bại' },
  { name: 'Bơm PUMP_01', result: 'Thành công' },
  { name: 'Đồng bộ WEATHER_01', result: 'Thành công' },
  { name: 'Báo cáo canh tác', result: 'Thất bại' },
]

const taskTone: Record<string, 'warn' | 'leaf' | 'ok'> = {
  'Chờ': 'warn',
  'Đang xử lý': 'leaf',
  'Hoàn tất': 'ok',
}

// Card kế hoạch tưới luôn nền xanh lá trơn; trạng thái phê duyệt chỉ thể hiện qua badge.
const PLAN_CARD_STYLE = 'border-[#bfe3c4] bg-[#e6f5e8]'

// ---- App ----------------------------------------------------------------

export default function App() {
  const { data, actions } = useFarmData()
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  // Khi backend chưa trả dữ liệu, mọi thứ rơi về bộ mẫu — xem ghi chú ở mockDevices.
  const devices = useMemo(
    () =>
      data.live && Object.keys(data.snapshot).length > 0
        ? toDeviceViews(data.snapshot, heroHistories(data.records), data.anomalyAt)
        : mockDevices,
    [data.live, data.snapshot, data.records, data.anomalyAt],
  )

  const taskList = useMemo(
    () => (data.live ? toTaskViews(data.tasks) : mockTasks),
    [data.live, data.tasks],
  )

  const verificationLog = useMemo(
    () => (data.live ? toVerificationViews(data.tasks, data.plans) : mockVerifications),
    [data.live, data.tasks, data.plans],
  )

  const soilTrend = useMemo(() => {
    const s = toSeries(data.records.SOIL_01 ?? [], 'soil_moisture')
    return s.length >= 2 ? s : mockSoilMoistureTrend
  }, [data.records])

  const tankTrend = useMemo(() => {
    const s = toSeries(data.records.TANK_01 ?? [], 'level')
    return s.length >= 2 ? s : mockTankLevelTrend
  }, [data.records])

  // Kế hoạch mới nhất — ưu tiên cái đang chờ duyệt, vì đó là cái người quản lý cần xử lý.
  const plan = useMemo(() => {
    if (!data.live || data.plans.length === 0) return null
    return data.plans.find((p) => p.status === 'pending_approval') ?? data.plans[0]
  }, [data.live, data.plans])

  const onlineDeviceCount = devices.filter((d) => d.status !== 'offline').length
  const planStatus: 'pending' | 'approved' | 'rejected' = !plan
    ? 'pending'
    : plan.status === 'confirmed'
      ? 'approved'
      : plan.status === 'rejected'
        ? 'rejected'
        : 'pending'

  async function run(fn: () => Promise<unknown>) {
    setBusy(true)
    setActionError(null)
    try {
      await fn()
    } catch (err) {
      setActionError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const handleApprove = () => plan && run(() => actions.approvePlan(plan.plan_id))
  const handleReject = () => plan && run(() => actions.rejectPlan(plan.plan_id))

  // Nút "Bơm sự cố": ép độ ẩm đất xuống 3% — model bắt bất thường, Agent chẩn đoán.
  const handleInjectDrought = () =>
    run(() => actions.inject('SOIL_01', { soil_moisture: 3.0 }))

  // Kịch bản 3: cảm biến ngừng gửi dữ liệu.
  const handleToggleSun = () => {
    const sun = devices.find((d) => d.id === 'SUN_01')
    return run(() => (sun?.status === 'offline' ? actions.unfreeze('SUN_01') : actions.freeze('SUN_01')))
  }

  return (
    <div className="min-h-full bg-[var(--color-field)] text-[var(--color-ink)]">
      {/* TOP BAR */}
      <header className="sticky top-0 z-30 border-b border-[var(--color-line)] bg-[var(--color-canvas)]/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <div className="mr-auto flex items-center gap-2">
            <img src="/logo-sprout.png" alt="" className="h-7 w-7 object-contain" />
            <span className="font-display text-xl font-extrabold tracking-tight text-[var(--color-leaf-deep)]">
              AeMT
            </span>
            <span className="hidden text-xs font-medium text-[var(--color-ink-soft)] sm:inline">
              Multi-Agent Farm
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Dot status={data.connected ? 'ok' : data.live ? 'warn' : 'offline'} size={10} />
            <span className="text-sm font-semibold">
              {data.connected ? 'Trực tuyến' : data.live ? 'Mất kết nối' : 'Dữ liệu mẫu'}
            </span>
            {data.scenario !== 'NORMAL' && <Badge tone="danger">{data.scenario}</Badge>}
          </div>

          <div className="hidden flex-col leading-tight sm:flex">
            <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-ink-soft)]">
              Cập nhật
            </span>
            <span className="font-mono text-sm font-semibold">
              {data.lastUpdate ? new Date(data.lastUpdate).toLocaleTimeString('vi-VN') : '--:--:--'}
            </span>
          </div>

          {/* Điều khiển demo — bơm sự cố / ngắt cảm biến theo ý muốn lúc pitch,
              thay vì ngồi chờ dữ liệu tự bất thường đúng lúc trình bày. */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleInjectDrought}
              disabled={busy || !data.live}
              className="rounded-lg border border-[var(--color-danger)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--color-danger)] transition-colors hover:bg-[var(--color-danger)] hover:text-white disabled:opacity-40"
            >
              Bơm sự cố hạn
            </button>
            <button
              onClick={handleToggleSun}
              disabled={busy || !data.live}
              className="rounded-lg border border-[var(--color-line)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-field)] disabled:opacity-40"
            >
              {devices.find((d) => d.id === 'SUN_01')?.status === 'offline'
                ? 'Nối lại SUN_01'
                : 'Ngắt SUN_01'}
            </button>
          </div>
        </div>

        {(actionError || (!data.live && data.error)) && (
          <div className="border-t border-[var(--color-line)] bg-[#fbe0e0] px-4 py-2 text-xs font-medium text-[#a72f2f] sm:px-6">
            {actionError ?? `Không kết nối được backend (${data.error}). Đang hiển thị dữ liệu mẫu.`}
          </div>
        )}
      </header>

      {/* CONTENT */}
      <main className="mx-auto flex max-w-[1440px] flex-col gap-5 px-4 py-5 sm:px-6">
        {/* THIẾT BỊ IOT — 1 khối, chia ô bằng đường kẻ nội bộ thay vì card riêng */}
        <section className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-canvas)] p-5 shadow-sm sm:p-6">
          <div className="mb-3 flex items-center gap-2">
            <h3 className="font-display text-lg font-bold tracking-tight">Thiết bị IoT</h3>
            <Badge tone={onlineDeviceCount === devices.length ? 'ok' : 'warn'}>
              {onlineDeviceCount}/{devices.length} online
            </Badge>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            {devices.map((d) => {
              const off = d.status === 'offline'
              return (
                <div
                  key={d.id}
                  className={`flex h-full flex-col rounded-xl border-2 border-[var(--color-line)] p-4 ${
                    off ? 'bg-[#e4e4e1] text-[var(--color-offline)]' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold tracking-tight text-[var(--color-ink-soft)]">
                      {d.id}
                    </span>
                    <Dot status={d.status} />
                  </div>
                  <div
                    className={`mt-0.5 text-sm font-semibold ${
                      off ? 'text-[var(--color-offline)]' : 'text-[var(--color-ink)]'
                    }`}
                  >
                    {d.name}
                  </div>

                  <div className="mt-3 grid grid-cols-[1fr_auto] items-baseline gap-x-2 gap-y-1.5">
                    {d.metrics.map((m, i) => {
                      const MetricIcon = METRIC_ICON[m.label]
                      return (
                        <Fragment key={m.label}>
                          <span className="flex items-center gap-1 text-[11px] font-medium text-[var(--color-ink-soft)]">
                            {MetricIcon && <MetricIcon className="h-3 w-3" />}
                            {m.label}
                          </span>
                          <span
                            className={
                              i === 0
                                ? `font-display text-2xl font-bold leading-none tracking-tight text-right ${
                                    off ? 'text-[var(--color-offline)]' : 'text-[var(--color-ink)]'
                                  }`
                                : `text-right text-sm font-semibold ${
                                    off ? 'text-[var(--color-offline)]' : 'text-[var(--color-ink)]'
                                  }`
                            }
                          >
                            {off ? '—' : m.value}
                          </span>
                        </Fragment>
                      )
                    })}
                  </div>

                  {/* Ghim sparkline + độ mới dữ liệu xuống đáy card để thẳng hàng giữa các ô dù số dòng metric khác nhau */}
                  <div className="mt-auto pt-3">
                    {!off && d.metrics[0].history && (
                      <Sparkline data={d.metrics[0].history} color={METRIC_COLOR[d.metrics[0].label]} />
                    )}
                    <div className="mt-3 text-xs font-medium text-[var(--color-ink-soft)]">
                      {off ? 'Mất kết nối' : d.age}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        {/* XU HƯỚNG DỮ LIỆU — sliding window 3 tiếng, bắt xu hướng dù số hiện tại chưa báo động */}
        <section className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-canvas)] p-5 shadow-sm sm:p-6">
          <h3 className="mb-3 font-display text-lg font-bold tracking-tight">Xu hướng dữ liệu</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <TrendChart
              title="Độ ẩm đất — Khu A"
              deviceId="SOIL_01"
              unit="%"
              color={METRIC_COLOR['Độ ẩm đất']}
              series={soilTrend}
            />
            <TrendChart
              title="Mực nước bồn chính"
              deviceId="TANK_01"
              unit="%"
              color={METRIC_COLOR['Mực nước']}
              series={tankTrend}
            />
          </div>
        </section>

        {/* CHẨN ĐOÁN CỦA AI — hiện LÝ DO chứ không chỉ hiện cảnh báo.
            Agent chỉ chạy khi model phát hiện bất thường, không chạy mọi gói tin. */}
        <section className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-canvas)] p-5 shadow-sm sm:p-6">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h3 className="font-display text-lg font-bold tracking-tight">Chẩn đoán của AI</h3>
            {data.insights.length > 0 && (
              <AgentBadge agent="Farm Coordinator" label="Farm Coordinator Agent" />
            )}
          </div>

          {data.veto && Date.now() - data.veto.at < 120_000 && (
            <div className="mb-3 rounded-xl border-2 border-[#a72f2f] bg-[#fbe0e0] p-4">
              <div className="font-display text-sm font-bold text-[#a72f2f]">
                VETO — guardrail cứng đã chặn hành động
              </div>
              <div className="mt-1 text-[13px] text-[#a72f2f]">{data.veto.reason}</div>
              <div className="mt-2 text-xs text-[#a72f2f]/80">
                Lớp luật vật lý bằng Python thuần, LLM không có quyền phủ quyết.
              </div>
            </div>
          )}

          <AiPanel insights={data.insights} />
        </section>

        {/* VẬN HÀNH HÔM NAY — kế hoạch + nhiệm vụ + xác minh gộp 1 khối, chia bằng đường kẻ */}
        <section className="rounded-2xl border border-[var(--color-line)] bg-[var(--color-canvas)] p-5 shadow-sm sm:p-6">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:divide-x-2 lg:divide-[var(--color-line)]">
            {/* Cột trái: kế hoạch tưới + nhiệm vụ */}
            <div className="flex flex-col lg:col-span-8 lg:pr-6">
              <div className={`rounded-2xl border-2 p-5 transition-colors sm:p-6 ${PLAN_CARD_STYLE}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="font-display text-2xl font-extrabold tracking-tight sm:text-3xl">
                      Kế hoạch tưới hôm nay
                    </h2>
                    <div className="mt-1 flex items-center gap-2">
                      <AgentBadge agent="Irrigation Planning" label="Irrigation Planning Agent" />
                    </div>
                  </div>
                  {planStatus === 'pending' && (
                    <Badge tone="danger">
                      {plan ? `Ưu tiên ${plan.priority}` : 'Ưu tiên cao'}
                    </Badge>
                  )}
                  {planStatus === 'approved' && (
                    <Badge tone="ok">
                      <IconCheckCircle className="mr-1 h-3 w-3" />
                      Đã duyệt
                    </Badge>
                  )}
                  {planStatus === 'rejected' && (
                    <Badge tone="danger">
                      <IconXCircle className="mr-1 h-3 w-3" />
                      Đã từ chối
                    </Badge>
                  )}
                </div>

                <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
                  <Field label="Khu vực" value={plan ? `Khu ${plan.zone}` : 'Khu A'} />
                  <Field label="Khung giờ" value={plan?.scheduled_time ?? '06:30 – 07:15'} mono />
                  <Field
                    label="Thời lượng"
                    value={plan ? `${plan.duration_minutes} phút` : '45 phút'}
                    mono
                  />
                </div>

                {plan?.rationale && (
                  <div className="mt-5">
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
                      Lý do
                    </div>
                    <p className="text-[13px] leading-relaxed">{plan.rationale}</p>
                  </div>
                )}

                <div className="mt-5">
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
                    Dữ liệu căn cứ
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(plan?.used_devices ?? ['SOIL_01', 'WEATHER_01', 'TANK_01', 'SUN_01', 'PUMP_01']).map(
                      (c) => {
                        const reading = plan?.data_snapshot?.[c]
                        const hero = reading
                          ? Object.entries(reading).find(([k]) => k !== 'ts')
                          : undefined
                        return (
                          <span
                            key={c}
                            className="rounded-md bg-[var(--color-canvas)] px-2 py-1 font-mono text-xs font-semibold text-[var(--color-soil)]"
                            title={hero ? `${hero[0]} = ${hero[1]} lúc lập kế hoạch` : undefined}
                          >
                            {c}
                            {hero && (
                              <span className="ml-1 font-normal text-[var(--color-ink-soft)]">
                                {Math.round(Number(hero[1]) * 10) / 10}
                              </span>
                            )}
                          </span>
                        )
                      },
                    )}
                  </div>
                </div>

                {plan && !plan.guardrail_check.allowed && (
                  <div className="mt-4 rounded-lg bg-[#fbe0e0] px-3 py-2 text-[13px] font-medium text-[#a72f2f]">
                    {plan.guardrail_check.reason}
                  </div>
                )}

                <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
                  {!plan && data.live && (
                    <span className="mr-auto text-[13px] font-medium text-[var(--color-ink-soft)]">
                      Chưa có kế hoạch nào — Agent sẽ tự lập khi phát hiện đất thiếu nước.
                    </span>
                  )}
                  {planStatus === 'pending' ? (
                    <>
                      <button
                        onClick={handleReject}
                        disabled={busy || !plan}
                        className="rounded-xl border border-[var(--color-danger)] bg-white px-5 py-2.5 text-sm font-semibold text-[var(--color-danger)] shadow-sm transition-colors hover:bg-[var(--color-danger)] hover:text-white disabled:opacity-40"
                      >
                        Từ chối
                      </button>
                      <button
                        onClick={handleApprove}
                        disabled={busy || !plan}
                        className="rounded-xl border border-[var(--color-leaf-deep)] bg-[var(--color-leaf)] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[var(--color-leaf-deep)] disabled:opacity-40"
                      >
                        Phê duyệt
                      </button>
                    </>
                  ) : (
                    <span className="font-mono text-xs font-semibold text-[var(--color-ink-soft)]">
                      {plan?.plan_id}
                      {plan?.approved_by && ` · ${plan.approved_by}`}
                    </span>
                  )}
                </div>
              </div>

              <div className="mt-8 border-t-2 border-[var(--color-line)] pt-6">
                <SectionTitle inline>Nhiệm vụ</SectionTitle>
                <div className="mt-1 overflow-x-auto">
                  <table className="w-full min-w-[480px] border-collapse text-left">
                    <thead>
                      <tr className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
                        <th className="py-2 pr-3 font-semibold">Nhiệm vụ</th>
                        <th className="py-2 pr-3 font-semibold">Agent</th>
                        <th className="py-2 pr-3 font-semibold">Trạng thái</th>
                        <th className="py-2 pr-3 font-semibold">Tạo lúc</th>
                        <th className="py-2 font-semibold">Hành động</th>
                      </tr>
                    </thead>
                    <tbody>
                      {taskList.map((t) => {
                        const StatusIcon = STATUS_ICON[t.status]
                        // Chỉ nhiệm vụ có id thật (đến từ backend, không phải dữ liệu mẫu)
                        // và chưa qua verification mới cho bấm — đây chính là bước
                        // "xác minh sau hành động" mà Track B yêu cầu.
                        const canVerify = data.live && t.id && t.status !== 'Hoàn tất'
                        return (
                          <tr
                            key={t.id ?? t.name}
                            className="border-t border-[var(--color-line)] transition-colors hover:bg-[var(--color-field)]"
                          >
                            <td className="py-3 pr-3 text-sm font-semibold">{t.name}</td>
                            <td className="py-3 pr-3">
                              <div className="flex flex-wrap gap-1.5">
                                {t.agent.map((a) => (
                                  <AgentBadge key={a} agent={a} />
                                ))}
                              </div>
                            </td>
                            <td className="py-3 pr-3">
                              <Badge tone={taskTone[t.status]}>
                                <StatusIcon
                                  className={`mr-1 h-3 w-3 ${t.status === 'Đang xử lý' ? 'animate-spin' : ''}`}
                                />
                                {t.status}
                              </Badge>
                            </td>
                            <td className="py-3 pr-3 font-mono text-sm text-[var(--color-ink-soft)]">
                              {t.time}
                            </td>
                            <td className="py-3">
                              {canVerify ? (
                                <button
                                  onClick={() => run(() => actions.verifyTask(t.id!))}
                                  disabled={busy}
                                  className="rounded-lg border border-[var(--color-leaf-deep)] px-2.5 py-1 text-xs font-semibold text-[var(--color-leaf-deep)] transition-colors hover:bg-[var(--color-leaf)] hover:text-white disabled:opacity-40"
                                >
                                  Xác minh
                                </button>
                              ) : (
                                t.status === 'Hoàn tất' && (
                                  <span className="text-xs text-[var(--color-ink-soft)]">Đã xác minh</span>
                                )
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Cột phải: xác minh */}
            <div className="lg:col-span-4 lg:pl-6">
              <SectionTitle inline>Xác minh gần nhất</SectionTitle>
              <ul className="mt-1 divide-y divide-[var(--color-line)]">
                {verificationLog.map((v, i) => {
                  const ok = v.result === 'Thành công'
                  const ResultIcon = ok ? IconCheckCircle : IconXCircle
                  return (
                    <li key={`${v.name}-${i}`} className="flex items-center justify-between gap-3 py-2.5">
                      <span className="truncate text-sm font-medium">{v.name}</span>
                      <Badge tone={ok ? 'ok' : 'danger'}>
                        <ResultIcon className="mr-1 h-3 w-3" />
                        {v.result}
                      </Badge>
                    </li>
                  )
                })}
              </ul>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

function SectionTitle({
  children,
  inline = false,
}: {
  children: React.ReactNode
  inline?: boolean
}) {
  return (
    <h3
      className={`font-display text-lg font-bold tracking-tight ${
        inline ? 'mb-3' : 'mb-3'
      }`}
    >
      {children}
    </h3>
  )
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
        {label}
      </div>
      <div
        className={`mt-0.5 text-base font-bold text-[var(--color-ink)] ${
          mono ? 'font-mono' : 'font-display'
        }`}
      >
        {value}
      </div>
    </div>
  )
}
