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
import { languageMeta, sortByLanguage } from '@/lib/languages'
import { ChartCard, LegendRow, TooltipFrame } from './ChartCard'
import { fmtDay, fmtInt, fmtSigned } from './format'
import { endLabel } from './shapes'
import type { LevelEvent, LevelSeries, LevelStats } from './types'
import { languageColor, type ChartColors } from './useChartColors'

/** One row per date; one rating column per language (`en`, `fr`, …). */
type Row = { date: string } & Record<string, number | string | undefined>

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

function LevelTooltip({
  active,
  payload,
  series,
  eventsByDate,
  colors,
}: {
  active?: boolean
  payload?: { payload: Row }[]
  series: LevelSeries[]
  eventsByDate: Map<string, (LevelEvent & { language: string })[]>
  colors: ChartColors
}) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  const rows = series
    .filter((s) => row[s.language] != null)
    .map((s) => ({
      label: series.length > 1 ? languageMeta(s.language).label.toLowerCase() : 'rating',
      value: fmtInt(Number(row[s.language])),
      color: series.length > 1 ? languageColor(colors, s.language) : undefined,
    }))
  for (const event of eventsByDate.get(row.date) ?? []) {
    rows.push({
      label: `sonda ${event.probe === 'above' ? 'acima' : 'abaixo'} · ${event.hit ? 'acertou' : 'errou'}${
        series.length > 1 ? ` · ${languageMeta(event.language).label.toLowerCase()}` : ''
      }`,
      value: fmtSigned(event.delta),
      color: undefined,
    })
  }
  return <TooltipFrame title={fmtDay(row.date, 'EEE, d MMM')} rows={rows} />
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
  const series = useMemo(() => sortByLanguage(stats.series, (s) => s.language), [stats])

  const data = useMemo<Row[]>(() => {
    const byDate = new Map<string, Row>()
    for (const s of series) {
      for (const p of s.points) {
        const row = byDate.get(p.date) ?? { date: p.date }
        row[s.language] = p.rating_after
        byDate.set(p.date, row)
      }
    }
    return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
  }, [series])

  const eventsByDate = useMemo(() => {
    const map = new Map<string, (LevelEvent & { language: string })[]>()
    for (const s of series) {
      for (const e of s.events) {
        const list = map.get(e.date) ?? []
        list.push({ ...e, language: s.language })
        map.set(e.date, list)
      }
    }
    return map
  }, [series])

  const ratings = series.flatMap((s) => [
    ...s.points.map((p) => p.rating_after),
    s.initial_rating,
    s.current.rating,
  ])
  const lo = ratings.length ? Math.min(...ratings) : 1000
  const hi = ratings.length ? Math.max(...ratings) : 1200
  const visibleBands = stats.bands.filter((b) => b.max >= lo - 100 && b.min <= hi + 100)
  const domain: [number, number] = [
    Math.max(600, Math.min(...visibleBands.map((b) => b.min))),
    Math.min(2200, Math.max(...visibleBands.map((b) => Math.min(b.max, 2200)))),
  ]
  const lastIndex = data.length - 1
  const multi = series.length > 1
  const single = series.length === 1 ? series[0] : null

  return (
    <ChartCard
      title="Evolução do nível"
      subtitle={`${single ? `${languageMeta(single.language).label} · ` : ''}rating ao fim de cada dia; faixas = níveis CEFR; ▲ sonda acertada · ▼ sonda errada`}
      loading={loading}
      empty={series.length === 0}
      emptyText="Nenhum idioma ativo."
      table={{
        columns: ['Dia', ...series.map((s) => languageMeta(s.language).label)],
        rows: data.map((row) => [
          fmtDay(row.date, 'dd/MM/yyyy'),
          ...series.map((s) => (row[s.language] == null ? '–' : Number(row[s.language]))),
        ]),
      }}
      footer={
        <div className="space-y-1">
          {series.map((s) => (
            <div key={s.language} className="flex flex-wrap items-center gap-x-4 gap-y-1">
              {multi ? (
                <span className="inline-flex items-center gap-1.5 font-medium text-fg">
                  <span
                    aria-hidden
                    className="inline-block size-2 rounded-full"
                    style={{ background: languageColor(colors, s.language) }}
                  />
                  {languageMeta(s.language).label}
                </span>
              ) : null}
              <span>
                sondas acima:{' '}
                <strong className="text-fg">
                  {s.probes.above.hits}/{s.probes.above.answered}
                </strong>{' '}
                acertos
              </span>
              <span>
                sondas abaixo:{' '}
                <strong className="text-fg">
                  {s.probes.below.hits}/{s.probes.below.answered}
                </strong>{' '}
                acertos
              </span>
              <span>
                início do período: <strong className="text-fg">{fmtInt(s.points[0]?.rating_after)}</strong> ·
                agora:{' '}
                <strong className="text-fg">
                  {fmtInt(s.current.rating)} · {s.current.band}
                </strong>
              </span>
            </div>
          ))}
        </div>
      }
    >
      {multi ? (
        <LegendRow
          shape="line"
          items={series.map((s) => ({
            key: s.language,
            label: languageMeta(s.language).label,
            color: languageColor(colors, s.language),
          }))}
        />
      ) : null}
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 56, bottom: 0, left: 0 }}>
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
            <Tooltip
              content={<LevelTooltip series={series} eventsByDate={eventsByDate} colors={colors} />}
              cursor={{ stroke: colors.axis, strokeWidth: 1 }}
            />
            {series.map((s) => {
              const color = languageColor(colors, s.language)
              const short = languageMeta(s.language).short
              return (
                <Line
                  key={s.language}
                  type="monotone"
                  dataKey={s.language}
                  stroke={color}
                  strokeWidth={2}
                  connectNulls
                  dot={{ r: 3, fill: color, stroke: colors.surface, strokeWidth: 2 }}
                  activeDot={{ r: 5, stroke: colors.surface, strokeWidth: 2 }}
                  isAnimationActive={false}
                  label={
                    multi
                      ? endLabel(lastIndex, (value) => `${short} ${fmtInt(value)}`, colors.ink)
                      : undefined
                  }
                />
              )
            })}
            {series.flatMap((s) =>
              s.events.map((e) => (
                <ReferenceDot
                  key={`${s.language}-${e.date}-${e.rating_after}-${e.delta}`}
                  x={e.date}
                  y={e.rating_after}
                  r={8}
                  shape={(props: { cx?: number; cy?: number }) => (
                    <ProbeMarker cx={props.cx} cy={props.cy} hit={e.hit} colors={colors} />
                  )}
                  ifOverflow="extendDomain"
                  zIndex={1000}
                />
              )),
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}
