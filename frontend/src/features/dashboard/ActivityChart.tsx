import { useEffect, useRef, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard, LegendRow, TooltipFrame } from './ChartCard'
import { gapRect } from './shapes'
import { fmtDay, fmtInt, fmtMinutes, fmtWeek, MATURITY_LABELS } from './format'
import type { ActivityBucket, HeatmapCell } from './types'
import type { ChartColors } from './useChartColors'

const KEYS = ['new', 'learning', 'mature'] as const

function ActivityTooltip({
  active,
  payload,
  bucket,
}: {
  active?: boolean
  payload?: { payload: ActivityBucket }[]
  bucket: 'day' | 'week'
}) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <TooltipFrame
      title={bucket === 'day' ? fmtDay(p.bucket_start, 'EEE, d MMM') : fmtWeek(p.bucket_start)}
      rows={[
        { label: 'revisões', value: fmtInt(p.total) },
        ...KEYS.map((k) => ({
          label: MATURITY_LABELS[k].toLowerCase(),
          value: fmtInt(p[k]),
          color: `var(--maturity-${k})`,
        })),
        { label: 'de fala', value: fmtMinutes(p.speaking_seconds), muted: true },
      ]}
    />
  )
}

/** GitHub-style calendar: 53 week columns × 7 rows, one-hue sequential ramp (violet). */
export function Heatmap({
  cells,
  year,
  colors,
}: {
  cells: HeatmapCell[]
  year: number
  colors: ChartColors
}) {
  const scroller = useRef<HTMLDivElement>(null)
  // Open the calendar scrolled to the most recent weeks (today sits at the right edge).
  useEffect(() => {
    const el = scroller.current
    if (el) el.scrollLeft = el.scrollWidth
  }, [year])
  const byDate = new Map(cells.map((c) => [c.date, c]))
  const start = new Date(Date.UTC(year, 0, 1))
  const startOffset = (start.getUTCDay() + 6) % 7 // Monday first
  const first = new Date(start)
  first.setUTCDate(first.getUTCDate() - startOffset)
  const max = Math.max(1, ...cells.map((c) => c.count))
  const steps = [colors.band, '#c9c3f3', '#a49ce8', '#7466d2', colors.mature]
  const weeks: { date: string; count: number; inYear: boolean }[][] = []
  const cursor = new Date(first)
  for (let w = 0; w < 53; w++) {
    const col = [] as { date: string; count: number; inYear: boolean }[]
    for (let d = 0; d < 7; d++) {
      const iso = cursor.toISOString().slice(0, 10)
      col.push({ date: iso, count: byDate.get(iso)?.count ?? 0, inYear: cursor.getUTCFullYear() === year })
      cursor.setUTCDate(cursor.getUTCDate() + 1)
    }
    weeks.push(col)
  }
  // Label the column that contains the 1st day of each month (once per month).
  const monthLabels = weeks.map((col) => {
    const first = col.find((c) => c.inYear && new Date(`${c.date}T00:00:00Z`).getUTCDate() === 1)
    return first ? fmtDay(first.date, 'MMM') : null
  })
  const level = (count: number) => (count === 0 ? 0 : Math.min(4, 1 + Math.floor(((count - 1) / max) * 4)))
  return (
    <div ref={scroller} className="overflow-x-auto pb-1">
      <div className="min-w-[680px]">
        <div
          className="mb-1 grid text-[10px] text-fg-muted"
          style={{ gridTemplateColumns: `repeat(53, minmax(0, 1fr))` }}
        >
          {monthLabels.map((m, i) => (
            <span key={i} className="overflow-visible whitespace-nowrap">
              {m ?? ''}
            </span>
          ))}
        </div>
        <div className="grid gap-[2px]" style={{ gridTemplateColumns: `repeat(53, minmax(0, 1fr))` }}>
          {weeks.map((col, wi) => (
            <div key={wi} className="grid gap-[2px]" style={{ gridTemplateRows: 'repeat(7, 1fr)' }}>
              {col.map((c) => (
                <button
                  key={c.date}
                  type="button"
                  className="aspect-square w-full rounded-[2px] focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  style={{ background: c.inYear ? steps[level(c.count)] : 'transparent' }}
                  aria-label={`${fmtDay(c.date, "d 'de' MMMM")}: ${c.count} ${c.count === 1 ? 'resposta' : 'respostas'}`}
                  title={`${fmtDay(c.date, 'd MMM')}: ${c.count}`}
                  tabIndex={c.count ? 0 : -1}
                />
              ))}
            </div>
          ))}
        </div>
        <div className="mt-2 flex items-center gap-1 text-[10px] text-fg-muted">
          <span>menos</span>
          {steps.map((s, i) => (
            <span key={i} className="inline-block size-2.5 rounded-[2px]" style={{ background: s }} />
          ))}
          <span>mais</span>
        </div>
      </div>
    </div>
  )
}

