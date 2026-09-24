import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { TooltipFrame } from './ChartCard'
import { gapRect } from './shapes'
import { fmtInt, fmtSeconds } from './format'
import { useAdvanced, type StatsFilters } from './api'
import { Sparkline } from './Sparkline'
import type { ChartColors } from './useChartColors'

function CountTooltip({
  active,
  payload,
  xKey,
}: {
  active?: boolean
  payload?: { payload: Record<string, string | number> }[]
  xKey: string
}) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <TooltipFrame title={String(row[xKey])} rows={[{ label: 'cards', value: fmtInt(Number(row.count)) }]} />
  )
}

function SmallBars({
  data,
  xKey,
  colors,
  title,
}: {
  data: Record<string, string | number>[]
  xKey: string
  colors: ChartColors
  title: string
}) {
  const Top = gapRect('vertical', true)
  return (
    <div>
      <p className="mb-1 text-sm font-medium text-fg">{title}</p>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
            barSize={20}
            barCategoryGap={4}
          >
            <XAxis
              dataKey={xKey}
              tick={{ fill: colors.inkMuted, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: colors.axis }}
            />
            <YAxis
              allowDecimals={false}
              width={22}
              tick={{ fill: colors.inkMuted, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<CountTooltip xKey={xKey} />} cursor={{ fill: colors.band }} />
            <Bar dataKey="count" fill={colors.mature} shape={Top} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function AdvancedSection({ colors, filters }: { colors: ChartColors; filters: StatsFilters }) {
  const [open, setOpen] = useState(false)
  const { data } = useAdvanced(open, filters)
  const thinking = data?.thinking_time ?? null
  return (
    <section className="rounded-2xl border border-border bg-surface shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <span>
          <span className="block text-base font-semibold text-fg">Avançado</span>
          <span className="block text-sm text-fg-muted">
            Facilidade (ease), intervalos, duração das respostas e tempo para começar
          </span>
        </span>
        <ChevronDown
          className={`size-5 text-fg-muted transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden
        />
      </button>
      {open ? (
        <div className="grid gap-6 border-t border-border p-5 md:grid-cols-2 xl:grid-cols-4">
          {data ? (
            <>
              <SmallBars title="Distribuição de facilidade" data={data.ease} xKey="ease" colors={colors} />
              <SmallBars title="Intervalos (dias)" data={data.intervals} xKey="range" colors={colors} />
              <div>
                <p className="mb-1 text-sm font-medium text-fg">Duração das respostas</p>
                <dl className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-fg-muted">média</dt>
                    <dd className="text-2xl font-semibold text-fg">
                      {fmtSeconds(data.answer_duration.avg_seconds)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-fg-muted">respostas</dt>
                    <dd className="text-2xl font-semibold text-fg">
                      {fmtInt(data.answer_duration.attempts)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-fg-muted">mínima</dt>
                    <dd className="text-fg">{fmtSeconds(data.answer_duration.min_seconds)}</dd>
                  </div>
                  <div>
                    <dt className="text-fg-muted">máxima</dt>
                    <dd className="text-fg">{fmtSeconds(data.answer_duration.max_seconds)}</dd>
                  </div>
                </dl>
              </div>
              <div>
                <p className="mb-1 text-sm font-medium text-fg">Tempo para começar</p>
                {thinking && thinking.attempts > 0 ? (
                  <>
                    <dl className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <dt className="text-fg-muted">mediana</dt>
                        <dd className="text-2xl font-semibold text-fg">
                          {fmtSeconds(thinking.median_seconds, 1)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-fg-muted">respostas</dt>
                        <dd className="text-2xl font-semibold text-fg">{fmtInt(thinking.attempts)}</dd>
                      </div>
                      <div>
                        <dt className="text-fg-muted">média</dt>
                        <dd className="text-fg">{fmtSeconds(thinking.avg_seconds, 1)}</dd>
                      </div>
                    </dl>
                    {thinking.series.length >= 2 ? (
                      <div className="mt-3">
                        <Sparkline
                          values={thinking.series.map((s) => s.median_seconds)}
                          color={colors.mature}
                          width={160}
                          height={32}
                        />
                        <p className="text-xs text-fg-muted">mediana por dia, no período</p>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <p className="text-sm text-fg-muted">Ainda sem dados.</p>
                )}
              </div>
            </>
          ) : (
            <p className="text-sm text-fg-muted">Carregando…</p>
          )}
        </div>
      ) : null}
    </section>
  )
}
