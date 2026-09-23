import { ArrowRight, Check, Minus, Plus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useMe } from '@/api/auth'
import { useCategories } from '@/api/categories'
import { isApiError } from '@/api/client'
import { useCreateSession, useProjection, useTodaySession } from '@/api/sessions'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { LanguageTag } from '@/components/ui/LanguageTag'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/lib/cn'
import { formatNumber, formatWeekdayDate } from '@/lib/format'
import { SESSION_STATUS_LABELS } from '@/lib/labels'
import { activeLanguages, languageMeta } from '@/lib/languages'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import type { Category, LanguageProfile, LanguageTargets, Projection, Session, User } from '@/types/api'

const MAX_NEW_CARDS = 20

export function TodayPage() {
  const me = useMe()
  const today = useTodaySession()

  if (me.isPending || today.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  if (today.isError || !me.data) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Não foi possível carregar o dia de hoje</AlertTitle>
        <AlertDescription>
          {today.error instanceof Error ? today.error.message : 'Erro desconhecido.'}
        </AlertDescription>
        <Button variant="outline" size="sm" className="mt-2" onClick={() => void today.refetch()}>
          Tentar de novo
        </Button>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-sm first-letter:uppercase text-fg-muted">{formatWeekdayDate(new Date())}</p>
        <h1 className="text-display text-3xl sm:text-4xl">Hoje</h1>
      </header>
      {today.data ? <SessionSummary session={today.data} /> : <DaySetup me={me.data} />}
    </div>
  )
}

// ---------------------------------------------------------------------------