export function ActivityChart({
  buckets,
  bucket,
  heatmap,
  year,
  colors,
  loading,
}: {
  buckets: ActivityBucket[]
  bucket: 'day' | 'week'
  heatmap: HeatmapCell[] | undefined
  year: number
  colors: ChartColors
  loading?: boolean
}) {
  const [mode, setMode] = useState<'bars' | 'calendar'>('bars')
  const totalReviews = buckets.reduce((s, b) => s + b.total, 0)
  const totalSeconds = buckets.reduce((s, b) => s + b.speaking_seconds, 0)
  const Top = gapRect('vertical', true)
  const Mid = gapRect('vertical', false)
  return (
    <ChartCard
      title="Atividade"
      subtitle={mode === 'bars' ? 'Revisões por dia, por maturidade do card' : `Respostas por dia em ${year}`}
      loading={loading}
      empty={mode === 'bars' ? buckets.length === 0 : !heatmap}
      emptyText="Nenhuma revisão no período."
      actions={
        <div role="tablist" aria-label="Modo" className="flex rounded-md border border-border p-0.5 text-xs">
          {(['bars', 'calendar'] as const).map((m) => (
            <button
              key={m}
              role="tab"
              type="button"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={`rounded px-2 py-0.5 ${mode === m ? 'bg-bg font-medium text-fg' : 'text-fg-muted hover:text-fg'}`}
            >
              {m === 'bars' ? 'Barras' : 'Calendário'}
            </button>
          ))}
        </div>
      }
      table={
        mode === 'bars'
          ? {
              columns: [
                bucket === 'day' ? 'Dia' : 'Semana',
                'Novos',
                'Aprendendo',
                'Maduros',
                'Total',
                'Fala',
              ],
              rows: buckets.map((b) => [
                bucket === 'day' ? fmtDay(b.bucket_start, 'dd/MM/yyyy') : fmtWeek(b.bucket_start),
                b.new,
                b.learning,
                b.mature,
                b.total,
                fmtMinutes(b.speaking_seconds),
              ]),
            }
          : {
              columns: ['Dia', 'Respostas', 'Fala'],
              rows: (heatmap ?? []).map((c) => [
                fmtDay(c.date, 'dd/MM/yyyy'),
                c.count,
                fmtMinutes(c.speaking_seconds),
              ]),
            }
      }
      footer={
        <span>
          {fmtInt(totalReviews)} revisões · {fmtMinutes(totalSeconds)} de fala no período
        </span>
      }
    >
      {mode === 'calendar' ? (
        <Heatmap cells={heatmap ?? []} year={year} colors={colors} />
      ) : (
        <>
          <LegendRow
            shape="rect"
            items={KEYS.map((k) => ({ key: k, label: MATURITY_LABELS[k], color: colors[k] }))}
          />
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={buckets}
                margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
                barSize={bucket === 'day' ? 12 : 24}
                barCategoryGap={2}
              >
                <CartesianGrid vertical={false} stroke={colors.grid} />
                <XAxis
                  dataKey="bucket_start"
                  tickFormatter={(v: string) => fmtDay(v)}
                  tick={{ fill: colors.inkMuted, fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: colors.axis }}
                  interval="preserveStartEnd"
                  minTickGap={24}
                />
                <YAxis
                  allowDecimals={false}
                  width={22}
                  tick={{ fill: colors.inkMuted, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip content={<ActivityTooltip bucket={bucket} />} cursor={{ fill: colors.band }} />
                <Bar dataKey="new" stackId="a" fill={colors.new} shape={Mid} isAnimationActive={false} />
                <Bar
                  dataKey="learning"
                  stackId="a"
                  fill={colors.learning}
                  shape={Mid}
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="mature"
                  stackId="a"
                  fill={colors.mature}
                  shape={Top}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </ChartCard>
  )
}
