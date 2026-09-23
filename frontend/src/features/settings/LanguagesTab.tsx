import { Minus, Plus } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'

import { useMe } from '@/api/auth'
import { isApiError } from '@/api/client'
import { useActivateLanguage, useLanguageCatalog, useUpdateLanguageProfile } from '@/api/languages'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { LanguageTag } from '@/components/ui/LanguageTag'
import { LevelBadge } from '@/components/ui/LevelBadge'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/cn'
import { formatDateShort } from '@/lib/format'
import { languageMeta, sortByLanguage } from '@/lib/languages'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import type { LanguageCatalogItem, LanguageProfile, StartingLevel } from '@/types/api'

const MAX_NEW_CARDS = 20

const STARTING_LEVELS: { value: StartingLevel; title: string; description: string }[] = [
  {
    value: 'A1',
    title: 'A1 — Iniciante',
    description: 'Frases curtas do dia a dia: se apresentar, pedir algo, falar da rotina.',
  },
  {
    value: 'A2',
    title: 'A2 — Básico',
    description: 'Conta o que aconteceu e descreve pessoas e lugares com frases simples.',
  },
  {
    value: 'B1',
    title: 'B1 — Intermediário',
    description: 'Sustenta uma conversa, dá opinião e explica motivos, ainda com erros.',
  },
]

export function LanguagesTab() {
  const me = useMe()
  const catalog = useLanguageCatalog()
  const [activating, setActivating] = useState<LanguageCatalogItem | null>(null)

  if (me.isPending || catalog.isPending) return <Skeleton className="h-64 w-full" />
  if (me.isError || catalog.isError || !me.data) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Não foi possível carregar os idiomas.</AlertDescription>
      </Alert>
    )
  }

  const profiles = new Map(me.data.languages.map((profile) => [profile.code, profile]))
  const rows = sortByLanguage(catalog.data, (item) => item.code)

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Idiomas</CardTitle>
          <CardDescription>
            Cada idioma tem nível e ritmo próprios. As categorias valem para todos.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="divide-y divide-border">
            {rows.map((item) => {
              const profile = profiles.get(item.code)
              return profile ? (
                <ProfileRow key={item.code} profile={profile} />
              ) : (
                <InactiveRow key={item.code} item={item} onActivate={() => setActivating(item)} />
              )
            })}
          </ul>
        </CardContent>
      </Card>
      {activating ? <ActivateLanguageDialog item={activating} onClose={() => setActivating(null)} /> : null}
    </div>
  )
}

function InactiveRow({ item, onActivate }: { item: LanguageCatalogItem; onActivate: () => void }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-4">
      <div className="flex items-center gap-3">
        <LanguageTag code={item.code} full size="md" />
        <span className="text-sm text-fg-muted">{item.name}</span>
        <Badge variant="outline">Não ativado</Badge>
      </div>
      <Button variant="outline" onClick={onActivate}>
        Ativar
      </Button>
    </li>
  )
}

