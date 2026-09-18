import { useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard, LegendRow, TooltipFrame } from './ChartCard'
import { Sparkline } from './Sparkline'
import { endLabel } from './shapes'
import { Delta } from './KpiTiles'
import { AXIS_LABELS, fmtDay, fmtScore, fmtWeek } from './format'
import type { ScoreBucket, ScoreSummary } from './types'
import type { ChartColors } from './useChartColors'

type AxisKey = keyof typeof AXIS_LABELS
const AXES: AxisKey[] = ['structure', 'grammar', 'fluency']

type Point = {
  date: string
  structure: number | null
  grammar: number | null
  fluency: number | null
  attempts: number
  raw: boolean
}

function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

/** Daily buckets -> full calendar + 7-day trailing weighted average per axis. */
function movingAverage(buckets: ScoreBucket[], from: string, to: string): Point[] {
  const byDate = new Map(buckets.map((b) => [b.bucket_start, b]))
  const days: string[] = []
  for (let d = from; d <= to; d = addDays(d, 1)) days.push(d)
  return days.map((date) => {
    const window: ScoreBucket[] = []
    for (let i = 0; i < 7; i++) {
      const b = byDate.get(addDays(date, -i))
      if (b) window.push(b)
    }
    const weight = window.reduce((s, b) => s + b.attempts, 0)
    const avg = (key: AxisKey) => {
      const values = window.filter((b) => b[`${key}_avg`] != null)
      if (!values.length) return null
      const w = values.reduce((s, b) => s + b.attempts, 0) || 1
      return (
        Math.round((values.reduce((s, b) => s + (b[`${key}_avg`] as number) * b.attempts, 0) / w) * 100) / 100
      )
    }
    return {
      date,
      structure: avg('structure'),
      grammar: avg('grammar'),
      fluency: avg('fluency'),
      attempts: weight,
      raw: byDate.has(date),
    }
  })
}

type DotProps = { cx?: number; cy?: number; payload?: Point; index?: number }

/** Daily buckets: a marker only on days that actually have answers (the line is the 7-day average). */
function dailyDot(color: string, dim: boolean, surface: string) {
  return (raw: unknown) => {
    const props = raw as DotProps
    if (!props.payload?.raw || props.cx == null || props.cy == null || dim) return <g key={props.index} />
    return (
      <circle
        key={props.index}
        cx={props.cx}
        cy={props.cy}
        r={4}
        fill={color}
        stroke={surface}
        strokeWidth={2}
      />
    )
  }
}

function ScoreTooltip({
  active,
  payload,
  bucket,
}: {
  active?: boolean
  payload?: { payload: Point }[]
  bucket: 'day' | 'week'
  colors?: ChartColors
}) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <TooltipFrame
      title={bucket === 'day' ? `${fmtDay(p.date, 'EEE, d MMM')} · média 7 dias` : fmtWeek(p.date)}
      rows={[
        ...AXES.map((k) => ({ label: AXIS_LABELS[k], value: fmtScore(p[k]), color: `var(--axis-${k})` })),
        { label: 'respostas', value: String(p.attempts), muted: true },
      ]}
    />
  )
}

export function ScoreTrend({
  buckets,
  bucket,
  from,
  to,
  summary,
  previous,
  colors,
  loading,
}: {
  buckets: ScoreBucket[]
  bucket: 'day' | 'week'
  from: string
  to: string
  summary: ScoreSummary
  previous: ScoreSummary
  colors: ChartColors
  loading?: boolean
}) {
  const [emphasis, setEmphasis] = useState<AxisKey | null>(null)
  const data = useMemo<Point[]>(() => {
    if (bucket === 'day') return movingAverage(buckets, from, to)
    return buckets.map((b) => ({
      date: b.bucket_start,
      structure: b.structure_avg,
      grammar: b.grammar_avg,
      fluency: b.fluency_avg,
      attempts: b.attempts,
      raw: true,
    }))
  }, [buckets, bucket, from, to])
  const lastIndex = data.length - 1
  const hasData = buckets.length > 0

  const table = {
    columns: [
      bucket === 'day' ? 'Dia' : 'Semana',
      'Estrutura',
      'Gramática',
      'Fluência',
      'Média',
      'Respostas',
    ],
    rows: buckets.map((b) => [
      bucket === 'day' ? fmtDay(b.bucket_start, 'dd/MM/yyyy') : fmtWeek(b.bucket_start),
      fmtScore(b.structure_avg),
      fmtScore(b.grammar_avg),
      fmtScore(b.fluency_avg),
      fmtScore(b.composite_avg),
      b.attempts,
    ]),
  }

  return (
    <ChartCard
      title="Evolução das notas"
      subtitle={
        bucket === 'day'
          ? 'Média móvel de 7 dias por eixo (1–5); pontos = média do dia'
          : 'Média semanal por eixo (1–5)'
      }
      table={table}
      loading={loading}
      empty={!hasData}
      emptyText="Nenhuma resposta avaliada no período."
      footer={
        <div className="grid grid-cols-3 gap-3">
          {AXES.map((k) => {
            const cur = summary[`${k}_avg`]
            const prev = previous[`${k}_avg`]
            const delta = cur != null && prev != null ? Math.round((cur - prev) * 10) / 10 : null
            return (
              <div key={k} className="flex items-center justify-between gap-2">
                <div>
                  <p className="flex items-center gap-1.5 text-fg-muted">
                    <span
                      aria-hidden
                      className="inline-block h-0.5 w-3 rounded"
                      style={{ background: colors[k] }}
                    />
                    {AXIS_LABELS[k]}
                  </p>
                  <p className="text-base font-semibold text-fg">
                    {fmtScore(cur)} <Delta value={delta} decimals={1} />
                  </p>
                </div>
                <Sparkline values={data.map((p) => p[k])} color={colors[k]} width={64} height={24} />
              </div>
            )
          })}
        </div>
      }
    >
      <LegendRow
        items={AXES.map((k) => ({ key: k, label: AXIS_LABELS[k], color: colors[k] }))}
        active={emphasis}
        onToggle={(k) => setEmphasis((cur) => (cur === k ? null : (k as AxisKey)))}
      />
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 84, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={colors.grid} />
            <XAxis
              dataKey="date"
              tickFormatter={(v: string) => fmtDay(v)}
              tick={{ fill: colors.inkMuted, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: colors.axis }}
              interval="preserveStartEnd"
              minTickGap={28}
            />
            <YAxis
              domain={[1, 5]}
              ticks={[1, 2, 3, 4, 5]}
              width={22}
              tick={{ fill: colors.inkMuted, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              content={<ScoreTooltip bucket={bucket} />}
              cursor={{ stroke: colors.axis, strokeWidth: 1 }}
            />
            {AXES.map((k) => {
              const dim = emphasis && emphasis !== k
              const color = dim ? colors.axis : colors[k]
              return (
                <Line
                  key={k}
                  type="monotone"
                  dataKey={k}
                  stroke={color}
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  connectNulls
                  isAnimationActive={false}
                  dot={
                    bucket === 'day'
                      ? dailyDot(color, Boolean(dim), colors.surface)
                      : { r: 4, fill: color, stroke: colors.surface, strokeWidth: 2 }
                  }
                  activeDot={{ r: 5, stroke: colors.surface, strokeWidth: 2 }}
                  label={
                    dim
                      ? undefined
                      : endLabel(lastIndex, (v) => `${AXIS_LABELS[k]} ${fmtScore(v)}`, colors.inkSecondary)
                  }
                />
              )
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}
