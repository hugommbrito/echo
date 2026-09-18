import { Sparkles } from 'lucide-react'
import { useState } from 'react'

import { useImprovedAnswer } from '@/api/attempts'
import { isApiError } from '@/api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import type { Attempt, ImprovedAnswer } from '@/types/api'

function describeError(error: unknown): string {
  if (isApiError(error)) {
    if (error.status === 503) return 'O serviço de IA está indisponível agora. Tente de novo em instantes.'
    if (error.code === 'insufficient_speech')
      return 'Não há fala suficiente nesta tentativa para sugerir uma resposta.'
    if (error.code === 'not_evaluated') return 'Esta tentativa ainda não foi avaliada.'
    return error.detail
  }
  return 'Não foi possível gerar a sugestão.'
}

export function ImprovedAnswerButton({ attempt }: { attempt: Attempt }) {
  const mutation = useImprovedAnswer(attempt.id)
  const [result, setResult] = useState<ImprovedAnswer | null>(null)

  const existing = attempt.evaluation?.improved_answer
  const answer = result?.improved_answer ?? existing ?? null
  const notes = result?.notes ?? attempt.evaluation?.improved_answer_notes ?? []

  if (answer) {
    return (
      <section
        aria-label="Sugestão de resposta melhorada"
        className="space-y-3 rounded-2xl border border-level-accent/30 bg-level-accent/5 p-5"
      >
        <h3 className="flex items-center gap-2 text-sm font-semibold text-level-accent">
          <Sparkles className="size-4" aria-hidden="true" /> Sugestão de resposta melhorada
        </h3>
        <p className="whitespace-pre-line leading-relaxed" lang="en">
          {answer}
        </p>
        {notes.length > 0 ? (
          <ul className="list-disc space-y-1 pl-5 text-sm text-fg-muted">
            {notes.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        ) : null}
      </section>
    )
  }

  return (
    <div className="space-y-2">
      <Button
        variant="outline"
        onClick={() => mutation.mutate(undefined, { onSuccess: setResult })}
        loading={mutation.isPending}
        className="border-level-accent/40 text-level-accent hover:bg-level-accent/10"
      >
        {mutation.isPending ? null : <Sparkles />}
        {mutation.isPending ? 'Gerando sugestão…' : 'Ver sugestão de resposta melhorada'}
      </Button>
      {mutation.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{describeError(mutation.error)}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  )
}
