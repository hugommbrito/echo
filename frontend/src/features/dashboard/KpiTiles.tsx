import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { ReactNode } from 'react'
import { languageMeta, sortByLanguage } from '@/lib/languages'
import { Sparkline } from './Sparkline'
import { fmtInt, fmtScore, fmtSigned, MATURITY_LABELS } from './format'
import type { Forecast, LevelOverview, Overview } from './types'
import { languageColor, type ChartColors } from './useChartColors'

function Tile({
  label,
  value,
  sub,
  children,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="flex min-w-0 flex-col rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">{label}</p>
      <p className="mt-1 text-3xl font-semibold leading-none text-fg">{value}</p>
      {sub ? <div className="mt-1.5 text-sm text-fg-muted">{sub}</div> : null}
      {children ? <div className="mt-3">{children}</div> : null}
    </div>
  )
}

export function Delta({
  value,
  decimals = 0,
  upIsGood = true,
  suffix = '',
}: {
  value: number | null | undefined
  decimals?: number
  upIsGood?: boolean
  suffix?: string
}) {
  if (value == null) return <span className="text-fg-muted">–</span>
  const good = value === 0 ? null : value > 0 === upIsGood
  const Icon = value === 0 ? Minus : value > 0 ? ArrowUpRight : ArrowDownRight
  const cls = good == null ? 'text-fg-muted' : good ? 'text-status-good' : 'text-status-critical'
  return (
    <span className={`inline-flex items-center gap-0.5 font-medium ${cls}`}>
      <Icon className="size-3.5" aria-hidden />
      {fmtSigned(value, decimals)}
      {suffix}
    </span>
  )
}

export function KpiTiles({
  overview,
  forecast,
  colors,
}: {
  overview: Overview
  forecast?: Forecast
  colors: ChartColors
}) {
  const { today, due, collection, scores } = overview
  const levels = sortByLanguage(overview.levels, (l) => l.language)
  const sparkValues = forecast ? forecast.days.slice(0, 7).map((d) => d.due) : []
  const total = collection.total || 1
  const composite = scores.period.composite_avg
  const prevComposite = scores.previous_period.composite_avg
  const compositeDelta =
    composite != null && prevComposite != null ? Math.round((composite - prevComposite) * 10) / 10 : null

  return (
    <section aria-label="Resumo" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      <Tile
        label="Hoje"
        value={
          <>
            {fmtInt(today.answered)}{' '}
            <span className="text-lg font-normal text-fg-muted">
              / {fmtInt(today.target + due.today + today.due_answered)}
            </span>
          </>
        }
        sub={`${fmtInt(today.new_answered)} novos · ${fmtInt(today.due_answered)} rev.`}
      />
      {levels.length === 1 ? (
        <Tile
          label="Nível"
          value={
            <>
              {levels[0].band}{' '}
              <span className="text-lg font-normal text-fg-muted">· {fmtInt(levels[0].rating)}</span>
            </>
          }
          sub={<LevelSub level={levels[0]} />}
        />
      ) : (
        <div className="flex min-w-0 flex-col rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">Nível</p>
          {levels.length === 0 ? (
            <p className="mt-1 text-sm text-fg-muted">Nenhum idioma ativo</p>
          ) : (
            <ul className="mt-1 space-y-1.5">
              {levels.map((level) => (
                <li key={level.language}>
                  <p className="flex items-center gap-1.5 text-xl font-semibold leading-none text-fg">
                    <span
                      aria-hidden
                      className="inline-block size-2 rounded-full"
                      style={{ background: languageColor(colors, level.language) }}
                    />
                    <span className="sr-only">{languageMeta(level.language).label}</span>
                    {level.band}{' '}
                    <span className="text-base font-normal text-fg-muted">· {fmtInt(level.rating)}</span>
                  </p>
                  <div className="mt-0.5 text-xs text-fg-muted">
                    <LevelSub level={level} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <Tile
        label="Vencem em 7 dias"
        value={fmtInt(due.today + due.next_7_days)}
        sub={due.overdue ? `${fmtInt(due.overdue)} atrasados` : 'nenhum atrasado'}
      >
        {sparkValues.length ? <Sparkline values={sparkValues} color={colors.mature} width={120} /> : null}
      </Tile>
      <Tile
        label="Coleção"
        value={fmtInt(collection.total)}
        sub={`${fmtInt(collection.new)} novos · ${fmtInt(collection.learning)} aprendendo · ${fmtInt(collection.mature)} maduros`}
      >
        <div
          className="flex h-2 w-full gap-0.5 overflow-hidden rounded"
          role="img"
          aria-label={`Novos ${collection.new}, aprendendo ${collection.learning}, maduros ${collection.mature}`}
        >
          {(['new', 'learning', 'mature'] as const).map((key) => (
            <span
              key={key}
              title={`${MATURITY_LABELS[key]}: ${collection[key]}`}
              style={{ width: `${(collection[key] / total) * 100}%`, background: colors[key] }}
            />
          ))}
        </div>
      </Tile>
      <Tile
        label="Nota média"
        value={fmtScore(composite)}
        sub={
          <span className="inline-flex items-center gap-2">
            <Delta value={compositeDelta} decimals={1} />
            <span>vs período ant.</span>
          </span>
        }
      />
    </section>
  )
}

function LevelSub({ level }: { level: LevelOverview }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <Delta value={level.delta_period} />
      {level.next_band ? (
        <span>
          {fmtInt(level.next_band.points_needed)} pts p/ {level.next_band.label}
        </span>
      ) : (
        <span>banda máxima</span>
      )}
      {level.provisional ? <span className="rounded bg-bg px-1.5 py-0.5 text-xs">provisório</span> : null}
    </span>
  )
}
