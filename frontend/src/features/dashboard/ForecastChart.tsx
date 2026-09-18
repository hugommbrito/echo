import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle } from 'lucide-react'
import { ChartCard, LegendRow, TooltipFrame } from './ChartCard'
import { gapRect } from './shapes'
import { fmtDay, fmtInt } from './format'
import type { Forecast } from './types'
import type { ChartColors } from './useChartColors'

type Row = { date: string; due: number; overdue: number; cumulative: number }

function ForecastTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  const rows = [{ label: 'vencem', value: fmtInt(p.due), color: 'var(--maturity-mature)' }]
  if (p.overdue) rows.push({ label: 'atrasados', value: fmtInt(p.overdue), color: 'var(--status-critical)' })
  rows.push({ label: 'acumulado', value: fmtInt(p.cumulative), color: '' })
  return (
    <TooltipFrame
      title={fmtDay(p.date, 'EEE, d MMM')}
      rows={rows.map((r) => ({ ...r, color: r.color || undefined, muted: r.label === 'acumulado' }))}
    />
  )
}

export function ForecastChart({
  forecast,
  colors,
  loading,
}: {
  forecast: Forecast
  colors: ChartColors
  loading?: boolean
}) {
  const rows: Row[] = forecast.days.reduce<Row[]>((acc, d, i) => {
    const overdue = i === 0 ? forecast.overdue : 0
    const previous = acc.length ? acc[acc.length - 1].cumulative : 0
    acc.push({ date: d.date, due: d.due - overdue, overdue, cumulative: previous + d.due })
    return acc
  }, [])
  const Top = gapRect('vertical', true)
  const Mid = gapRect('vertical', false)
  return (
    <ChartCard
      title="Próximas revisões"
      subtitle={`Cards que vencem por dia, próximos ${forecast.days.length} dias`}
      loading={loading}
      empty={forecast.total === 0}
      emptyText="Nada agendado ainda — responda os primeiros cards."
      table={{
        columns: ['Dia', 'Vencem', 'Atrasados', 'Acumulado'],
        rows: rows.map((r) => [fmtDay(r.date, 'dd/MM/yyyy'), r.due, r.overdue || '', r.cumulative]),
      }}
      footer={
        <span className="inline-flex items-center gap-1">
          <strong className="text-fg">{fmtInt(forecast.total)}</strong> cards ·{' '}
          {forecast.overdue ? (
            <span className="inline-flex items-center gap-1 text-status-critical">
              <AlertTriangle className="size-3.5" aria-hidden /> {fmtInt(forecast.overdue)} atrasados
            </span>
          ) : (
            'nenhum atrasado'
          )}
        </span>
      }
    >
      {forecast.overdue ? (
        <LegendRow
          shape="rect"
          items={[
            { key: 'due', label: 'Vencem no dia', color: colors.mature },
            { key: 'overdue', label: 'Atrasados (hoje)', color: colors.bad },
          ]}
        />
      ) : null}
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
            barSize={forecast.days.length > 14 ? 10 : 20}
            barCategoryGap={2}
          >
            <CartesianGrid vertical={false} stroke={colors.grid} />
            <XAxis
              dataKey="date"
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
            <Tooltip content={<ForecastTooltip />} cursor={{ fill: colors.band }} />
            <Bar dataKey="overdue" stackId="a" fill={colors.bad} shape={Mid} isAnimationActive={false} />
            <Bar dataKey="due" stackId="a" fill={colors.mature} shape={Top} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}
