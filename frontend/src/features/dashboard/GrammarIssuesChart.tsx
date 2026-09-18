import { useState } from 'react'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard, TooltipFrame } from './ChartCard'
import { gapRect, type LabelRenderProps } from './shapes'
import { Delta } from './KpiTiles'
import { fmtInt, ISSUE_TYPE_LABELS } from './format'
import type { GrammarIssues } from './types'
import type { ChartColors } from './useChartColors'

type Row = GrammarIssues['items'][number] & { name: string }

function IssueTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <TooltipFrame
      title={p.name}
      rows={[
        { label: 'ocorrências', value: fmtInt(p.count), color: 'var(--axis-grammar)' },
        { label: 'período anterior', value: fmtInt(p.previous_count), muted: true },
      ]}
    />
  )
}

export function GrammarIssuesChart({
  issues,
  colors,
  loading,
}: {
  issues: GrammarIssues
  colors: ChartColors
  loading?: boolean
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const rows: Row[] = issues.items
    .slice(0, 8)
    .map((i) => ({ ...i, name: ISSUE_TYPE_LABELS[i.type] ?? i.type }))
  const active = rows.find((r) => r.type === selected) ?? null
  const End = gapRect('horizontal', true)
  const height = Math.max(120, rows.length * 32 + 16)
  return (
    <ChartCard
      title="Erros de gramática mais frequentes"
      subtitle="Tipos apontados pela avaliação no período (clique numa barra para ver exemplos)"
      loading={loading}
      empty={issues.items.length === 0}
      emptyText="Nenhum erro registrado no período."
      table={{
        columns: ['Tipo', 'Ocorrências', 'Período anterior', 'Δ'],
        rows: issues.items.map((i) => [
          ISSUE_TYPE_LABELS[i.type] ?? i.type,
          i.count,
          i.previous_count,
          i.delta,
        ]),
      }}
      footer={
        <span>
          <strong className="text-fg">{fmtInt(issues.total)}</strong> erros apontados ·{' '}
          <Delta value={issues.total - issues.previous_total} upIsGood={false} /> vs período anterior
        </span>
      }
    >
      <div className="grid gap-3 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={rows}
              layout="vertical"
              margin={{ top: 0, right: 56, bottom: 0, left: 0 }}
              barSize={16}
              barCategoryGap={8}
            >
              <XAxis type="number" hide allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="name"
                width={130}
                tick={{ fill: colors.inkSecondary, fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<IssueTooltip />} cursor={{ fill: colors.band }} />
              <Bar
                dataKey="count"
                fill={colors.grammar}
                shape={End}
                isAnimationActive={false}
                onClick={(entry: { payload?: Row }) =>
                  setSelected((cur) =>
                    entry.payload && cur !== entry.payload.type ? entry.payload.type : null,
                  )
                }
                cursor="pointer"
                label={(raw: unknown) => {
                  const props = raw as LabelRenderProps
                  const row = props.index != null ? rows[props.index] : undefined
                  if (!row || props.x == null || props.y == null) return <g />
                  const x = Number(props.x) + Number(props.width ?? 0) + 6
                  const y = Number(props.y) + Number(props.height ?? 0) / 2
                  const sign =
                    row.delta > 0 ? `+${row.delta}` : row.delta < 0 ? `−${Math.abs(row.delta)}` : '='
                  return (
                    <text x={x} y={y} dy={4} fontSize={11} fill={colors.inkSecondary}>
                      {row.count} <tspan fill={colors.inkMuted}>({sign})</tspan>
                    </text>
                  )
                }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="rounded-xl bg-bg p-3 text-sm">
          {active ? (
            <>
              <p className="mb-2 font-medium text-fg">{active.name} · exemplos</p>
              <ul className="space-y-2">
                {active.examples.map((e, i) => (
                  <li key={i} className="leading-snug">
                    <span className="text-fg-muted line-through decoration-status-critical/60">
                      {e.quote}
                    </span>
                    <span className="mx-1 text-fg-muted">→</span>
                    <span className="text-fg">{e.correction}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-fg-muted">
              Clique num tipo de erro para ver exemplos{' '}
              <span className="whitespace-nowrap">trecho → correção</span>.
            </p>
          )}
        </div>
      </div>
    </ChartCard>
  )
}
