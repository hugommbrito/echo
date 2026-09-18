import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard, LegendRow, TooltipFrame } from './ChartCard'
import { gapRect } from './shapes'
import { fmtInt, MATURITY_LABELS } from './format'
import type { Collection } from './types'
import type { ChartColors } from './useChartColors'

const KEYS = ['new', 'learning', 'mature'] as const
type Row = Collection['by_category'][number] & { name: string }

function CollectionTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <TooltipFrame
      title={p.category.name}
      rows={[
        { label: 'cards', value: fmtInt(p.total) },
        ...KEYS.map((k) => ({
          label: MATURITY_LABELS[k].toLowerCase(),
          value: fmtInt(p[k]),
          color: `var(--maturity-${k})`,
        })),
      ]}
    />
  )
}

export function CollectionChart({
  collection,
  colors,
  loading,
}: {
  collection: Collection
  colors: ChartColors
  loading?: boolean
}) {
  const rows: Row[] = collection.by_category.map((c) => ({ ...c, name: c.category.name }))
  const maxLevel = Math.max(1, ...collection.by_level.map((l) => l.count))
  const End = gapRect('horizontal', true)
  const Mid = gapRect('horizontal', false)
  const height = Math.max(120, rows.length * 34 + 16)
  return (
    <ChartCard
      title="Coleção"
      subtitle="Cards ativos por categoria e maturidade"
      loading={loading}
      empty={
        collection.by_maturity.new + collection.by_maturity.learning + collection.by_maturity.mature === 0
      }
      emptyText="Ainda não há cards."
      table={{
        columns: ['Categoria', 'Novos', 'Aprendendo', 'Maduros', 'Total'],
        rows: rows.map((r) => [r.name, r.new, r.learning, r.mature, r.total]),
      }}
      footer={
        <div>
          <p className="mb-1.5">Por nível CEFR</p>
          <ul className="grid grid-cols-6 gap-2">
            {collection.by_level.map((l) => (
              <li key={l.level} className="text-center">
                <div className="mx-auto flex h-10 w-4 items-end rounded-sm bg-bg" aria-hidden>
                  <div
                    className="w-full rounded-sm"
                    style={{ height: `${(l.count / maxLevel) * 100}%`, background: colors.mature }}
                  />
                </div>
                <p className="mt-1 text-fg">{l.level}</p>
                <p className="tabular-nums">{fmtInt(l.count)}</p>
              </li>
            ))}
          </ul>
        </div>
      }
    >
      <LegendRow
        shape="rect"
        items={KEYS.map((k) => ({ key: k, label: MATURITY_LABELS[k], color: colors[k] }))}
      />
      <div className="w-full" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 0, right: 32, bottom: 0, left: 0 }}
            barSize={18}
            barCategoryGap={8}
          >
            <XAxis type="number" hide allowDecimals={false} />
            <YAxis
              type="category"
              dataKey="name"
              width={120}
              tick={{ fill: colors.inkSecondary, fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<CollectionTooltip />} cursor={{ fill: colors.band }} />
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
              shape={End}
              isAnimationActive={false}
              label={{ dataKey: 'total', position: 'right', fill: colors.inkSecondary, fontSize: 11 }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}
