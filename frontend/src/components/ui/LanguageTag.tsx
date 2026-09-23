import { cn } from '@/lib/cn'
import { languageMeta } from '@/lib/languages'

export interface LanguageTagProps {
  code: string
  /** Show "Inglês" instead of "EN". */
  full?: boolean
  size?: 'sm' | 'md'
  /** Render without the pill border (for use inside another badge). */
  bare?: boolean
  className?: string
}

/** Dot in the language color + text in ink: "EN" (title "Inglês") or "Inglês". */
export function LanguageTag({ code, full = false, size = 'sm', bare = false, className }: LanguageTagProps) {
  const meta = languageMeta(code)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-medium text-fg',
        !bare && 'rounded-full border border-border bg-surface',
        !bare && (size === 'sm' ? 'px-2.5 py-0.5 text-xs' : 'px-3 py-1 text-sm'),
        bare && (size === 'sm' ? 'text-xs' : 'text-sm'),
        className,
      )}
      title={full ? undefined : meta.label}
      data-language={code}
    >
      <span
        aria-hidden="true"
        className="size-2 shrink-0 rounded-full ring-1 ring-black/10 dark:ring-white/20"
        style={{ backgroundColor: `var(${meta.colorVar})` }}
      />
      {full ? (
        meta.label
      ) : (
        <abbr className="no-underline" title={meta.label}>
          {meta.short}
        </abbr>
      )}
    </span>
  )
}
