import { ChartCard } from './ChartCard'
import { Sparkline } from './Sparkline'
import { AXIS_LABELS, fmtInt, fmtScore } from './format'
import type { CategoryRow } from './types'
import type { ChartColors } from './useChartColors'

const AXES = ['structure', 'grammar', 'fluency'] as const

function MicroBar({ value, color }: { value: number | null; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded bg-bg" aria-hidden>
        {value != null ? (
          <div
            className="h-full rounded"
            style={{ width: `${((value - 1) / 4) * 100}%`, background: color }}
          />
        ) : null}
      </div>
      <span className="w-7 text-right tabular-nums text-fg">{fmtScore(value)}</span>
    </div>
  )
}

export function CategoryTable({
  rows,
  colors,
  loading,
}: {
  rows: CategoryRow[]
  colors: ChartColors
  loading?: boolean
}) {
  return (
    <ChartCard
      title="Por categoria"
      subtitle="Cards, respostas e média por eixo no período; tendência = média semanal"
      loading={loading}
      empty={rows.length === 0}
      emptyText="Nenhuma categoria com cards ainda."
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-fg-muted">
            <tr>
              <th className="py-2 pr-3 font-medium">Categoria</th>
              <th className="py-2 pr-3 text-right font-medium">Cards</th>
              <th className="py-2 pr-3 text-right font-medium">Respostas</th>
              {AXES.map((k) => (
                <th key={k} className="py-2 pr-3 font-medium">
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      aria-hidden
                      className="inline-block size-2 rounded-sm"
                      style={{ background: colors[k] }}
                    />
                    {AXIS_LABELS[k]}
                  </span>
                </th>
              ))}
              <th className="py-2 font-medium">Tendência</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.category.id} className="border-t border-border">
                <td className="py-2 pr-3 text-fg">
                  {r.category.name}
                  {r.category.scope === 'personal' ? (
                    <span className="ml-1.5 rounded bg-bg px-1 text-[10px] uppercase text-fg-muted">
                      pessoal
                    </span>
                  ) : null}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">{fmtInt(r.cards)}</td>
                <td className="py-2 pr-3 text-right tabular-nums">{fmtInt(r.attempts)}</td>
                {AXES.map((k) => (
                  <td key={k} className="py-2 pr-3">
                    <MicroBar value={r[`${k}_avg`]} color={colors[k]} />
                  </td>
                ))}
                <td className="py-2">
                  <Sparkline
                    values={r.trend.map((t) => t.composite_avg)}
                    color={colors.inkSecondary}
                    width={72}
                    height={22}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartCard>
  )
}
