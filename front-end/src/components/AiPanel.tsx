// Panel chẩn đoán của AI.
//
// Đây là phần trả lời cho tiêu chí "Năng lực phân tích và hỗ trợ quyết định của
// AI" — nên nó phải hiện ĐƯỢC LÝ DO, không chỉ hiện cảnh báo: thiết bị nào kích
// hoạt, model chấm bao nhiêu, metric nào lệch mạnh nhất, Agent đã gọi những tool
// nào, mất bao lâu, và diễn giải bằng tiếng Việt.

import { useState } from 'react'

import type { AgentInsight } from '../lib/api'
import { formatAge, topDeviation } from '../lib/adapt'

// Tên tool backend -> nhãn đọc được, để hàng "Agent đã làm gì" không hiện raw snake_case.
const TOOL_LABEL: Record<string, string> = {
  get_farm_snapshot: 'Đọc cảm biến',
  assess_irrigation_need: 'Đánh giá nhu cầu tưới',
  review_irrigation_session: 'Soát phiên tưới',
  create_irrigation_plan: 'Lập kế hoạch tưới',
  create_inspection_task: 'Tạo phiếu kiểm tra',
  send_notification: 'Gửi thông báo',
  generate_report: 'Tổng hợp báo cáo',
  approve_plan: 'Duyệt kế hoạch',
  complete_task: 'Đóng nhiệm vụ',
}

/** Renderer markdown tối giản — đủ cho đầu ra của LLM, không kéo thêm thư viện. */
function Markdown({ text }: { text: string }) {
  const blocks: React.JSX.Element[] = []
  let bullets: string[] = []

  const flushBullets = () => {
    if (bullets.length === 0) return
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="ml-4 list-disc space-y-1">
        {bullets.map((b, i) => (
          <li key={i}>{inline(b)}</li>
        ))}
      </ul>,
    )
    bullets = []
  }

  for (const raw of text.split('\n')) {
    const line = raw.trimEnd()

    if (!line.trim() || /^-{3,}$/.test(line.trim())) {
      flushBullets()
      continue
    }
    if (/^#{1,6}\s/.test(line)) {
      flushBullets()
      const body = line.replace(/^#+\s*/, '')
      blocks.push(
        <div key={`h-${blocks.length}`} className="mt-3 font-display text-sm font-bold first:mt-0">
          {inline(body)}
        </div>,
      )
      continue
    }
    if (/^\s*[-*]\s+/.test(line)) {
      bullets.push(line.replace(/^\s*[-*]\s+/, ''))
      continue
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      bullets.push(line.replace(/^\s*\d+\.\s+/, ''))
      continue
    }
    // Hàng bảng markdown: bỏ hàng kẻ ngăn cách, hàng còn lại hiện dạng "a · b · c".
    if (line.trim().startsWith('|')) {
      if (/^[\s|:-]+$/.test(line)) continue
      flushBullets()
      const cells = line.split('|').map((c) => c.trim()).filter(Boolean)
      blocks.push(
        <div key={`t-${blocks.length}`} className="text-[13px]">
          {inline(cells.join(' · '))}
        </div>,
      )
      continue
    }

    flushBullets()
    blocks.push(
      <p key={`p-${blocks.length}`} className="leading-relaxed">
        {inline(line)}
      </p>,
    )
  }
  flushBullets()

  return <div className="space-y-1.5 text-[13px] text-[var(--color-ink)]">{blocks}</div>
}

