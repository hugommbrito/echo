import { Pencil, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useMe, useUpdateMe } from '@/api/auth'
import { slugify, useCategories, useCreateCategory, useUpdateCategory } from '@/api/categories'
import { isApiError } from '@/api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { plural } from '@/lib/format'
import type { Category, FeedbackLanguage, User } from '@/types/api'

import { LanguagesTab } from './LanguagesTab'

const TABS = ['preferences', 'languages', 'categories'] as const
type Tab = (typeof TABS)[number]

function isTab(value: string | null): value is Tab {
  return value !== null && (TABS as readonly string[]).includes(value)
}

const COMMON_TIMEZONES = [
  'America/Sao_Paulo',
  'America/Toronto',
  'America/Vancouver',
  'America/Edmonton',
  'America/Winnipeg',
  'America/Halifax',
  'America/St_Johns',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Manaus',
  'America/Fortaleza',
  'America/Recife',
  'America/Bahia',
  'America/Belem',
  'America/Cuiaba',
  'America/Rio_Branco',
  'Europe/Lisbon',
  'Europe/London',
  'Europe/Dublin',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Madrid',
  'UTC',
]

export function SettingsPage() {
  const me = useMe()
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const tab: Tab = isTab(requested) ? requested : 'preferences'
  const setTab = (value: string) => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value === 'preferences') next.delete('tab')
        else next.set('tab', value)
        return next
      },
      { replace: true },
    )
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-display text-3xl sm:text-4xl">Configurações</h1>
        {me.data ? <p className="text-sm text-fg-muted">{me.data.email}</p> : null}
      </header>

      <Tabs value={tab} onValueChange={setTab} id="settings">
        <TabsList>
          <TabsTrigger value="preferences">Preferências</TabsTrigger>
          <TabsTrigger value="languages">Idiomas</TabsTrigger>
          <TabsTrigger value="categories">Categorias</TabsTrigger>
        </TabsList>
        <TabsContent value="preferences">
          {me.data ? (
            <PreferencesForm key={`${me.data.timezone}|${me.data.feedback_language}`} me={me.data} />
          ) : (
            <Skeleton className="h-64 w-full" />
          )}
        </TabsContent>
        <TabsContent value="languages">
          <LanguagesTab />
        </TabsContent>
        <TabsContent value="categories">
          <CategoriesSection />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// ---------------------------------------------------------------------------

