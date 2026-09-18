import { createBrowserRouter, Navigate } from 'react-router-dom'

import { LoginPage } from '@/features/auth/LoginPage'
import { CardDetailPage } from '@/features/cards/CardDetailPage'
import { CardsPage } from '@/features/cards/CardsPage'
import { LazyStatsPage } from '@/features/dashboard/LazyStatsPage'
import { TodayPage } from '@/features/day-setup/TodayPage'
import { SessionPage } from '@/features/practice/SessionPage'
import { SettingsPage } from '@/features/settings/SettingsPage'

import { AppShell } from './AppShell'

import { NotFoundPage } from './NotFoundPage'
import { RequireAuth } from './RequireAuth'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { path: '/', element: <Navigate to="/today" replace /> },
      { path: '/today', element: <TodayPage /> },
      { path: '/session/:id', element: <SessionPage /> },
      { path: '/cards', element: <CardsPage /> },
      { path: '/cards/:id', element: <CardDetailPage /> },
      { path: '/stats', element: <LazyStatsPage /> },
      { path: '/settings', element: <SettingsPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
