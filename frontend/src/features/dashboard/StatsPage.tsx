import { useMemo, useState } from 'react'
import { Check } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { useMe } from '@/api/auth'
import { LanguageTag } from '@/components/ui/LanguageTag'
import { isLanguageCode, sortByLanguage } from '@/lib/languages'
import { ActivityChart } from './ActivityChart'
import { AdvancedSection } from './AdvancedSection'
import { CategoryTable } from './CategoryTable'
import { CollectionChart } from './CollectionChart'
import { ForecastChart } from './ForecastChart'
import { GrammarIssuesChart } from './GrammarIssuesChart'
import { KpiTiles } from './KpiTiles'
import { LevelTrend } from './LevelTrend'
import { ScoreTrend } from './ScoreTrend'
import {
  useActivity,
  useCategoryOptions,
  useCategoryStats,
  useCollection,
  useForecast,
  useGrammarIssues,
  useHeatmap,
  useLevel,
  useOverview,
  useScores,
  type StatsFilters,
} from './api'
import { useChartColors } from './useChartColors'
import type { PeriodPreset } from './types'

const PRESETS: { key: PeriodPreset; label: string; days: number | null }[] = [
  { key: '7d', label: '7 dias', days: 7 },
  { key: '30d', label: '30 dias', days: 30 },
  { key: '90d', label: '90 dias', days: 90 },
  { key: '1y', label: '1 ano', days: 365 },
  { key: 'all', label: 'Tudo', days: null },
]

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

