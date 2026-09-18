import { useMemo } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ChartCard, TooltipFrame } from './ChartCard'
import { fmtDay, fmtInt, fmtSigned } from './format'
import type { LevelStats } from './types'
import type { ChartColors } from './useChartColors'

type Point = { date: string; rating: number; delta?: number; probe?: 'above' | 'below'; hit?: boolean }

function ProbeMarker({
  cx,
  cy,
  hit,
  colors,
}: {
  cx?: number
  cy?: number
  hit: boolean
  colors: ChartColors
}) {
  if (cx == null || cy == null) return <g />
  // Offset the marker away from the line's own dot: hits point up above it, misses point down below.
  const color = hit ? colors.good : colors.bad
  const y = hit ? cy - 13 : cy + 13
  const points = hit
    ? `${cx},${y - 7} ${cx - 7},${y + 5} ${cx + 7},${y + 5}`
    : `${cx},${y + 7} ${cx - 7},${y - 5} ${cx + 7},${y - 5}`
  return (
    <g>
      <polygon points={points} fill={color} stroke={colors.surface} strokeWidth={2} />
    </g>
  )
}

function LevelTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  const rows = [{ label: 'rating', value: fmtInt(p.rating) }]
  if (p.probe)
    rows.push({
      label: `sonda ${p.probe === 'above' ? 'acima' : 'abaixo'} · ${p.hit ? 'acertou' : 'errou'}`,
      value: fmtSigned(p.delta),
    })
  return <TooltipFrame title={fmtDay(p.date, 'EEE, d MMM')} rows={rows} />
}

export function LevelTrend({
  stats,
  colors,
  loading,
}: {
  stats: LevelStats
  colors: ChartColors
  loading?: boolean
}) {
  const data = useMemo<Point[]>(
    () => stats.points.map((p) => ({ date: p.date, rating: p.rating_after })),
    [stats],
  )
  const ratings = data.map((d) => d.rating)
  const lo = Math.min(...ratings, stats.initial_rating)
  const hi = Math.max(...ratings, stats.current.rating)
  const visibleBands = stats.bands.filter((b) => b.max >= lo - 100 && b.min <= hi + 100)
  const domain: [number, number] = [
    Math.max(600, Math.min(...visibleBands.map((b) => b.min))),
    Math.min(2200, Math.max(...visibleBands.map((b) => Math.min(b.max, 2200)))),
  ]
  const events = stats.events.map((e) => ({ ...e, key: `${e.date}-${e.rating_after}-${e.delta}` }))
  const above = stats.probes.above
  const below = stats.probes.below

  return (
    <ChartCard
      title="Evolução do nível"
      subtitle="Rating ao fim de cada dia; faixas = níveis CEFR; ▲ sonda acertada · ▼ sonda errada"
      loading={loading}
      table={{
        columns: ['Dia', 'Rating'],
        rows: stats.points.map((p) => [fmtDay(p.date, 'dd/MM/yyyy'), p.rating_after]),
      }}
      footer={
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <span>
            sondas acima:{' '}
            <strong className="text-fg">
              {above.hits}/{above.answered}
            </strong>{' '}
            acertos
          </span>
          <span>
            sondas abaixo:{' '}
            <strong className="text-fg">
              {below.hits}/{below.answered}
            </strong>{' '}
            acertos
          </span>
          <span>
            início do período: <strong className="text-fg">{fmtInt(stats.points[0]?.rating_after)}</strong> ·
            agora:{' '}
            <strong className="text-fg">
              {fmtInt(stats.current.rating)} · {stats.current.band}
            </strong>
          </span>
        </div>
      }
    >
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 36, bottom: 0, left: 0 }}>
            {visibleBands.map((b, i) => (
              <ReferenceArea
                key={b.label}
                y1={Math.max(b.min, domain[0])}
                y2={Math.min(b.max, domain[1])}
                fill={i % 2 ? colors.bandAlt : colors.band}
                fillOpacity={1}
                ifOverflow="hidden"
                label={{ value: b.label, position: 'insideTopRight', fill: colors.inkMuted, fontSize: 11 }}
              />
            ))}
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
              domain={domain}
              width={44}
              tick={{ fill: colors.inkMuted, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => fmtInt(v)}
            />
            <Tooltip content={<LevelTooltip />} cursor={{ stroke: colors.axis, strokeWidth: 1 }} />
            <Line
              type="monotone"
              dataKey="rating"
              stroke={colors.ink}
              strokeWidth={2}
              dot={{ r: 3, fill: colors.ink, stroke: colors.surface, strokeWidth: 2 }}
              activeDot={{ r: 5, stroke: colors.surface, strokeWidth: 2 }}
              isAnimationActive={false}
            />
            {events.map((e) => (
              <ReferenceDot
                key={e.key}
                x={e.date}
                y={e.rating_after}
                r={8}
                shape={(props: { cx?: number; cy?: number }) => (
                  <ProbeMarker cx={props.cx} cy={props.cy} hit={e.hit} colors={colors} />
                )}
                ifOverflow="extendDomain"
                zIndex={1000}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}
