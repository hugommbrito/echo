import { VolumeX } from 'lucide-react'

import { cn } from '@/lib/cn'

export interface AudioPlayerProps {
  src: string | null | undefined
  mimeType?: string | null
  className?: string
  label?: string
}

/** Thin wrapper over the native player. */
export function AudioPlayer({ src, mimeType, className, label = 'Gravação' }: AudioPlayerProps) {
  if (!src) {
    return (
      <p className={cn('inline-flex items-center gap-2 text-sm text-fg-muted', className)}>
        <VolumeX className="size-4" aria-hidden="true" /> Áudio indisponível
      </p>
    )
  }
  return (
    <audio controls preload="none" aria-label={label} className={cn('h-10 w-full max-w-md', className)}>
      <source src={src} type={mimeType || undefined} />
      Seu navegador não suporta a reprodução de áudio.
    </audio>
  )
}