export function StatsPage() {
  const [preset, setPreset] = useState<PeriodPreset>('30d')
  const [category, setCategory] = useState<string | null>(null)
  const [params, setParams] = useSearchParams()
  const me = useMe()
  const profiles = useMemo(() => sortByLanguage(me.data?.languages ?? [], (p) => p.code), [me.data])
  const requested = params.get('language')
  const language =
    requested && isLanguageCode(requested) && profiles.some((p) => p.code === requested) ? requested : null
  const setLanguage = (code: string | null) => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (code) next.set('language', code)
        else next.delete('language')
        return next
      },
      { replace: true },
    )
  }
  const colors = useChartColors()

  const filters = useMemo<StatsFilters>(() => {
    const days = PRESETS.find((p) => p.key === preset)?.days ?? null
    return { from: isoDaysAgo(days == null ? 3650 : days - 1), to: todayIso(), category, language }
  }, [preset, category, language])
  const bucket: 'day' | 'week' = preset === '7d' || preset === '30d' ? 'day' : 'week'
  const year = Number(filters.to.slice(0, 4))

  const overview = useOverview(filters)
  const scores = useScores(filters, bucket)
  const level = useLevel(filters)
  const activity = useActivity(filters, bucket)
  const forecast = useForecast(30, language)
  const collection = useCollection(language)
  const grammar = useGrammarIssues(filters)
  const categories = useCategoryStats(filters)
  const heatmap = useHeatmap(year, category, language)
  const options = useCategoryOptions()

  const anyError = [overview, scores, level, activity, forecast, collection, grammar, categories].find(
    (q) => q.isError,
  )

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 pb-12 pt-4 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">Estatísticas</h1>
          <p className="text-sm text-fg-muted">
            O que o Anki não mostra: como as notas e o nível evoluem com o tempo.
          </p>
        </div>
      </header>

      {/* One filter row scopes everything below it. */}
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filtros">
        <div
          className="flex flex-wrap rounded-lg border border-border bg-surface p-0.5 text-sm"
          role="radiogroup"
          aria-label="Período"
        >
          {PRESETS.map((p) => (
            <button
              key={p.key}
              type="button"
              role="radio"
              aria-checked={preset === p.key}
              onClick={() => setPreset(p.key)}
              className={`inline-flex items-center gap-1 rounded-md px-3 py-1.5 ${preset === p.key ? 'bg-bg font-semibold text-fg' : 'text-fg-muted hover:text-fg'}`}
            >
              {preset === p.key ? <Check className="size-4" strokeWidth={3} aria-hidden /> : null}
              {p.label}
            </button>
          ))}
        </div>
        {profiles.length > 1 ? (
          <div
            className="flex flex-wrap rounded-lg border border-border bg-surface p-0.5 text-sm"
            role="radiogroup"
            aria-label="Idioma"
          >
            {[null, ...profiles.map((p) => p.code)].map((code) => {
              const checked = language === code
              return (
                <button
                  key={code ?? 'all'}
                  type="button"
                  role="radio"
                  aria-checked={checked}
                  onClick={() => setLanguage(code)}
                  className={`inline-flex items-center gap-1 rounded-md px-3 py-1.5 ${checked ? 'bg-bg font-semibold text-fg' : 'text-fg-muted hover:text-fg'}`}
                >
                  {checked ? <Check className="size-4" strokeWidth={3} aria-hidden /> : null}
                  {code ? <LanguageTag code={code} full bare /> : 'Todos'}
                </button>
              )
            })}
          </div>
        ) : null}
        <label className="inline-flex items-center gap-2 text-sm text-fg-muted">
          <span>Categoria</span>
          <select
            value={category ?? ''}
            onChange={(e) => setCategory(e.target.value || null)}
            className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm text-fg focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <option value="">todas</option>
            {(options.data ?? []).map((c) => (
              <option key={c.id} value={c.slug}>
                {c.name}
                {c.scope === 'personal' ? ' (pessoal)' : ''}
              </option>
            ))}
          </select>
        </label>
      </div>

      {anyError ? (
        <p
          role="alert"
          className="rounded-xl border border-status-critical/40 bg-surface p-3 text-sm text-status-critical"
        >
          Não foi possível carregar parte das estatísticas: {(anyError.error as Error).message}
        </p>
      ) : null}

      {overview.data ? (
        <KpiTiles overview={overview.data} forecast={forecast.data} colors={colors} />
      ) : (
        <div className="h-28 animate-pulse rounded-2xl bg-surface" aria-hidden />
      )}

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="xl:col-span-7">
          <ScoreTrend
            buckets={scores.data ?? []}
            bucket={bucket}
            from={filters.from}
            to={filters.to}
            summary={
              overview.data?.scores.period ?? {
                structure_avg: null,
                grammar_avg: null,
                fluency_avg: null,
                composite_avg: null,
                attempts: 0,
              }
            }
            previous={
              overview.data?.scores.previous_period ?? {
                structure_avg: null,
                grammar_avg: null,
                fluency_avg: null,
                composite_avg: null,
                attempts: 0,
              }
            }
            colors={colors}
            loading={scores.isFetching}
          />
        </div>
        <div className="xl:col-span-5">
          {level.data ? (
            <LevelTrend stats={level.data} colors={colors} loading={level.isFetching} />
          ) : (
            <div className="h-72 animate-pulse rounded-2xl bg-surface" aria-hidden />
          )}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="xl:col-span-7">
          <ActivityChart
            buckets={activity.data ?? []}
            bucket={bucket}
            heatmap={heatmap.data}
            year={year}
            colors={colors}
            loading={activity.isFetching || heatmap.isFetching}
          />
        </div>
        <div className="xl:col-span-5">
          {forecast.data ? (
            <ForecastChart forecast={forecast.data} colors={colors} loading={forecast.isFetching} />
          ) : (
            <div className="h-72 animate-pulse rounded-2xl bg-surface" aria-hidden />
          )}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="xl:col-span-5">
          {collection.data ? (
            <CollectionChart collection={collection.data} colors={colors} loading={collection.isFetching} />
          ) : (
            <div className="h-72 animate-pulse rounded-2xl bg-surface" aria-hidden />
          )}
        </div>
        <div className="xl:col-span-7">
          {grammar.data ? (
            <GrammarIssuesChart issues={grammar.data} colors={colors} loading={grammar.isFetching} />
          ) : (
            <div className="h-72 animate-pulse rounded-2xl bg-surface" aria-hidden />
          )}
        </div>
      </div>

      <CategoryTable rows={categories.data ?? []} colors={colors} loading={categories.isFetching} />

      <AdvancedSection colors={colors} filters={filters} />
    </div>
  )
}
