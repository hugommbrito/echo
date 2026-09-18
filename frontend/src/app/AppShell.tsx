import { BarChart3, Layers, LogOut, Settings, Sun } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useLogout, useMe } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { LevelBadge } from '@/components/ui/LevelBadge'
import { cn } from '@/lib/cn'

const NAV = [
  { to: '/today', label: 'Hoje', icon: Sun },
  { to: '/cards', label: 'Cards', icon: Layers },
  { to: '/stats', label: 'Estatísticas', icon: BarChart3 },
  { to: '/settings', label: 'Configurações', icon: Settings },
] as const

export function AppShell() {
  const me = useMe()
  const logout = useLogout()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout.mutate(undefined, {
      onSettled: () => navigate('/login', { replace: true }),
    })
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 border-b border-border bg-bg/85 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-[960px] items-center justify-between gap-3 px-4">
          <NavLink
            to="/today"
            className="flex items-center gap-2 font-semibold tracking-tight"
            aria-label="Echo — início"
          >
            <span
              aria-hidden="true"
              className="grid size-7 place-items-center rounded-lg bg-primary text-primary-fg"
            >
              <span className="size-2 rounded-full bg-primary-fg" />
            </span>
            <span className="text-display text-xl">Echo</span>
          </NavLink>

          <nav aria-label="Principal" className="hidden items-center gap-1 sm:flex">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'rounded-lg px-3 py-1.5 text-sm font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg',
                    isActive && 'bg-surface-muted text-fg',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            {me.data ? (
              <NavLink
                to="/stats"
                aria-label={`Seu nível: ${me.data.level.band}, ${me.data.level.rating} pontos`}
              >
                <LevelBadge band={me.data.level.band} rating={me.data.level.rating} size="md" />
              </NavLink>
            ) : null}
            <Button
              variant="ghost"
              size="icon"
              aria-label="Sair"
              title="Sair"
              onClick={handleLogout}
              loading={logout.isPending}
            >
              {logout.isPending ? null : <LogOut />}
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[960px] flex-1 px-4 pb-24 pt-6 sm:pb-12">
        <Outlet />
      </main>

      {/* mobile bottom nav */}
      <nav
        aria-label="Principal (mobile)"
        className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-bg/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden"
      >
        <ul className="grid grid-cols-4">
          {NAV.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium text-fg-muted',
                    isActive && 'text-fg',
                  )
                }
              >
                <item.icon className="size-5" aria-hidden="true" />
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
