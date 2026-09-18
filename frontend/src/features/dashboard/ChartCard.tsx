import { useState, type ReactNode } from 'react'
import { Table2, BarChart3 } from 'lucide-react'

export type TableSpec = {
  columns: string[]
  rows: (string | number | null | undefined)[][]
}

type Props = {
  title: string
  subtitle?: string
  children: ReactNode
  table?: TableSpec
  footer?: ReactNode
  actions?: ReactNode
  loading?: boolean
  empty?: boolean
  emptyText?: string
  className?: string
}

/**
 * Chart container: title, optional actions, a "ver tabela" twin (WCAG-clean equivalent)
 * and a footer line. While data refetches the previous render is kept at reduced opacity.
 */
export function ChartCard({
  title,
  subtitle,
  children,
  table,
  footer,
  actions,
  loading,
  empty,
  emptyText,
  className,
}: Props) {
  const [showTable, setShowTable] = useState(false)
  return (
    <figure
      className={`flex min-w-0 flex-col rounded-2xl border border-border bg-surface p-4 shadow-sm sm:p-5 ${className ?? ''}`}
    >
      <figcaption className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-base font-semibold leading-tight text-fg">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-sm text-fg-muted">{subtitle}</p> : null}
        </div>
        <div className="flex items-center gap-1">
          {actions}
          {table ? (
            <button
              type="button"
              onClick={() => setShowTable((v) => !v)}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-fg-muted hover:bg-bg hover:text-fg focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              aria-pressed={showTable}
            >
              {showTable ? (
                <BarChart3 className="size-3.5" aria-hidden />
              ) : (
                <Table2 className="size-3.5" aria-hidden />
              )}
              {showTable ? 'Ver gráfico' : 'Ver tabela'}
            </button>
          ) : null}
        </div>
      </figcaption>
      <div className={`min-w-0 flex-1 transition-opacity ${loading ? 'opacity-60' : ''}`} aria-busy={loading}>
        {empty ? (
          <p className="flex h-40 items-center justify-center text-sm text-fg-muted">
            {emptyText ?? 'Sem dados no período.'}
          </p>
        ) : showTable && table ? (
          <DataTable spec={table} />
        ) : (
          children
        )}
      </div>
      {footer ? <div className="mt-3 border-t border-border pt-2 text-xs text-fg-muted">{footer}</div> : null}
    </figure>
  )
}

export function DataTable({ spec }: { spec: TableSpec }) {
  return (
    <div className="max-h-80 overflow-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-bg text-left text-xs uppercase tracking-wide text-fg-muted">
          <tr>
            {spec.columns.map((c) => (
              <th key={c} className="px-3 py-2 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {spec.rows.map((row, i) => (
            <tr key={i} className="border-t border-border">
              {row.map((cell, j) => (
                <td key={j} className={`px-3 py-1.5 ${j > 0 ? 'tabular-nums' : ''}`}>
                  {cell ?? '–'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Tooltip body shared by every chart: values lead, labels follow, keyed by a short line. */
export function TooltipFrame({
  title,
  rows,
}: {
  title: string
  rows: { label: string; value: string; color?: string; muted?: boolean }[]
}) {
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-fg">{title}</p>
      <ul className="space-y-0.5">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center gap-2">
            {r.color ? (
              <span aria-hidden className="inline-block h-0.5 w-3 rounded" style={{ background: r.color }} />
            ) : (
              <span className="w-3" />
            )}
            <span className={`font-semibold tabular-nums ${r.muted ? 'text-fg-muted' : 'text-fg'}`}>
              {r.value}
            </span>
            <span className="text-fg-muted">{r.label}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function LegendRow({
  items,
  active,
  onToggle,
  shape = 'line',
}: {
  items: { key: string; label: string; color: string }[]
  active?: string | null
  onToggle?: (key: string) => void
  shape?: 'line' | 'rect'
}) {
  return (
    <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-muted">
      {items.map((item) => {
        const dim = active && active !== item.key
        const content = (
          <>
            <span
              aria-hidden
              className={
                shape === 'line' ? 'inline-block h-0.5 w-4 rounded' : 'inline-block size-3 rounded-sm'
              }
              style={{ background: dim ? 'var(--chart-axis)' : item.color }}
            />
            <span className={dim ? 'opacity-60' : ''}>{item.label}</span>
          </>
        )
        return (
          <li key={item.key}>
            {onToggle ? (
              <button
                type="button"
                onClick={() => onToggle(item.key)}
                aria-pressed={active === item.key}
                className="inline-flex items-center gap-1.5 rounded px-1 hover:text-fg focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                {content}
              </button>
            ) : (
              <span className="inline-flex items-center gap-1.5">{content}</span>
            )}
          </li>
        )
      })}
    </ul>
  )
}