function ProfileRow({ profile }: { profile: LanguageProfile }) {
  const update = useUpdateLanguageProfile()
  const meta = languageMeta(profile.code)
  const [target, setTarget] = useState(profile.default_new_cards_per_day)
  const debounced = useDebouncedValue(target, 400)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (debounced === profile.default_new_cards_per_day) return
    setSaved(false)
    update.mutate(
      { code: profile.code, patch: { default_new_cards_per_day: debounced } },
      { onSuccess: () => setSaved(true) },
    )
    // `update` is a stable mutation object; re-running on every render would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced, profile.code, profile.default_new_cards_per_day])

  const toggle = (checked: boolean) => {
    update.mutate({ code: profile.code, patch: { is_active: checked } })
  }
  const targetError = isApiError(update.error) ? update.error.fieldError('default_new_cards_per_day') : null
  const inputId = `default-target-${profile.code}`

  return (
    <li className={cn('space-y-3 py-4', !profile.is_active && 'opacity-70')} data-language={profile.code}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <LanguageTag code={profile.code} full size="md" />
          <LevelBadge band={profile.level.band} rating={profile.level.rating} />
          {profile.level.provisional ? <Badge variant="outline">provisório</Badge> : null}
          {!profile.is_active ? <Badge variant="warning">Pausado</Badge> : null}
          <span className="text-xs text-fg-muted">desde {formatDateShort(profile.activated_at)}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-fg-muted">{profile.is_active ? 'Ativo' : 'Pausado'}</span>
          <Switch
            checked={profile.is_active}
            onCheckedChange={toggle}
            disabled={update.isPending}
            aria-label={`${profile.is_active ? 'Pausar' : 'Retomar'} ${meta.label.toLowerCase()}`}
          />
        </div>
      </div>
      <p className="text-xs text-fg-muted">{profile.name}</p>
      <div className="flex flex-wrap items-center gap-3">
        <Label htmlFor={inputId} className="text-sm">
          Perguntas novas por dia
        </Label>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            aria-label={`Diminuir perguntas novas ${meta.inPhrase}`}
            onClick={() => setTarget((t) => clamp(t - 1))}
            disabled={target <= 0}
          >
            <Minus />
          </Button>
          <Input
            id={inputId}
            type="number"
            inputMode="numeric"
            min={0}
            max={MAX_NEW_CARDS}
            value={target}
            onChange={(e) => setTarget(clamp(Number(e.target.value)))}
            className="w-20 text-center"
          />
          <Button
            variant="outline"
            size="icon"
            aria-label={`Aumentar perguntas novas ${meta.inPhrase}`}
            onClick={() => setTarget((t) => clamp(t + 1))}
            disabled={target >= MAX_NEW_CARDS}
          >
            <Plus />
          </Button>
        </div>
        {targetError ? (
          <span className="text-xs text-danger">{targetError}</span>
        ) : saved && debounced === profile.default_new_cards_per_day ? (
          <span className="text-xs text-success">Salvo.</span>
        ) : null}
      </div>
      {update.isError && !targetError ? (
        <Alert variant="destructive">
          <AlertDescription>
            {isApiError(update.error) ? update.error.detail : 'Não foi possível salvar.'}
          </AlertDescription>
        </Alert>
      ) : null}
    </li>
  )
}

function clamp(n: number): number {
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(MAX_NEW_CARDS, Math.round(n)))
}

function ActivateLanguageDialog({ item, onClose }: { item: LanguageCatalogItem; onClose: () => void }) {
  const activate = useActivateLanguage()
  const meta = languageMeta(item.code)
  const [level, setLevel] = useState<StartingLevel>('A1')
  const levels = STARTING_LEVELS.filter((option) => item.starting_levels.includes(option.value))

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    activate.mutate({ language: item.code, starting_level: level }, { onSuccess: onClose })
  }

  const error = activate.isError
    ? isApiError(activate.error)
      ? activate.error.status === 409
        ? 'Este idioma já está ativado.'
        : (activate.error.fieldError('starting_level') ?? activate.error.detail)
      : 'Não foi possível ativar o idioma.'
    : null

  return (
    <Dialog
      open
      onOpenChange={(open) => (!open ? onClose() : undefined)}
      title={`Ativar ${meta.label.toLowerCase()}`}
      description="Escolha por onde começar. O nível se ajusta sozinho depois das primeiras respostas."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Nível inicial</legend>
          {levels.map((option) => (
            <label
              key={option.value}
              className={cn(
                'flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors',
                level === option.value
                  ? 'border-primary bg-surface-muted'
                  : 'border-border hover:bg-surface-muted/60',
              )}
            >
              <input
                type="radio"
                name="starting_level"
                value={option.value}
                checked={level === option.value}
                onChange={() => setLevel(option.value)}
                className="mt-1"
              />
              <span>
                <span className="block text-sm font-medium">{option.title}</span>
                <span className="block text-xs text-fg-muted">{option.description}</span>
              </span>
            </label>
          ))}
        </fieldset>
        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" loading={activate.isPending}>
            Ativar idioma
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  )
}
