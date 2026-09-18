import type { ReactElement } from 'react'

export type LabelRenderProps = {
  x?: number | string
  y?: number | string
  width?: number | string
  height?: number | string
  index?: number
  value?: number | string | null
}

type RectProps = { x?: number; y?: number; width?: number; height?: number; fill?: string; radius?: number }

/**
 * Bar segment with the 2px surface gap baked in (no strokes) and a 4px rounded data-end when
 * `radius` is set. Vertical bars are capped at 24px wide by the chart's `barSize`.
 */
export function gapRect(orientation: 'vertical' | 'horizontal', rounded = false) {
  return function GapRect(raw: unknown): ReactElement {
    const { x = 0, y = 0, width = 0, height = 0, fill } = raw as RectProps
    if (width <= 0 || height <= 0) return <g />
    const gap = 2
    const r = rounded ? 4 : 0
    if (orientation === 'vertical') {
      const h = Math.max(0, height - gap)
      const yy = y + gap // gap sits between this segment and the one above it
      if (!rounded) return <rect x={x} y={yy} width={width} height={h} fill={fill} />
      const rr = Math.min(r, width / 2, h)
      const d = `M${x},${yy + h} V${yy + rr} Q${x},${yy} ${x + rr},${yy} H${x + width - rr} Q${x + width},${yy} ${x + width},${yy + rr} V${yy + h} Z`
      return <path d={d} fill={fill} />
    }
    const w = Math.max(0, width - gap)
    const xx = x // gap sits on the right of each segment
    if (!rounded) return <rect x={xx} y={y} width={w} height={height} fill={fill} />
    const rr = Math.min(r, height / 2, w)
    const d = `M${xx},${y} H${xx + w - rr} Q${xx + w},${y} ${xx + w},${y + rr} V${y + height - rr} Q${xx + w},${y + height} ${xx + w - rr},${y + height} H${xx} Z`
    return <path d={d} fill={fill} />
  }
}

/** Selective direct label: only the last point of a line gets its value, in text ink. */
export function endLabel(lastIndex: number, text: (value: number) => string, ink: string) {
  return function EndLabel(raw: unknown) {
    const props = raw as LabelRenderProps
    if (props.index !== lastIndex || props.value == null || props.x == null || props.y == null) return <g />
    return (
      <text x={Number(props.x) + 8} y={Number(props.y)} dy={4} fontSize={11} fill={ink} fontWeight={600}>
        {text(Number(props.value))}
      </text>
    )
  }
}