function PreferencesForm({ me }: { me: User }) {
  const update = useUpdateMe()
  const [timezone, setTimezone] = useState(me.timezone)
  const [language, setLanguage] = useState<FeedbackLanguage>(me.feedback_language)
  const [saved, setSaved] = useState(false)

  const dirty = timezone !== me.timezone || language !== me.feedback_language

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSaved(false)
    update.mutate(
      { timezone: timezone.trim(), feedback_language: language },
      { onSuccess: () => setSaved(true) },
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Preferências</CardTitle>
        <CardDescription>
          Fuso horário define o "dia" das sessões; o idioma do feedback vale para todas as línguas que você
          pratica. As perguntas novas por dia ficam na aba Idiomas.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-1.5">
            <Label htmlFor="timezone">Fuso horário</Label>
            <Input
              id="timezone"
              list="timezones"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              placeholder="America/Sao_Paulo"
              autoComplete="off"
              aria-invalid={
                update.isError && isApiError(update.error) && Boolean(update.error.fieldError('timezone'))
              }
            />
            <datalist id="timezones">
              {COMMON_TIMEZONES.map((tz) => (
                <option key={tz} value={tz} />
              ))}
            </datalist>
            {isApiError(update.error) && update.error.fieldError('timezone') ? (
              <p className="text-xs text-danger">{update.error.fieldError('timezone')}</p>
            ) : (
              <p className="text-xs text-fg-muted">Nome IANA, por exemplo America/Toronto.</p>
            )}
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="feedback-language">Idioma do feedback</Label>
              <Select
                id="feedback-language"
                value={language}
                onChange={(e) => setLanguage(e.target.value as FeedbackLanguage)}
              >
                <option value="pt-BR">Português (Brasil)</option>
                <option value="en">English</option>
              </Select>
            </div>
          </div>

          {update.isError && !isApiError(update.error) ? (
            <Alert variant="destructive">
              <AlertDescription>Não foi possível salvar. Verifique sua conexão.</AlertDescription>
            </Alert>
          ) : null}
          {update.isError && isApiError(update.error) && !update.error.errors ? (
            <Alert variant="destructive">
              <AlertDescription>{update.error.detail}</AlertDescription>
            </Alert>
          ) : null}

          <div className="flex items-center gap-3">
            <Button type="submit" loading={update.isPending} disabled={!dirty}>
              Salvar
            </Button>
            {saved && !dirty ? <span className="text-sm text-success">Preferências salvas.</span> : null}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------

function CategoriesSection() {
  const categories = useCategories()
  const [editing, setEditing] = useState<Category | null>(null)

  if (categories.isPending) return <Skeleton className="h-64 w-full" />
  if (categories.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Não foi possível carregar as categorias.</AlertDescription>
      </Alert>
    )
  }

  const personals = categories.data.filter((c) => c.scope === 'personal')
  const globals = categories.data.filter((c) => c.scope === 'global')

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Minhas categorias</CardTitle>
          <CardDescription>
            Temas seus. A dica de geração orienta as perguntas novas dessa categoria.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {personals.length === 0 ? (
            <p className="text-sm text-fg-muted">Você ainda não criou categorias pessoais.</p>
          ) : (
            <ul className="divide-y divide-border">
              {personals.map((c) => (
                <CategoryRow key={c.id} category={c} onEdit={() => setEditing(c)} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <CreateCategoryForm />

      <Card>
        <CardHeader>
          <CardTitle>Categorias globais</CardTitle>
          <CardDescription>Disponíveis para todo mundo; somente leitura.</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="divide-y divide-border">
            {globals.map((c) => (
              <li key={c.id} className="flex items-start justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="font-medium">
                    {c.name}
                    {!c.is_active ? (
                      <Badge variant="outline" className="ml-2">
                        inativa
                      </Badge>
                    ) : null}
                  </p>
                  {c.description ? <p className="text-sm text-fg-muted">{c.description}</p> : null}
                </div>
                <span className="shrink-0 text-xs text-fg-muted tabular">
                  {plural(c.card_count, 'card', 'cards')}
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {editing ? <EditCategoryDialog category={editing} onClose={() => setEditing(null)} /> : null}
    </div>
  )
}

function CategoryRow({ category, onEdit }: { category: Category; onEdit: () => void }) {
  const update = useUpdateCategory()
  return (
    <li className="flex items-start justify-between gap-3 py-3">
      <div className="min-w-0 flex-1">
        <p className="font-medium">
          {category.name} <span className="text-xs font-normal text-fg-muted">/{category.slug}</span>
        </p>
        {category.description ? <p className="text-sm text-fg-muted">{category.description}</p> : null}
        <p className="mt-1 text-xs text-fg-muted tabular">{plural(category.card_count, 'card', 'cards')}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Switch
          checked={category.is_active}
          onCheckedChange={(checked) => update.mutate({ id: category.id, patch: { is_active: checked } })}
          disabled={update.isPending}
          aria-label={`${category.is_active ? 'Desativar' : 'Ativar'} ${category.name}`}
        />
        <Button variant="ghost" size="icon" aria-label={`Editar ${category.name}`} onClick={onEdit}>
          <Pencil />
        </Button>
      </div>
    </li>
  )
}

function EditCategoryDialog({ category, onClose }: { category: Category; onClose: () => void }) {
  const update = useUpdateCategory()
  const [name, setName] = useState(category.name)
  const [description, setDescription] = useState(category.description)
  const [hint, setHint] = useState(category.generation_hint)
  const [active, setActive] = useState(category.is_active)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    update.mutate(
      {
        id: category.id,
        patch: { name: name.trim(), description, generation_hint: hint, is_active: active },
      },
      { onSuccess: onClose },
    )
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => (!open ? onClose() : undefined)}
      title="Editar categoria"
      description={`/${category.slug}`}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="edit-name">Nome</Label>
          <Input
            id="edit-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={80}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="edit-description">Descrição</Label>
          <Textarea
            id="edit-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="edit-hint">Dica de geração</Label>
          <Textarea
            id="edit-hint"
            value={hint}
            onChange={(e) => setHint(e.target.value)}
            rows={3}
            placeholder="Ex.: situações de trabalho em cafés de Toronto"
          />
        </div>
        <div className="flex items-center justify-between">
          <Label htmlFor="edit-active">Ativa</Label>
          <Switch id="edit-active" checked={active} onCheckedChange={setActive} />
        </div>
        {update.isError ? (
          <Alert variant="destructive">
            <AlertDescription>
              {isApiError(update.error)
                ? (update.error.fieldError('name') ?? update.error.detail)
                : 'Não foi possível salvar.'}
            </AlertDescription>
          </Alert>
        ) : null}
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" loading={update.isPending} disabled={!name.trim()}>
            Salvar
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  )
}

function CreateCategoryForm() {
  const create = useCreateCategory()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [hint, setHint] = useState('')
  const slug = slugify(name)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!slug) return
    create.mutate(
      { slug, name: name.trim(), description: description.trim(), generation_hint: hint.trim() },
      {
        onSuccess: () => {
          setName('')
          setDescription('')
          setHint('')
        },
      },
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Plus className="size-4" aria-hidden="true" /> Nova categoria pessoal
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="new-name">Nome</Label>
              <Input
                id="new-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={80}
                placeholder="Ex.: Entrevista de emprego"
              />
              <p className="text-xs text-fg-muted">
                Identificador: <code className="font-mono">{slug || '—'}</code>
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-description">Descrição</Label>
              <Textarea
                id="new-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-hint">Dica de geração</Label>
            <Textarea
              id="new-hint"
              value={hint}
              onChange={(e) => setHint(e.target.value)}
              rows={2}
              placeholder="Contexto extra para as perguntas dessa categoria (opcional)"
            />
          </div>
          {create.isError ? (
            <Alert variant="destructive">
              <AlertDescription>
                {isApiError(create.error)
                  ? (create.error.fieldError('slug') ??
                    create.error.fieldError('name') ??
                    create.error.detail)
                  : 'Não foi possível criar a categoria.'}
              </AlertDescription>
            </Alert>
          ) : null}
          {create.isSuccess ? <p className="text-sm text-success">Categoria criada.</p> : null}
          <Button type="submit" loading={create.isPending} disabled={!slug}>
            Criar categoria
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