function SessionSummary({ session }: { session: Session }) {
  const { progress } = session
  const total = progress.new_total + progress.due_total
  const done = progress.new_done + progress.due_done
  const completed = session.status === 'completed'
  const pct = total > 0 ? (done / total) * 100 : 0

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Sessão de {formatWeekdayDate(session.session_date)}</CardTitle>
          <Badge variant={completed ? 'success' : session.status === 'failed' ? 'danger' : 'default'}>
            {SESSION_STATUS_LABELS[session.status]}
          </Badge>
        </div>
        <CardDescription>
          {session.categories.length > 0
            ? session.categories.map((c) => c.name).join(' · ')
            : 'Todas as categorias ativas'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-end gap-6">
          <div>
            <p className="text-display text-5xl tabular">
              {done}
              <span className="text-2xl text-fg-muted">/{total}</span>
            </p>
            <p className="mt-1 text-sm text-fg-muted">cards feitos</p>
          </div>
          <p className="pb-1 text-sm text-fg-muted tabular">
            Novos {progress.new_done}/{progress.new_total} · Revisões {progress.due_done}/{progress.due_total}
          </p>
        </div>
        <Progress value={pct} label="Progresso da sessão" />
        {session.plans.length > 1 ? (
          <ul
            className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-fg-muted tabular"
            aria-label="Por idioma"
          >
            {session.plans.map((plan) => (
              <li key={plan.language} className="inline-flex items-center gap-1.5">
                <LanguageTag code={plan.language} full bare />
                {plan.progress.new_done + plan.progress.due_done}/
                {plan.progress.new_total + plan.progress.due_total}
              </li>
            ))}
          </ul>
        ) : null}
        {session.status === 'failed' && session.generation_error ? (
          <Alert variant="destructive">
            <AlertDescription>{session.generation_error}</AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
      <CardFooter>
        <Button asChild size="lg">
          <Link to={`/session/${session.id}`}>
            {completed ? 'Ver resumo' : 'Continuar'} <ArrowRight />
          </Link>
        </Button>
      </CardFooter>
    </Card>
  )
}

// ---------------------------------------------------------------------------

function DaySetup({ me }: { me: User }) {
  const navigate = useNavigate()
  const categories = useCategories({ active: true })
  const createSession = useCreateSession()
  const languages = useMemo(() => activeLanguages(me), [me])

  // `null` = untouched → every active category is selected by default.
  const [touched, setTouched] = useState<Set<string> | null>(null)
  const [targets, setTargets] = useState<LanguageTargets>(() =>
    Object.fromEntries(languages.map((l) => [l.code, clampTarget(l.default_new_cards_per_day)])),
  )
  const totalTarget = Object.values(targets).reduce((sum, n) => sum + (n ?? 0), 0)

  const allIds = useMemo(() => categories.data?.map((c) => c.id) ?? [], [categories.data])
  const selected = useMemo(() => touched ?? new Set(allIds), [touched, allIds])
  const selectedIds = useMemo(() => [...selected].sort(), [selected])
  const debounced = useDebouncedValue({ targets, category_ids: selectedIds }, 350)
  const projection = useProjection(debounced, categories.data !== undefined && languages.length > 0)

  const setTarget = (code: string, value: number) =>
    setTargets((prev) => ({ ...prev, [code]: clampTarget(value) }))

  const toggle = (id: string) => {
    setTouched((prev) => {
      const next = new Set(prev ?? allIds)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const start = () => {
    createSession.mutate(
      { category_ids: selectedIds, new_cards_targets: targets },
      {
        onSuccess: (session) => navigate(`/session/${session.id}`),
        onError: (error) => {
          if (isApiError(error) && error.status === 409 && typeof error.body.session_id === 'string') {
            navigate(`/session/${error.body.session_id}`)
          }
        },
      },
    )
  }

  const createError =
    createSession.isError && !(isApiError(createSession.error) && createSession.error.status === 409)
      ? createSession.error
      : null

  if (languages.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Nenhum idioma ativo</CardTitle>
          <CardDescription>
            Ative inglês ou francês em Configurações › Idiomas para montar a sessão de hoje.
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <Button asChild>
            <Link to="/settings?tab=languages">
              Ativar idioma <ArrowRight />
            </Link>
          </Button>
        </CardFooter>
      </Card>
    )
  }

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_320px]">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Categorias</CardTitle>
            <CardDescription>
              Escolha sobre o que quer falar hoje. Sem seleção, valem todas as ativas.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {categories.isPending ? (
              <div className="flex flex-wrap gap-2">
                {Array.from({ length: 6 }, (_, i) => (
                  <Skeleton key={i} className="h-9 w-28 rounded-full" />
                ))}
              </div>
            ) : categories.isError ? (
              <Alert variant="destructive">
                <AlertDescription>Não foi possível carregar as categorias.</AlertDescription>
              </Alert>
            ) : (
              <CategoryChips categories={categories.data} selected={selected} onToggle={toggle} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{languages.length > 1 ? 'Perguntas novas por idioma' : 'Perguntas novas'}</CardTitle>
            <CardDescription>
              Quantas perguntas inéditas você quer receber hoje (0–{MAX_NEW_CARDS}). Coloque 0 para só
              revisar.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {languages.map((profile) => (
              <TargetStepper
                key={profile.code}
                profile={profile}
                value={targets[profile.code] ?? 0}
                onChange={(value) => setTarget(profile.code, value)}
              />
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="md:sticky md:top-20 md:self-start">
        <ProjectionPanel
          projection={projection.data}
          loading={projection.isPending || projection.isFetching}
          error={projection.isError}
        />
        <Button
          className="mt-4 w-full"
          size="lg"
          onClick={start}
          loading={createSession.isPending}
          disabled={totalTarget > 0 && selectedIds.length === 0}
        >
          Começar <ArrowRight />
        </Button>
        {totalTarget > 0 && selectedIds.length === 0 ? (
          <p className="mt-2 text-sm text-fg-muted">
            Escolha ao menos uma categoria para gerar perguntas novas (ou deixe todos os idiomas em 0 para só
            revisar).
          </p>
        ) : projection.data && projection.data.total === 0 ? (
          <p className="mt-2 text-sm text-fg-muted">Nada para hoje: sem perguntas novas nem revisões.</p>
        ) : null}
        {createError ? (
          <Alert variant="destructive" className="mt-3">
            <AlertDescription>
              {isApiError(createError)
                ? (createError.fieldError('new_cards_targets') ??
                  createError.fieldError('category_ids') ??
                  createError.detail)
                : 'Não foi possível criar a sessão.'}
            </AlertDescription>
          </Alert>
        ) : null}
      </div>
    </div>
  )
}

function clampTarget(n: number): number {
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(MAX_NEW_CARDS, Math.round(n)))
}

function TargetStepper({
  profile,
  value,
  onChange,
}: {
  profile: LanguageProfile
  value: number
  onChange: (value: number) => void
}) {
  const meta = languageMeta(profile.code)
  const inputId = `new-cards-target-${profile.code}`
  return (
    <div className="flex flex-wrap items-center gap-3">
      <LanguageTag code={profile.code} full size="md" className="min-w-28 justify-center" />
      <Button
        variant="outline"
        size="icon"
        aria-label={`Diminuir perguntas novas ${meta.inPhrase}`}
        onClick={() => onChange(value - 1)}
        disabled={value <= 0}
      >
        <Minus />
      </Button>
      <Label htmlFor={inputId} className="sr-only">
        Perguntas novas {meta.inPhrase}
      </Label>
      <Input
        id={inputId}
        type="number"
        inputMode="numeric"
        min={0}
        max={MAX_NEW_CARDS}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-12 w-20 text-center text-display text-2xl"
      />
      <Button
        variant="outline"
        size="icon"
        aria-label={`Aumentar perguntas novas ${meta.inPhrase}`}
        onClick={() => onChange(value + 1)}
        disabled={value >= MAX_NEW_CARDS}
      >
        <Plus />
      </Button>
      <span className="text-xs text-fg-muted">
        nível {profile.level.band}
        {profile.level.provisional ? ' (provisório)' : ''}
      </span>
    </div>
  )
}

function CategoryChips({
  categories,
  selected,
  onToggle,
}: {
  categories: Category[]
  selected: Set<string>
  onToggle: (id: string) => void
}) {
  if (categories.length === 0) {
    return <p className="text-sm text-fg-muted">Nenhuma categoria ativa. Crie uma em Configurações.</p>
  }
  const globals = categories.filter((c) => c.scope === 'global')
  const personals = categories.filter((c) => c.scope === 'personal')
  return (
    <div className="space-y-4">
      <ChipGroup label="Globais" categories={globals} selected={selected} onToggle={onToggle} />
      {personals.length > 0 ? (
        <ChipGroup label="Minhas" categories={personals} selected={selected} onToggle={onToggle} personal />
      ) : null}
    </div>
  )
}

function ChipGroup({
  label,
  categories,
  selected,
  onToggle,
  personal = false,
}: {
  label: string
  categories: Category[]
  selected: Set<string>
  onToggle: (id: string) => void
  personal?: boolean
}) {
  if (categories.length === 0) return null
  return (
    <div>
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-fg-muted">{label}</p>
      <div role="group" aria-label={`Categorias ${label.toLowerCase()}`} className="flex flex-wrap gap-2">
        {categories.map((c) => {
          const active = selected.has(c.id)
          return (
            <button
              key={c.id}
              type="button"
              aria-pressed={active}
              onClick={() => onToggle(c.id)}
              className={cn(
                'inline-flex h-9 items-center gap-1.5 rounded-full border px-3.5 text-sm font-medium transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
                active
                  ? 'border-primary bg-primary text-primary-fg'
                  : 'border-border bg-surface text-fg hover:bg-surface-muted',
              )}
            >
              {active ? <Check className="size-3.5" aria-hidden="true" /> : null}
              {c.name}
              {personal ? (
                <span
                  className={cn('text-[10px] uppercase', active ? 'text-primary-fg/70' : 'text-level-accent')}
                >
                  pessoal
                </span>
              ) : null}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function ProjectionPanel({
  projection,
  loading,
  error,
}: {
  projection: Projection | undefined
  loading: boolean
  error: boolean
}) {
  return (
    <Card className="bg-surface-muted/60">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-base">
          Carga de hoje {loading ? <Spinner size="sm" label="Recalculando…" /> : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {error && !projection ? (
          <p className="text-sm text-danger">Não foi possível estimar a carga.</p>
        ) : projection ? (
          <>
            <p className="text-display text-6xl tabular">
              <span aria-hidden="true">≈ </span>
              {formatNumber(projection.total)}
              <span className="ml-2 text-base font-sans font-normal text-fg-muted">cards hoje</span>
            </p>
            <p className="text-sm leading-relaxed text-fg">
              <strong className="tabular">{projection.carried_over + projection.to_generate}</strong> novos
              (dos quais <strong className="tabular">{projection.probes}</strong> sondas) +{' '}
              <strong className="tabular">{projection.due_today}</strong> revisões (
              <strong className="tabular">{projection.overdue}</strong> atrasadas)
            </p>
            <ul
              className="space-y-1.5 border-t border-border pt-3 text-sm text-fg-muted"
              aria-label="Por idioma"
            >
              {projection.languages
                .filter((lp) => lp.total > 0 || lp.available_carry_over > 0)
                .map((lp) => (
                  <li key={lp.language} className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <LanguageTag code={lp.language} />
                    <span>
                      nível{' '}
                      <Badge variant="outline" className="text-fg">
                        {lp.base_level}
                      </Badge>
                    </span>
                    {lp.to_generate > 0 ? <span className="tabular">· {lp.to_generate} a gerar</span> : null}
                    {lp.carried_over > 0 ? (
                      <span className="tabular">· {lp.carried_over} de dias anteriores</span>
                    ) : lp.available_carry_over > 0 ? (
                      <span className="tabular">
                        · {lp.available_carry_over}{' '}
                        {lp.available_carry_over === 1 ? 'novo esperando' : 'novos esperando'}
                      </span>
                    ) : null}
                    {lp.due_today > 0 ? (
                      <span className="tabular">
                        · {lp.due_today} {lp.due_today === 1 ? 'revisão' : 'revisões'}
                      </span>
                    ) : null}
                    {lp.probes > 0 ? (
                      <span className="tabular">
                        · {lp.probes} {lp.probes === 1 ? 'sonda' : 'sondas'}
                      </span>
                    ) : null}
                  </li>
                ))}
            </ul>
          </>
        ) : (
          <div className="space-y-2">
            <Skeleton className="h-14 w-32" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
