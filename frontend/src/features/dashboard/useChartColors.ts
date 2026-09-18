import { useEffect, useState } from 'react'

/**
 * Recharts writes colors as SVG attributes, where `var(--x)` is not resolved, so the chart
 * tokens are read from the computed style and refreshed when the color scheme changes.
 * Values come from the validated palette in docs/dataviz-palette.md.
 */
export type ChartColors = {
  structure: string
  grammar: string
  fluency: string
  new: string
  learning: string
  mature: string
  ink: string
  inkSecondary: string
  inkMuted: string
  grid: string
  axis: string
  surface: string
  good: string
  bad: string
  band: string
  bandAlt: string
}

const FALLBACK: ChartColors = {
  structure: '#2a78d6',
  grammar: '#eb6834',
  fluency: '#1baf7a',
  new: '#a49ce8',
  learning: '#7466d2',
  mature: '#4a3aa7',
  ink: '#0b0b0b',
  inkSecondary: '#52514e',
  inkMuted: '#898781',
  grid: '#e1e0d9',
  axis: '#c3c2b7',
  surface: '#fcfcfb',
  good: '#006300',
  bad: '#d03b3b',
  band: '#f3f2ee',
  bandAlt: '#fcfcfb',
}

const VARS: Record<keyof ChartColors, string> = {
  structure: '--axis-structure',
  grammar: '--axis-grammar',
  fluency: '--axis-fluency',
  new: '--maturity-new',
  learning: '--maturity-learning',
  mature: '--maturity-mature',
  ink: '--chart-ink',
  inkSecondary: '--chart-ink-secondary',
  inkMuted: '--chart-ink-muted',
  grid: '--chart-grid',
  axis: '--chart-axis',
  surface: '--surface',
  good: '--status-good',
  bad: '--status-critical',
  band: '--chart-band',
  bandAlt: '--chart-band-alt',
}

function readColors(): ChartColors {
  if (typeof window === 'undefined') return FALLBACK
  const style = getComputedStyle(document.documentElement)
  const out = { ...FALLBACK }
  for (const key of Object.keys(VARS) as (keyof ChartColors)[]) {
    const value = style.getPropertyValue(VARS[key]).trim()
    if (value) out[key] = value
  }
  return out
}

export function useChartColors(): ChartColors {
  const [colors, setColors] = useState<ChartColors>(readColors)
  useEffect(() => {
    const refresh = () => setColors(readColors())
    refresh()
    const media =
      typeof window.matchMedia === 'function' ? window.matchMedia('(prefers-color-scheme: dark)') : null
    media?.addEventListener('change', refresh)
    const observer = typeof MutationObserver === 'function' ? new MutationObserver(refresh) : null
    observer?.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme', 'class'],
    })
    return () => {
      media?.removeEventListener('change', refresh)
      observer?.disconnect()
    }
  }, [])
  return colors
}