/** Xử lý **đậm** và `code` trong một dòng. */
function inline(text: string): React.JSX.Element {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i}>{part.slice(2, -2)}</strong>
        }
        if (part.startsWith('`') && part.endsWith('`')) {
          return (
            <code key={i} className="rounded bg-[var(--color-field)] px-1 font-mono text-[12px]">
              {part.slice(1, -1)}
            </code>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}

/** Một thẻ chẩn đoán đầy đủ — dùng cho cả bản ghi mới nhất và bản ghi cũ khi mở rộng. */
function InsightCard({ insight }: { insight: AgentInsight }) {
  const deviation = insight.anomaly ? topDeviation(insight.anomaly) : null
  const score = insight.anomaly?.anomaly_score

  return (
    <div className="rounded-xl border-2 border-[#e4c9c9] bg-[#fdf6f6] p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-display text-base font-bold tracking-tight">
            Chẩn đoán: {insight.device_name ?? insight.device_code}
          </div>
          <div className="mt-0.5 font-mono text-xs font-semibold text-[var(--color-ink-soft)]">
            {insight.device_code}
            {typeof insight.latency_ms === 'number' &&
              ` · phản hồi ${(insight.latency_ms / 1000).toFixed(1)}s`}
            {` · ${formatAge(insight.ts)} trước`}
          </div>
        </div>
        {typeof score === 'number' && (
          <div className="text-right">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
              Điểm bất thường
            </div>
            <div className="font-mono text-lg font-bold text-[#a72f2f]">{score.toFixed(2)}</div>
          </div>
        )}
      </div>

      {deviation && (
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-[13px]">
          <span className="text-[var(--color-ink-soft)]">Lệch mạnh nhất: </span>
          <strong>{deviation.metric}</strong>
          <span className="text-[var(--color-ink-soft)]">
            {' '}
            — {deviation.z > 0 ? 'cao hơn' : 'thấp hơn'} trung bình 300 giây gần nhất{' '}
          </span>
          <strong>{Math.abs(deviation.z).toFixed(1)}σ</strong>
        </div>
      )}

      {insight.trace.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            Agent đã làm gì
          </div>
          <div className="flex flex-wrap gap-1.5">
            {insight.trace.map((call, i) => (
              <span
                key={i}
                className="rounded-md bg-white px-2 py-1 text-xs font-semibold text-[var(--color-soil)]"
              >
                {TOOL_LABEL[call.tool] ?? call.tool}
              </span>
            ))}
          </div>
        </div>
      )}

      {insight.error && (
        <div className="mt-3 rounded-lg bg-[#fbe0e0] px-3 py-2 text-[13px] text-[#a72f2f]">
          Agent lỗi: {insight.error}
        </div>
      )}

      {insight.answer && (
        <div className="mt-4 max-h-80 overflow-y-auto rounded-lg bg-white p-4">
          <Markdown text={insight.answer} />
        </div>
      )}
    </div>
  )
}

/**
 * Panel chẩn đoán + Incident Log.
 *
 * Bản ghi mới nhất luôn mở rộng đầy đủ. Các bản ghi cũ hơn thu gọn thành 1
 * dòng (thiết bị, thời điểm, điểm bất thường) — bấm vào để mở chi tiết. Không
 * dùng accordion "chỉ mở 1 cái" vì lúc pitch có thể cần so sánh 2 kịch bản đã
 * demo trước đó cùng lúc.
 */
export function AiPanel({ insights }: { insights: AgentInsight[] }) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  if (insights.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--color-line)] p-5 text-center">
        <div className="text-sm font-semibold text-[var(--color-ink-soft)]">
          Chưa có bất thường nào
        </div>
        <div className="mt-1 text-xs text-[var(--color-ink-soft)]">
          Agent chỉ được gọi khi model phát hiện dữ liệu bất thường — không chạy trên mọi gói tin.
        </div>
      </div>
    )
  }

  const [latest, ...older] = insights

  function toggle(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className="space-y-3">
      <InsightCard insight={latest} />

      {older.length > 0 && (
        <div>
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            Lịch sử chẩn đoán ({older.length})
          </div>
          <div className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
            {older.map((item) => {
              const isOpen = expanded.has(item.id)
              const score = item.anomaly?.anomaly_score
              return (
                <div key={item.id}>
                  <button
                    onClick={() => toggle(item.id)}
                    className="flex w-full items-center justify-between gap-3 rounded-lg border border-[var(--color-line)] bg-[var(--color-canvas)] px-3 py-2 text-left transition-colors hover:bg-[var(--color-field)]"
                  >
                    <span className="min-w-0 flex-1 truncate text-sm font-semibold">
                      {item.device_name ?? item.device_code}
                    </span>
                    {typeof score === 'number' && (
                      <span className="font-mono text-xs font-semibold text-[#a72f2f]">
                        {score.toFixed(2)}
                      </span>
                    )}
                    <span className="shrink-0 text-xs text-[var(--color-ink-soft)]">
                      {formatAge(item.ts)} trước
                    </span>
                  </button>
                  {isOpen && (
                    <div className="mt-1.5">
                      <InsightCard insight={item} />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
