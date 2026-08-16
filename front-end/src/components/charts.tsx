import { useEffect, useRef, useState } from 'react'

// Metric label -> hex, matching the colors already used by METRIC_ICON in App.tsx
// so a sparkline/trend line always reads as "the same metric" as its icon.
export const METRIC_COLOR: Record<string, string> = {
  'Độ ẩm đất': '#0EA5E9',
  'Độ ẩm': '#38BDF8',
  'Nhiệt độ': '#F97316',
  'Lưu lượng': '#06B6D4',
  'Công suất': '#F59E0B',
  'Độ pH': '#8B5CF6',
  'Mực nước': '#3B82F6',
  'Cường độ sáng': '#F59E0B',
}

function linePath(points: { x: number; y: number }[]) {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
}

// ---- Sparkline: tiny trend accessory embedded in a device card ----------
// No axes, no hover — decorative-informative only, per the stat-tile trend spec.

const SPARK_W = 100
const SPARK_H = 32

export function Sparkline({ data, color, className = 'h-7 w-full' }: { data: number[]; color: string; className?: string }) {
  if (data.length < 2) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const span = max - min || 1
  const step = SPARK_W / (data.length - 1)

  const points = data.map((v, i) => ({
    x: i * step,
    y: SPARK_H - 3 - ((v - min) / span) * (SPARK_H - 6),
  }))
  const path = linePath(points)
  const area = `${path} L ${points[points.length - 1].x} ${SPARK_H} L 0 ${SPARK_H} Z`
  const last = points[points.length - 1]

  return (
    <svg
      viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}
      preserveAspectRatio="none"
      className={`overflow-visible ${className}`}
      aria-hidden="true"
    >
      <path d={area} fill={color} fillOpacity={0.1} stroke="none" />
      <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <circle cx={last.x} cy={last.y} r={2.5} fill={color} stroke="var(--color-canvas)" strokeWidth={1.5} />
    </svg>
  )
}

// ---- TrendChart: bigger single-series line chart with hover readout -----

export type SeriesPoint = { label: string; value: number }

const PAD = { top: 14, right: 34, bottom: 4, left: 4 }
const CHART_H = 120
const innerH = CHART_H - PAD.top - PAD.bottom
const DEFAULT_CHART_W = 320 // fallback trước khi đo được kích thước thật, tránh chia cho 0

export function TrendChart({
  title,
  deviceId,
  unit,
  color,
  series,
}: {
  title: string
  deviceId: string
  unit: string
  color: string
  series: SeriesPoint[]
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [chartW, setChartW] = useState(DEFAULT_CHART_W)

  // Đo đúng kích thước pixel thật của khung chart (thay vì scale viewBox không đều)
  // để text/vòng tròn không bị méo — SVG 1 đơn vị = 1px thật.
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width
      if (w) setChartW(w)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const innerW = chartW - PAD.left - PAD.right

  const values = series.map((p) => p.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const yMin = min - span * 0.2
  const yMax = max + span * 0.2

  const points = series.map((p, i) => ({
    x: PAD.left + (i / (series.length - 1)) * innerW,
    y: PAD.top + innerH - ((p.value - yMin) / (yMax - yMin)) * innerH,
  }))
  const path = linePath(points)
  const area = `${path} L ${points[points.length - 1].x} ${PAD.top + innerH} L ${points[0].x} ${PAD.top + innerH} Z`
  const dataTicks = [min, (min + max) / 2, max]

  function handleMove(e: React.PointerEvent<SVGSVGElement>) {
    const rect = wrapRef.current?.getBoundingClientRect()
    if (!rect || rect.width === 0) return
    const relX = e.clientX - rect.left
    let nearest = 0
    let bestDist = Infinity
    points.forEach((p, i) => {
      const d = Math.abs(p.x - relX)
      if (d < bestDist) {
        bestDist = d
        nearest = i
      }
    })
    setHoverIndex(nearest)
  }

  const activeIndex = hoverIndex ?? points.length - 1
  const activePoint = points[activeIndex]
  const activeSeriesPoint = series[activeIndex]

  return (
    <div className="rounded-xl border border-[var(--color-line)] p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold">{title}</div>
          <span className="font-mono text-xs font-bold text-[var(--color-ink-soft)]">{deviceId}</span>
        </div>
        <div className="font-display text-xl font-bold leading-none" style={{ color }}>
          {series[series.length - 1].value}
          <span className="ml-0.5 text-xs font-semibold text-[var(--color-ink-soft)]">{unit}</span>
        </div>
      </div>

      <div ref={wrapRef} className="relative mt-2 h-32 w-full">
        {/* Nhãn trục Y — render bằng HTML, không nằm trong SVG, để không bị kéo giãn theo tỉ lệ chart */}
        {dataTicks.map((t, i) => {
          const y = PAD.top + innerH - ((t - yMin) / (yMax - yMin)) * innerH
          return (
            <span
              key={i}
              className="pointer-events-none absolute right-0 -translate-y-1/2 font-mono text-[10px] font-medium text-[var(--color-ink-soft)]"
              style={{ top: `${(y / CHART_H) * 100}%` }}
            >
              {Math.round(t)}
            </span>
          )
        })}

        <svg
          viewBox={`0 0 ${chartW} ${CHART_H}`}
          width={chartW}
          height={CHART_H}
          className="h-full w-full touch-none"
          onPointerMove={handleMove}
          onPointerLeave={() => setHoverIndex(null)}
        >
          {dataTicks.map((t, i) => {
            const y = PAD.top + innerH - ((t - yMin) / (yMax - yMin)) * innerH
            return (
              <line
                key={i}
                x1={PAD.left}
                x2={chartW - PAD.right}
                y1={y}
                y2={y}
                stroke="var(--color-line)"
                strokeWidth={1}
                strokeOpacity={0.6}
              />
            )
          })}

          <path d={area} fill={color} fillOpacity={0.1} stroke="none" />
          <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />

          {hoverIndex !== null && (
            <line
              x1={activePoint.x}
              x2={activePoint.x}
              y1={PAD.top}
              y2={PAD.top + innerH}
              stroke="var(--color-ink-soft)"
              strokeWidth={1}
              strokeOpacity={0.4}
            />
          )}

          <circle cx={activePoint.x} cy={activePoint.y} r={4.5} fill={color} stroke="var(--color-canvas)" strokeWidth={2} />
        </svg>

        {hoverIndex !== null && (
          <div
            className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 -translate-y-[calc(100%+6px)] whitespace-nowrap rounded-lg border border-[var(--color-line)] bg-[var(--color-canvas)] px-2.5 py-1.5 text-xs shadow-md"
            style={{ left: `${activePoint.x}px` }}
          >
            <div className="font-mono font-bold text-[var(--color-ink)]">
              {activeSeriesPoint.value}
              {unit}
            </div>
            <div className="text-[10px] text-[var(--color-ink-soft)]">{activeSeriesPoint.label}</div>
          </div>
        )}
      </div>

      <div className="mt-1 flex justify-between text-[10px] font-medium text-[var(--color-ink-soft)]">
        <span>{series[0].label}</span>
        <span>{series[series.length - 1].label}</span>
      </div>
    </div>
  )
}
