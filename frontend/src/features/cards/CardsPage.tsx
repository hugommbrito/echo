import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useCards } from '@/api/cards'
import { useCategories } from '@/api/categories'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { LevelBadge } from '@/components/ui/LevelBadge'
import { MaturityBadge } from '@/components/ui/MaturityBadge'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { MATURITY_LABELS } from '@/lib/colors'
import { formatNumber, plural } from '@/lib/format'
import { CARD_STATUS_LABELS } from '@/lib/labels'
import { CEFR_BANDS } from '@/lib/levels'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import type { CardFilters, CardStatus, Maturity } from '@/types/api'

const PAGE_SIZE = 30

export function CardsPage() {
  const [params, setParams] = useSearchParams()
  const categories = useCategories()

  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)
  const filters: CardFilters = {
    category: params.get('category') ?? '',
    maturity: (params.get('maturity') ?? '') as CardFilters['maturity'],
    level: (params.get('level') ?? '') as CardFilters['level'],
    status: (params.get('status') ?? '') as CardFilters['status'],
    q: params.get('q') ?? '',
    page,
    page_size: PAGE_SIZE,
  }

  const [search, setSearch] = useState(filters.q ?? '')
  const debouncedSearch = useDebouncedValue(search, 350)

  useEffect(() => {
    if (debouncedSearch !== (params.get('q') ?? '')) {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (debouncedSearch) next.set('q', debouncedSearch)
          else next.delete('q')
          next.delete('page')
          return next
        },
        { replace: true },
      )
    }
  }, [debouncedSearch, params, setParams])

  const cards = useCards(filters)

  const setFilter = (key: string, value: string) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      next.delete('page')
      return next
    })
  }

  const setPage = (p: number) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (p > 1) next.set('page', String(p))
      else next.delete('page')
      return next
    })
  }

  const count = cards.data?.count ?? 0
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE))
  const first = count === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const last = Math.min(count, page * PAGE_SIZE)

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-display text-3xl sm:text-4xl">Cards</h1>
          <p className="text-sm text-fg-muted">
            {cards.data ? plural(count, 'card', 'cards') : 'Sua coleção de perguntas'}
          </p>
        </div>
      </header>

      <Card className="p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="space-y-1 lg:col-span-1 sm:col-span-2">
            <Label htmlFor="cards-search">Buscar</Label>
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-muted"
                aria-hidden="true"
              />
              <Input
                id="cards-search"
                type="search"
                placeholder="Texto da pergunta"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="filter-category">Categoria</Label>
            <Select
              id="filter-category"
              value={filters.category}
              onChange={(e) => setFilter('category', e.target.value)}
            >
              <option value="">Todas</option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.slug}>
                  {c.name}
                  {c.scope === 'personal' ? ' (pessoal)' : ''}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="filter-maturity">Maturidade</Label>
            <Select
              id="filter-maturity"
              value={filters.maturity ?? ''}
              onChange={(e) => setFilter('maturity', e.target.value)}
            >
              <option value="">Todas</option>
              {(Object.keys(MATURITY_LABELS) as Maturity[]).map((m) => (
                <option key={m} value={m}>
                  {MATURITY_LABELS[m]}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="filter-level">Nível</Label>
            <Select
              id="filter-level"
              value={filters.level ?? ''}
              onChange={(e) => setFilter('level', e.target.value)}
            >
              <option value="">Todos</option>
              {CEFR_BANDS.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="filter-status">Status</Label>
            <Select
              id="filter-status"
              value={filters.status ?? ''}
              onChange={(e) => setFilter('status', e.target.value)}
            >
              <option value="">Todos</option>
              {(Object.keys(CARD_STATUS_LABELS) as CardStatus[]).map((s) => (
                <option key={s} value={s}>
                  {CARD_STATUS_LABELS[s]}
                </option>
              ))}
            </Select>
          </div>
        </div>
      </Card>

      {cards.isPending ? (
        <ul className="space-y-2" aria-busy="true">
          {Array.from({ length: 6 }, (_, i) => (
            <li key={i}>
              <Skeleton className="h-20 w-full" />
            </li>
          ))}
        </ul>
      ) : cards.isError ? (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar os cards.</AlertDescription>
        </Alert>
      ) : cards.data.results.length === 0 ? (
        <Card className="p-10 text-center text-fg-muted">Nenhum card encontrado com esses filtros.</Card>
      ) : (
        <ul className="space-y-2" aria-busy={cards.isFetching || undefined}>
          {cards.data.results.map((card) => (
            <li key={card.id}>
              <Link
                to={`/cards/${card.id}`}
                className="block rounded-2xl border border-border bg-surface p-4 transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <p className="font-medium leading-snug">{card.question_text}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-fg-muted">
                  <Badge variant="outline">{card.category.name}</Badge>
                  <LevelBadge band={card.cefr_level} probe={card.probe} />
                  <MaturityBadge maturity={card.maturity} />
                  {card.status !== 'active' ? (
                    <Badge variant="warning">{CARD_STATUS_LABELS[card.status]}</Badge>
                  ) : null}
                  <span className="ml-auto tabular">
                    {plural(card.attempt_count, 'tentativa', 'tentativas')}
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {cards.data && count > 0 ? (
        <nav aria-label="Paginação" className="flex items-center justify-between gap-3 text-sm text-fg-muted">
          <span className="tabular">
            {formatNumber(first)}–{formatNumber(last)} de {formatNumber(count)}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(page - 1)}
              disabled={!cards.data.previous}
            >
              <ChevronLeft /> Anterior
            </Button>
            <span className="tabular">
              {page}/{totalPages}
            </span>
            <Button variant="outline" size="sm" onClick={() => setPage(page + 1)} disabled={!cards.data.next}>
              Próxima <ChevronRight />
            </Button>
          </div>
        </nav>
      ) : null}
    </div>
  )
}
