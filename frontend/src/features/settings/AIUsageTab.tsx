import { useAIUsage } from '@/api/aiUsage'
import { useMe } from '@/api/auth'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateShort, formatNumber, formatUsd } from '@/lib/format'
import type { AIProviderStatus, AIStatus } from '@/types/api'

const PROVIDER_LABELS = { anthropic: 'Anthropic', openai: 'OpenAI' } as const
const SOURCE_LABELS = { user: 'sua chave', global: 'chave do Echo', none: 'indisponível' } as const

function routingSummary(ai: AIStatus): string {
  const text = ai.llm_provider
    ? `${PROVIDER_LABELS[ai.llm_provider]} (${SOURCE_LABELS[ai[ai.llm_provider].source]})`
    : 'indisponível'
  const speech = ai.speech_available ? `OpenAI (${SOURCE_LABELS[ai.openai.source]})` : 'indisponível'
  return `Textos (perguntas, avaliação, resposta melhorada): ${text} · Fala (transcrição e áudio): ${speech}`
}

function ProviderRow({ name, status }: { name: string; status: AIProviderStatus }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-3">
      <span className="font-medium">{name}</span>
      {status.configured ? (
        <Badge variant="success">configurada · {status.hint}</Badge>
      ) : status.source === 'global' ? (
        <Badge variant="default">usando a chave do Echo</Badge>
      ) : (
        <Badge variant="outline">não disponível</Badge>
      )}
    </li>
  )
}

/** Read-only: which keys serve this learner and what her calls cost (estimates). */
export function AIUsageTab() {
  const me = useMe()
  const usage = useAIUsage()

  if (me.isPending || usage.isPending) return <Skeleton className="h-64 w-full" />
  if (me.isError || usage.isError || !me.data || !usage.data) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Não foi possível carregar as informações de IA.</AlertDescription>
      </Alert>
    )
  }
  const ai = me.data.ai
  const { month, all_time: allTime, by_key_source: bySource } = usage.data

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Suas chaves de IA</CardTitle>
          <CardDescription>
            As chaves são cadastradas pelo administrador e guardadas cifradas; aqui você vê apenas de onde
            saem as chamadas. Sem chave própria, o Echo usa a chave dele.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ul className="divide-y divide-border">
            <ProviderRow name="Anthropic" status={ai.anthropic} />
            <ProviderRow name="OpenAI" status={ai.openai} />
          </ul>
          <p className="text-sm text-fg-muted">{routingSummary(ai)}</p>
          {!ai.speech_available ? (
            <Alert variant="warning">
              <AlertDescription>
                Transcrição e áudio das perguntas indisponíveis: nenhuma chave OpenAI configurada.
              </AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Custo estimado</CardTitle>
          <CardDescription>
            Calculado a partir dos preços públicos dos provedores; o valor real aparece na fatura de cada um.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <table className="w-full text-sm tabular" aria-label="Custo estimado por provedor">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-fg-muted">
                <th className="py-1 font-medium">Provedor</th>
                <th className="py-1 text-right font-medium">Este mês</th>
                <th className="py-1 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <tr>
                <td className="py-2">Anthropic</td>
                <td className="py-2 text-right">{formatUsd(month.anthropic_usd)}</td>
                <td className="py-2 text-right">{formatUsd(allTime.anthropic_usd)}</td>
              </tr>
              <tr>
                <td className="py-2">OpenAI</td>
                <td className="py-2 text-right">{formatUsd(month.openai_usd)}</td>
                <td className="py-2 text-right">{formatUsd(allTime.openai_usd)}</td>
              </tr>
              <tr className="font-semibold">
                <td className="py-2">Total</td>
                <td className="py-2 text-right">{formatUsd(month.total_usd)}</td>
                <td className="py-2 text-right">{formatUsd(allTime.total_usd)}</td>
              </tr>
            </tbody>
          </table>
          <p className="text-xs text-fg-muted">
            Mês desde {formatDateShort(month.starts_on)} · {formatNumber(month.requests)} chamadas este mês,{' '}
            {formatNumber(allTime.requests)} no total · na sua chave {formatUsd(bySource.user_usd)} · na chave
            do Echo {formatUsd(bySource.global_usd)}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
