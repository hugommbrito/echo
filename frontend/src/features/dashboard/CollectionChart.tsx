import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard, LegendRow, TooltipFrame } from './ChartCard'
import { gapRect } from './shapes'
import { fmtInt, MATURITY_LABELS } from './format'
import { languageMeta, sortByLanguage } from '@/lib/languages'
import type { Collection } from './types'
import { languageColor, type ChartColors } from './useChartColors'

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
  const byLevel = sortByLanguage(collection.by_level, (l) => l.language)
  const maxLevel = Math.max(1, ...byLevel.flatMap((l) => l.levels.map((x) => x.count)))
  const levels = byLevel[0]?.levels.map((x) => x.level) ?? ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
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
          {byLevel.length > 1 ? (
            <LegendRow
              shape="rect"
              items={byLevel.map((l) => ({
                key: l.language,
                label: languageMeta(l.language).label,
                color: languageColor(colors, l.language),
              }))}
            />
          ) : null}
          <ul className="grid grid-cols-6 gap-2">
            {levels.map((level) => (
              <li key={level} className="text-center">
                <div className="mx-auto flex h-10 items-end justify-center gap-0.5" aria-hidden>
                  {byLevel.map((l) => {
                    const count = l.levels.find((x) => x.level === level)?.count ?? 0
                    return (
                      <div key={l.language} className="flex h-full w-4 items-end rounded-sm bg-bg">
                        <div
                          className="w-full rounded-sm"
                          style={{
                            height: `${(count / maxLevel) * 100}%`,
                            background: languageColor(colors, l.language),
                          }}
                        />
                      </div>
                    )
                  })}
                </div>
                <p className="mt-1 text-fg">{level}</p>
                <p className="tabular-nums">
                  {byLevel
                    .map((l) => fmtInt(l.levels.find((x) => x.level === level)?.count ?? 0))
                    .join(' · ')}
                </p>
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
