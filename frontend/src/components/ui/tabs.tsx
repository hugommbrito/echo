import {
  createContext,
  useContext,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type ReactNode,
} from 'react'

import { cn } from '@/lib/cn'

interface TabsContextValue {
  value: string
  onValueChange: (value: string) => void
  id: string
}

const TabsContext = createContext<TabsContextValue | null>(null)

function useTabs(): TabsContextValue {
  const ctx = useContext(TabsContext)
  if (!ctx) throw new Error('Tabs components must be used inside <Tabs>')
  return ctx
}

export interface TabsProps {
  value: string
  onValueChange: (value: string) => void
  /** Base id for aria wiring. */
  id?: string
  className?: string
  children: ReactNode
}

/** Simple controlled tabs. */
export function Tabs({ value, onValueChange, id = 'tabs', className, children }: TabsProps) {
  return (
    <TabsContext.Provider value={{ value, onValueChange, id }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  )
}

export function TabsList({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="tablist"
      className={cn(
        'inline-flex h-10 items-center gap-1 rounded-xl bg-surface-muted p-1 text-fg-muted',
        className,
      )}
      {...props}
    />
  )
}

export interface TabsTriggerProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  value: string
}

export function TabsTrigger({ value, className, children, ...props }: TabsTriggerProps) {
  const ctx = useTabs()
  const selected = ctx.value === value
  return (
    <button
      type="button"
      role="tab"
      id={`${ctx.id}-tab-${value}`}
      aria-selected={selected}
      aria-controls={`${ctx.id}-panel-${value}`}
      tabIndex={selected ? 0 : -1}
      onClick={() => ctx.onValueChange(value)}
      className={cn(
        'inline-flex h-8 items-center justify-center whitespace-nowrap rounded-lg px-3 text-sm font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        selected ? 'bg-surface text-fg shadow-sm' : 'hover:text-fg',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}

export interface TabsContentProps extends HTMLAttributes<HTMLDivElement> {
  value: string
}

export function TabsContent({ value, className, children, ...props }: TabsContentProps) {
  const ctx = useTabs()
  if (ctx.value !== value) return null
  return (
    <div
      role="tabpanel"
      id={`${ctx.id}-panel-${value}`}
      aria-labelledby={`${ctx.id}-tab-${value}`}
      tabIndex={0}
      className={cn('mt-4 focus-visible:outline-none', className)}
      {...props}
    >
      {children}
    </div>
  )
}
