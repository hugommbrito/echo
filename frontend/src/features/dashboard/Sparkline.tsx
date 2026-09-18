/** Tiny trend line for stat tiles and tables (de-emphasis hue, accent on the last point). */
export function Sparkline({
  values,
  color,
  width = 96,
  height = 28,
  accentLast = true,
}: {
  values: (number | null)[]
  color: string
  width?: number
  height?: number
  accentLast?: boolean
}) {
  const clean = values.map((v) => (v == null ? null : v))
  const present = clean.filter((v): v is number => v != null)
  if (present.length < 2) return <svg width={width} height={height} aria-hidden />
  const min = Math.min(...present)
  const max = Math.max(...present)
  const span = max - min || 1
  const step = width / Math.max(1, clean.length - 1)
  const points = clean.map((v, i) =>
    v == null ? null : ([i * step, height - 3 - ((v - min) / span) * (height - 6)] as const),
  )
  const d = points
    .map((p, i) => (p ? `${i === 0 || !points[i - 1] ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}` : ''))
    .join(' ')
  const last = [...points].reverse().find((p) => p)
  return (
    <svg width={width} height={height} aria-hidden className="overflow-visible">
      <path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {accentLast && last ? (
        <circle cx={last[0]} cy={last[1]} r={3} fill={color} stroke="var(--surface)" strokeWidth={2} />
      ) : null}
    </svg>
  )
}
